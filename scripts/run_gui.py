# To run:
# cd /Users/conradearney/Documents/repos/voice-llm-chat
# source .venv/bin/activate
# python gui.py

from src.config import ensure_directories_exist

# create sessions directory if it does not already exist
ensure_directories_exist()

from src.asr_whisper import stop_asr
import atexit
atexit.register(stop_asr)

import threading
import tkinter as tk
from tkinter import ttk

from src.conversation import ConversationManager
from src.audio_io import Recorder
from src.tts_engine import speak, stop_tts


def gui():
    convo = ConversationManager()
    rec = Recorder()
    root = tk.Tk()
    root.title("Voice Chat")

    # --- Make window fullscreen ---
    root.attributes("-fullscreen", True)

    # --- Escape to exit full screen, only for developing ---
    root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))  #todo: remove this eventually

     # --- adding a 'container' to centre GUI elements on screen ---
    container = tk.Frame(root)
    container.place(relx=0.5, rely=0.5, anchor="center")

    # --- user text with scrollbar ---
    user_frame = tk.Frame(container)

    user_scroll = tk.Scrollbar(user_frame)
    user_scroll.pack(side="right", fill="y")

    user_text = tk.Text(
        user_frame,
        width=80,
        height=8,
        wrap="word",
        yscrollcommand=user_scroll.set
    )
    user_text.pack(side="left", fill="both", expand=True)

    user_scroll.config(command=user_text.yview)
    user_frame.pack(pady=10)

    # --- ai text with scrollbar ---
    ai_frame = tk.Frame(container)

    ai_scroll = tk.Scrollbar(ai_frame)
    ai_scroll.pack(side="right", fill="y")

    ai_text = tk.Text(
        ai_frame,
        width=80,
        height=12,
        wrap="word",
        yscrollcommand=ai_scroll.set
    )
    ai_text.pack(side="left", fill="both", expand=True)

    ai_scroll.config(command=ai_text.yview)
    ai_frame.pack(pady=10)

    # --- status indicator ---
    status_label = ttk.Label(container, text="Ready", foreground="green")
    status_label.pack(pady=10)

    # --- status updater ---
    def set_status(text, color):
        status_label.config(text=text, foreground=color)
        status_label.update_idletasks()

    # --- button press = start recording ---
    def on_press(event):
        set_status("Listening", "red")
        rec.start()

    # --- button release = stop + process ---
    def on_release(event):
        set_status("Thinking", "blue")

        def worker():
            audio = rec.stop()
            text, reply, outpath = convo.run_turn_with_audio(audio)
            root.after(0, lambda: finalize_turn(text, reply, outpath))

        threading.Thread(target=worker, daemon=True).start()

    # --- finalize after worker thread returns ---
    def finalize_turn(text, reply, outpath):
        user_text.delete("1.0", tk.END)
        user_text.insert(tk.END, text)

        ai_text.delete("1.0", tk.END)
        ai_text.insert(tk.END, reply)

        set_status("Speaking", "purple")

        def tts_worker():
            if outpath:
                speak(reply, outpath)
            root.after(0, lambda: set_status("Ready", "green"))

        threading.Thread(target=tts_worker, daemon=True).start()

    # --- hold-to-talk button ---
    button = ttk.Button(container, text="Hold to Talk")
    button.bind("<ButtonPress-1>", on_press)
    button.bind("<ButtonRelease-1>", on_release)
    button.pack(pady=20)

    root.shutting_down = False

    def shutdown():
        if root.shutting_down:
            return
        root.shutting_down = True

        print("Shutting down...")

        try:
            stop_tts()
        except Exception:
            pass

        try:
            stop_asr()
        except Exception:
            pass

        try:
            rec.is_recording = False 
            rec.stop()
        except Exception:
            pass

        try:
            root.destroy()
            root.quit()
        except Exception:
            pass

        print("Clean exit.")

    # Close window → clean shutdown
    root.protocol("WM_DELETE_WINDOW", shutdown)

    # Catch ctrl+c → clean shutdown
    try:
        root.mainloop()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    # Redundant but useful safety net:
    try:
        gui()
    except KeyboardInterrupt:
        stop_asr()
        print("Force shutdown by user.")
