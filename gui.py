import threading
import tkinter as tk
from tkinter import ttk

from src.conversation import ConversationManager
from src.audio_io import Recorder
from src.audio_io import get_audio_duration
from src.tts_engine import speak
from config import ensure_directories_exist

ensure_directories_exist()


def gui():
    convo = ConversationManager()
    rec = Recorder(debug=False)

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
        nonlocal is_listening

        if turn_in_flight:
            print("[UI] Ignoring press: turn already in flight")
            return

        print("Button press")
        is_listening = True
        set_status("Listening…", "red")
        rec.start()

    def on_release(event):
        nonlocal is_listening

        # Ignore releases that happen when we never started listening
        if not is_listening:
            print("[UI] Ignoring release: not currently listening")
            return

        if turn_in_flight:
            print("[UI] Ignoring release: turn already in flight")
            return

        print("Button release")
        is_listening = False

        set_turn_in_flight(True)
        set_status("Processing…", "blue")

        print("[UI] Calling rec.stop()…")
        audio = rec.stop()
        print("[UI] rec.stop() returned")

        def worker():
            try:
                print("[WORKER] Starting worker thread")
                print(
                    f"[WORKER] audio type: {type(audio)}, shape/len: "
                    f"{getattr(audio, 'shape', None) or (len(audio) if audio is not None else 'None')}"
                )

                turn_id, text = convo.transcribe_only(audio)
                print(f"[WORKER] transcription: {text!r}")
                display_text = text if text else "(no speech detected)"
                root.after(0, lambda: show_user(display_text))

                reply, outpath = convo.reply_only(turn_id, text)
                print(f"[WORKER] AI reply: {reply!r}, outpath: {outpath!r}")
                root.after(0, lambda: handle_ai_reply(turn_id, reply, outpath))

            except Exception as e:
                print(f"[WORKER ERROR] {e!r}")
                root.after(0, lambda: set_status("Ready", "green"))
                root.after(0, lambda: set_turn_in_flight(False))

        threading.Thread(target=worker, daemon=True).start()

    def handle_ai_reply(turn_id, reply, outpath):
        show_ai(reply)

        # If there's no outpath, we are not doing TTS (empty input or LLM error).
        if not outpath:
            try:
                convo.finalize_turn_log(turn_id, None)
            except Exception as e:
                print(f"[LOG ERROR] {e!r}")

            set_status("Ready", "green")
            set_turn_in_flight(False)
            return

        set_status("Speaking…", "purple")

        def tts_worker():
            try:
                speak(reply, outpath)

                # Now that the AIFF file exists, measure its duration
                try:
                    ai_duration = get_audio_duration(outpath)
                    if ai_duration is not None:
                        print(f"[TTS] AI audio duration: {ai_duration:.3f} sec")
                    else:
                        print("[TTS] AI audio duration: None")
                except Exception as e:
                    print(f"[TTS ERROR] Could not get AI audio duration: {e!r}")
                    ai_duration = None

                convo.finalize_turn_log(turn_id, ai_duration)

            except Exception as e:
                print(f"[TTS WORKER ERROR] {e!r}")
                # Even on TTS failure, finalize log so the turn completes
                try:
                    convo.finalize_turn_log(turn_id, None)
                except Exception as e2:
                    print(f"[LOG ERROR] {e2!r}")

            root.after(0, lambda: set_status("Ready", "green"))
            root.after(0, lambda: set_turn_in_flight(False))

        threading.Thread(target=tts_worker, daemon=True).start()


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
