import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime

from src.conversation import ConversationManager
from src.audio_io import Recorder
from src.response_modes import LocalResponseAdapter, RobotResponseAdapter
from config import ensure_directories_exist, USE_NAO_BACKEND, WAIT_FOR_NAO_DONE, validate_mode_settings

from src.logger import debug, exc

ensure_directories_exist()

TAG_UI = "UI"
TAG_WORKER = "WORKER"


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

    # --------------------------------------
    # Fullscreen mode
    # --------------------------------------
    root.attributes("-fullscreen", True)
    root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))

    # --------------------------------------
    # Center container (for consistent layout)
    # --------------------------------------
    container = tk.Frame(root)
    container.place(relx=0.5, rely=0.5, anchor="center")

    # --------------------------------------
    # CHAT WINDOW (scrollable)
    # --------------------------------------
    chat_frame = tk.Frame(container)

    scroll = tk.Scrollbar(chat_frame)
    scroll.pack(side="right", fill="y")

    chat = tk.Text(
        chat_frame,
        width=90,
        height=24,
        wrap="word",
        yscrollcommand=scroll.set,
        font=("Helvetica", 16),
        padx=20,
        pady=20
    )
    chat.pack(side="left", fill="both", expand=True)
    scroll.config(command=chat.yview)

    chat_frame.pack(pady=20)

    # --------------------------------------
    # Chat helpers — LABELS REMOVED
    # --------------------------------------
    def show_user(text):
        chat.insert(tk.END, f"{text}\n\n", ("user_msg",))
        chat.see(tk.END)

    def show_ai(text):
        chat.insert(tk.END, f"{text}\n\n", ("ai_msg",))
        chat.see(tk.END)

    # --------------------------------------
    # Styling tags
    # --------------------------------------
    chat.tag_configure("user_msg", justify="right", foreground="#0066cc")
    chat.tag_configure("ai_msg", justify="left", foreground="#ff4da6")  # pink

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

    def set_turn_in_flight(flag):
        nonlocal turn_in_flight
        turn_in_flight = flag
        try:
            button.state(["disabled"] if flag else ["!disabled"])
        except Exception:
            pass

    # --------------------------------------
    # Recording logic
    # --------------------------------------
    def on_press(event):
        nonlocal is_listening, recording_started_at

        if turn_in_flight:
            debug(TAG_UI, "Ignoring press: turn already in flight")
            return

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
            try:
                turn_id, text = convo.transcribe_only(audio, recording_started_at=started_at)
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

        threading.Thread(target=completion_worker, daemon=True).start()

    # Bind button events
    button.bind("<ButtonPress-1>", on_press)
    button.bind("<ButtonRelease-1>", on_release)

    # Cleanup
    def on_closing():
        rec.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    try:
        root.mainloop()
    finally:
        rec.shutdown()


if __name__ == "__main__":
    gui()
