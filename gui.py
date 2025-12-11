import threading
import tkinter as tk
from tkinter import ttk

from src.conversation import ConversationManager
from src.audio_io import Recorder
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
    # Recording logic
    # --------------------------------------
    def on_press(event):
        print("Button press")
        set_status("Listening…", "red")
        rec.start()

    def on_release(event):
        print("Button release")
        set_status("Processing…", "blue")
        print("[UI] Calling rec.stop()…")
        audio = rec.stop()
        print("[UI] rec.stop() returned")

        def worker():
            print("[WORKER] Starting worker thread")
            print(f"[WORKER] audio type: {type(audio)}, shape/len: "
                f"{getattr(audio, 'shape', None) or len(audio) if audio is not None else 'None'}")

            text = convo.transcribe_only(audio)
            print(f"[WORKER] transcription: {text!r}")
            root.after(0, lambda: show_user(text))

            reply, outpath = convo.reply_only(text)
            print(f"[WORKER] AI reply: {reply!r}, outpath: {outpath!r}")
            root.after(0, lambda: handle_ai_reply(reply, outpath))

        threading.Thread(target=worker, daemon=True).start()

    def handle_ai_reply(reply, outpath):
        show_ai(reply)

        set_status("Speaking…", "purple")

        def tts_worker():
            if outpath:
                speak(reply, outpath)
            root.after(0, lambda: set_status("Ready", "green"))

        threading.Thread(target=tts_worker, daemon=True).start()

    # --------------------------------------
    # Button
    # --------------------------------------
    button = ttk.Button(container, text="Hold to Talk")
    button.bind("<ButtonPress-1>", on_press)
    button.bind("<ButtonRelease-1>", on_release)
    button.pack(pady=20)

    # Cleanup
    def on_closing():
        # Ensure recorder is cleaned up before exiting
        rec.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    try:
        root.mainloop()
    finally:
        # Safety net in case something else kills the app
        rec.shutdown()

if __name__ == "__main__":
    gui()
