import threading
import tkinter as tk
import os
import re
from tkinter import ttk
from datetime import datetime

from src.conversation import ConversationManager
from src.audio_io import Recorder
from src.audio_io import get_audio_duration
from src.response_modes import LocalResponseAdapter, RobotResponseAdapter
from src.tts_engine import _wait_for_operator_enter, speak
from config import (
    ensure_directories_exist,
    USE_NAO_BACKEND,
    WAIT_FOR_NAO_DONE,
    WATCHDOG_ENABLED,
    WATCHDOG_ACTIVATE_AFTER_TURN,
    WATCHDOG_INTERVAL_SEC,
    WATCHDOG_MAX_CONSECUTIVE_WITHOUT_USER,
    WATCHDOG_EPHEMERAL_SYSTEM_PROMPT,
    validate_mode_settings,
)

from src.logger import debug, exc

ensure_directories_exist()

TAG_UI = "UI"
TAG_WORKER = "WORKER"
WINDOWED_FALLBACK_GEOMETRY = "1280x800+80+80"


def _signed_offset(value):
    return "+{}".format(value) if value >= 0 else str(value)


def _format_geometry(width, height, x, y):
    return "{}x{}{}{}".format(width, height, _signed_offset(x), _signed_offset(y))


def _parse_geometry_override(raw_value):
    raw_value = (raw_value or "").strip()
    if not raw_value:
        return None

    match = re.fullmatch(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", raw_value)
    if not match:
        return None

    width_text, height_text, x_text, y_text = match.groups()
    return (
        max(200, int(width_text)),
        max(200, int(height_text)),
        int(x_text),
        int(y_text),
    )


def _best_external_geometry(root):
    root.update_idletasks()

    screen_w = int(root.winfo_screenwidth())
    screen_h = int(root.winfo_screenheight())
    vroot_x = int(root.winfo_vrootx())
    vroot_y = int(root.winfo_vrooty())
    vroot_w = int(root.winfo_vrootwidth())
    vroot_h = int(root.winfo_vrootheight())

    virtual_left = vroot_x
    virtual_top = vroot_y
    virtual_right = vroot_x + vroot_w
    virtual_bottom = vroot_y + vroot_h

    candidates = []

    if virtual_left < 0:
        candidates.append((0 - virtual_left, screen_h, virtual_left, 0))
    if virtual_right > screen_w:
        candidates.append((virtual_right - screen_w, screen_h, screen_w, 0))
    if virtual_top < 0:
        candidates.append((screen_w, 0 - virtual_top, 0, virtual_top))
    if virtual_bottom > screen_h:
        candidates.append((screen_w, virtual_bottom - screen_h, 0, screen_h))

    candidates = [candidate for candidate in candidates if candidate[0] >= 400 and candidate[1] >= 300]
    if not candidates:
        return None

    return max(candidates, key=lambda candidate: candidate[0] * candidate[1])


def _enter_presentation_display(root, bounds_override_env):
    override = _parse_geometry_override(os.getenv(bounds_override_env))
    if override is not None:
        width, height, x, y = override
    else:
        target = _best_external_geometry(root)
        if target is None:
            root.geometry(WINDOWED_FALLBACK_GEOMETRY)
            return False
        width, height, x, y = target

    root.attributes("-fullscreen", False)
    root.overrideredirect(True)
    root.geometry(_format_geometry(width, height, x, y))
    root.lift()
    return True


def gui():
    validate_mode_settings(robot_enabled=USE_NAO_BACKEND)
    convo = ConversationManager(robot_enabled=USE_NAO_BACKEND)
    response_adapter = (
        RobotResponseAdapter(wait_for_done=WAIT_FOR_NAO_DONE)
        if USE_NAO_BACKEND
        else LocalResponseAdapter()
    )
    rec = Recorder()

    root = tk.Tk()
    root.title("Voice Chat")

    presentation_mode = _enter_presentation_display(root, "VOICE_LLM_CHAT_DISPLAY_BOUNDS")

    def on_escape(event=None):
        if presentation_mode:
            root.overrideredirect(False)
            root.geometry(WINDOWED_FALLBACK_GEOMETRY)
        else:
            root.attributes("-fullscreen", False)

    root.bind("<Escape>", on_escape)

    # --------------------------------------
    # Center container (for consistent layout)
    # --------------------------------------
    container = tk.Frame(root)
    container.place(relx=0.5, rely=0.5, anchor="center")

    # --------------------------------------
    # Transcript display disabled for participants
    # --------------------------------------
    def show_user(text):
        pass

    def show_ai(text):
        pass

    # --------------------------------------
    # Status indicator
    # --------------------------------------
    status = ttk.Label(container, text="Ready", foreground="green", font=("Helvetica", 16))
    status.pack(pady=10)

    def set_status(text, color):
        status.config(text=text, foreground=color)
        status.update_idletasks()

    # --------------------------------------
    # Button (define early so we can disable/enable it)
    # --------------------------------------
    button = ttk.Button(container, text="Hold to Talk")
    button.pack(pady=20)

    # --------------------------------------
    # Single-turn gating (prevents overlapping turns)
    # --------------------------------------
    turn_in_flight = False
    is_listening = False
    recording_started_at = None
    local_watchdog_after_id = None
    local_watchdog_in_flight = False
    local_watchdog_total = 0
    local_watchdog_consecutive_without_user = 0
    ui_closing = False

    def local_watchdog_active():
        return bool((not USE_NAO_BACKEND) and WATCHDOG_ENABLED)

    def set_turn_in_flight(flag):
        nonlocal turn_in_flight
        turn_in_flight = flag
        try:
            button.state(["disabled"] if flag else ["!disabled"])
        except Exception:
            pass

    def cancel_local_watchdog():
        nonlocal local_watchdog_after_id
        if local_watchdog_after_id is None:
            return
        try:
            root.after_cancel(local_watchdog_after_id)
        except Exception:
            pass
        local_watchdog_after_id = None

    def schedule_local_watchdog():
        nonlocal local_watchdog_after_id
        if not local_watchdog_active():
            return
        if convo.turn < WATCHDOG_ACTIVATE_AFTER_TURN:
            return
        if local_watchdog_consecutive_without_user >= WATCHDOG_MAX_CONSECUTIVE_WITHOUT_USER:
            return
        cancel_local_watchdog()
        local_watchdog_after_id = root.after(
            max(1, int(WATCHDOG_INTERVAL_SEC * 1000)),
            fire_local_watchdog,
        )
        debug(
            TAG_UI,
            "Scheduled local watchdog in {:.3f}s after turn {}".format(
                WATCHDOG_INTERVAL_SEC, convo.turn
            ),
        )

    def finish_local_watchdog(should_reschedule):
        nonlocal local_watchdog_in_flight
        if ui_closing:
            return
        local_watchdog_in_flight = False
        set_status("Ready", "green")
        set_turn_in_flight(False)
        if should_reschedule:
            schedule_local_watchdog()

    def run_local_watchdog_audio(reply, output_path):
        nonlocal local_watchdog_total, local_watchdog_consecutive_without_user
        try:
            speak(reply, output_path)

            try:
                ai_duration = get_audio_duration(output_path)
                if ai_duration is not None:
                    debug(TAG_WORKER, f"Local watchdog audio duration: {ai_duration:.3f} sec")
            except Exception as e:
                exc(TAG_WORKER, e, msg="Could not get local watchdog audio duration")

            local_watchdog_total += 1
            local_watchdog_consecutive_without_user += 1
            debug(
                TAG_WORKER,
                "Local watchdog fired (total={}, consecutive={})".format(
                    local_watchdog_total,
                    local_watchdog_consecutive_without_user,
                ),
            )
            if not ui_closing:
                root.after(0, lambda: finish_local_watchdog(True))
        except Exception as e:
            exc(TAG_WORKER, e, msg="Local watchdog audio worker failed")
            if not ui_closing:
                root.after(0, lambda: finish_local_watchdog(True))

    def handle_local_watchdog_reply(reply, output_path):
        if ui_closing:
            return
        if not reply:
            debug(TAG_WORKER, "Local watchdog generated empty reply")
            finish_local_watchdog(True)
            return

        _wait_for_operator_enter()
        if ui_closing:
            finish_local_watchdog(False)
            return
        set_status("Speaking…", "purple")
        threading.Thread(
            target=run_local_watchdog_audio,
            args=(reply, output_path),
            daemon=True,
        ).start()

    def fire_local_watchdog():
        nonlocal local_watchdog_after_id, local_watchdog_in_flight
        local_watchdog_after_id = None

        if not local_watchdog_active():
            return
        if local_watchdog_in_flight or turn_in_flight or is_listening:
            schedule_local_watchdog()
            return
        if convo.turn < WATCHDOG_ACTIVATE_AFTER_TURN:
            return
        if local_watchdog_consecutive_without_user >= WATCHDOG_MAX_CONSECUTIVE_WITHOUT_USER:
            return

        local_watchdog_in_flight = True
        set_turn_in_flight(True)
        set_status("Processing…", "blue")

        def watchdog_worker():
            try:
                reply = convo.generate_watchdog_reply(
                    ephemeral_system=WATCHDOG_EPHEMERAL_SYSTEM_PROMPT
                )
                output_path = os.path.join(
                    convo.session_dir,
                    "watchdog_{:03d}_{:03d}.aiff".format(
                        int(convo.turn or 0),
                        int(local_watchdog_total + 1),
                    ),
                )
                if not ui_closing:
                    root.after(0, lambda: handle_local_watchdog_reply(reply, output_path))
            except Exception as e:
                exc(TAG_WORKER, e, msg="Local watchdog worker failed")
                if not ui_closing:
                    root.after(0, lambda: finish_local_watchdog(True))

        threading.Thread(target=watchdog_worker, daemon=True).start()

    # --------------------------------------
    # Recording logic
    # --------------------------------------
    def on_press(event):
        nonlocal is_listening, recording_started_at

        if turn_in_flight:
            debug(TAG_UI, "Ignoring press: turn already in flight")
            return

        cancel_local_watchdog()
        is_listening = True
        recording_started_at = datetime.now().isoformat(timespec="milliseconds")
        set_status("Listening…", "red")
        rec.start()

    def on_release(event):
        nonlocal is_listening, recording_started_at

        # Ignore releases that happen when we never started listening
        if not is_listening:
            debug(TAG_UI, "Ignoring release: not currently listening")
            return

        if turn_in_flight:
            debug(TAG_UI, "Ignoring release: turn already in flight")
            return

        is_listening = False

        set_turn_in_flight(True)
        set_status("Processing…", "blue")

        audio = rec.stop()
        started_at = recording_started_at
        recording_started_at = None

        def worker():
            nonlocal local_watchdog_consecutive_without_user
            try:
                turn_id, text = convo.transcribe_only(audio, recording_started_at=started_at)
                if (text or "").strip():
                    local_watchdog_consecutive_without_user = 0
                    debug(TAG_WORKER, "Reset local watchdog consecutive count after participant speech")
                display_text = text if text else "(no speech detected)"
                root.after(0, lambda: show_user(display_text))
                reply, outpath = response_adapter.prepare_reply(convo, turn_id, text)
                root.after(0, lambda: handle_ai_reply(turn_id, reply, outpath))

            except Exception as e:
                exc(TAG_WORKER, e, msg="Worker thread failed")
                root.after(0, lambda: set_status("Ready", "green"))
                root.after(0, lambda: set_turn_in_flight(False))

        threading.Thread(target=worker, daemon=True).start()

    def handle_ai_reply(turn_id, reply, outpath):
        show_ai(reply)
        if outpath:
            _wait_for_operator_enter()
            set_status("Speaking…", "purple")
        else:
            set_status("Completing…", "blue")

        def completion_worker():
            try:
                response_adapter.complete_turn(convo, turn_id, reply, outpath)
            except Exception as e:
                exc(TAG_WORKER, e, msg="Turn completion failed")
            root.after(0, lambda: set_status("Ready", "green"))
            root.after(0, lambda: set_turn_in_flight(False))
            if outpath and local_watchdog_active():
                root.after(0, schedule_local_watchdog)

        threading.Thread(target=completion_worker, daemon=True).start()

    # Bind button events
    button.bind("<ButtonPress-1>", on_press)
    button.bind("<ButtonRelease-1>", on_release)

    # Cleanup
    def on_closing():
        nonlocal ui_closing
        ui_closing = True
        cancel_local_watchdog()
        rec.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    try:
        root.mainloop()
    finally:
        rec.shutdown()


if __name__ == "__main__":
    gui()
