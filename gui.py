import threading
import tkinter as tk
import os
from datetime import datetime

from src.conversation import ConversationManager
from src.audio_io import Recorder
from src.audio_io import get_audio_duration
from src.display import place_on_target_display
from src.response_modes import LocalResponseAdapter, RobotResponseAdapter
from src.tts_engine import speak
from config import (
    ensure_directories_exist,
    REQUIRE_ENTER_BEFORE_SPEAK,
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
FULLSCREEN_AFTER_PLACEMENT_DELAY_MS = 500

APP_BACKGROUND = "#F4F7FB"
BUTTON_BACKGROUND = "#A65300"
BUTTON_FOREGROUND = "#FFFFFF"
BUTTON_ACTIVE_BACKGROUND = "#7A3D00"
BUTTON_BORDER = "#7A3D00"
BUTTON_BUSY_BACKGROUND = "#AAB7C4"
BUTTON_BUSY_FOREGROUND = "#EEF3FF"
BUTTON_BUSY_BORDER = "#7D8A98"
STATUS_FONT = ("Helvetica", 32, "bold")
BUTTON_FONT = ("Helvetica", 28, "bold")


def _env_bool(name, default):
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default

    return raw_value.strip().lower() in ("1", "true", "yes", "on")


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
    root.configure(bg=APP_BACKGROUND)

    place_on_display = _env_bool("VOICE_LLM_CHAT_PLACE_ON_TARGET_DISPLAY", True)
    if place_on_display:
        display_positioned = place_on_target_display(root, WINDOWED_FALLBACK_GEOMETRY)
    else:
        root.geometry(WINDOWED_FALLBACK_GEOMETRY)
        display_positioned = False
    start_fullscreen = _env_bool("VOICE_LLM_CHAT_START_FULLSCREEN", True)

    def enter_fullscreen():
        if display_positioned and start_fullscreen:
            root.attributes("-fullscreen", True)

    if start_fullscreen:
        root.after(FULLSCREEN_AFTER_PLACEMENT_DELAY_MS, enter_fullscreen)

    def on_escape(event=None):
        root.attributes("-fullscreen", False)

    root.bind("<Escape>", on_escape)

    # --------------------------------------
    # Center container (for consistent layout)
    # --------------------------------------
    container = tk.Frame(root, bg=APP_BACKGROUND)
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
    status = tk.Label(
        container,
        text="Ready",
        fg="green",
        bg=APP_BACKGROUND,
        font=STATUS_FONT,
    )
    status.pack(pady=20)

    def set_status(text, color):
        status.config(text=text, fg=color)
        status.update_idletasks()

    def set_button_style(background, foreground, border):
        button_outer.config(bg=border)
        button.config(bg=background, fg=foreground)

    # --------------------------------------
    # Button (define early so we can disable/enable it)
    # --------------------------------------
    button_outer = tk.Frame(
        container,
        bg=BUTTON_BORDER,
        bd=0,
        highlightthickness=0,
    )
    button_outer.pack(pady=32)

    button = tk.Label(
        button_outer,
        text="Hold to Talk",
        font=BUTTON_FONT,
        bg=BUTTON_BACKGROUND,
        fg=BUTTON_FOREGROUND,
        relief="flat",
        bd=0,
        padx=56,
        pady=32,
    )
    button.pack(padx=4, pady=4)

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
    operator_gate_active = False
    operator_gate_callback = None
    ui_closing = False

    def local_watchdog_active():
        return bool((not USE_NAO_BACKEND) and WATCHDOG_ENABLED)

    def release_operator_gate(event=None):
        nonlocal operator_gate_active, operator_gate_callback
        if not operator_gate_active:
            return

        callback = operator_gate_callback
        operator_gate_active = False
        operator_gate_callback = None
        debug(TAG_UI, "Operator released queued speech")
        if callback is not None:
            callback()

    def wait_for_operator_release(callback):
        nonlocal operator_gate_active, operator_gate_callback
        if not REQUIRE_ENTER_BEFORE_SPEAK:
            callback()
            return

        operator_gate_active = True
        operator_gate_callback = callback
        set_status("Processing…", "blue")
        print(
            "[operator_gate] Reply is ready. Press Return while the participant "
            "GUI is focused to play speech."
        )

    def set_turn_in_flight(flag):
        nonlocal turn_in_flight
        turn_in_flight = flag
        try:
            if flag:
                set_button_style(BUTTON_BUSY_BACKGROUND, BUTTON_BUSY_FOREGROUND, BUTTON_BUSY_BORDER)
            else:
                set_button_style(BUTTON_BACKGROUND, BUTTON_FOREGROUND, BUTTON_BORDER)
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

        def start_local_watchdog_audio():
            if ui_closing:
                finish_local_watchdog(False)
                return
            set_status("Speaking…", "purple")
            threading.Thread(
                target=run_local_watchdog_audio,
                args=(reply, output_path),
                daemon=True,
            ).start()

        wait_for_operator_release(start_local_watchdog_audio)

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
        set_button_style(BUTTON_ACTIVE_BACKGROUND, BUTTON_FOREGROUND, BUTTON_ACTIVE_BACKGROUND)
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

        def completion_worker():
            try:
                response_adapter.complete_turn(convo, turn_id, reply, outpath)
            except Exception as e:
                exc(TAG_WORKER, e, msg="Turn completion failed")
            root.after(0, lambda: set_status("Ready", "green"))
            root.after(0, lambda: set_turn_in_flight(False))
            if outpath and local_watchdog_active():
                root.after(0, schedule_local_watchdog)

        def start_completion():
            if ui_closing:
                set_turn_in_flight(False)
                return
            if outpath:
                set_status("Speaking…", "purple")
            else:
                set_status("Completing…", "blue")
            threading.Thread(target=completion_worker, daemon=True).start()

        if outpath:
            wait_for_operator_release(start_completion)
        else:
            start_completion()

    # Bind button events
    button.bind("<ButtonPress-1>", on_press)
    button.bind("<ButtonRelease-1>", on_release)
    button_outer.bind("<ButtonPress-1>", on_press)
    button_outer.bind("<ButtonRelease-1>", on_release)
    root.bind_all("<Return>", release_operator_gate)

    # Cleanup
    def on_closing():
        nonlocal operator_gate_active, operator_gate_callback, ui_closing
        ui_closing = True
        operator_gate_active = False
        operator_gate_callback = None
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
