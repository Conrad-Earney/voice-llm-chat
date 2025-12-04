# To run:
# cd /Users/conradearney/Documents/repos/voice-llm-chat
# source .venv/bin/activate
# python gui.py

import threading
import tkinter as tk
from tkinter import ttk

from src.conversation import ConversationManager
from src.audio_io import Recorder
from src.tts_engine import speak


def gui():
    convo = ConversationManager()
    rec = Recorder()
    root = tk.Tk()
    root.title("Voice Chat")

    # --- UI elements ---
    user_text = tk.Text(root, height=3, width=60)
    ai_text = tk.Text(root, height=3, width=60)
    status_label = ttk.Label(root, text="Ready", foreground="green")

    user_text.pack(padx=10, pady=5)
    ai_text.pack(padx=10, pady=5)
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
            # Move rec.stop() OFF the GUI thread
            audio = rec.stop()

            # Heavy backend work
            text, reply, outpath = convo.run_turn_with_audio(audio)

            # Back to GUI thread
            root.after(0, lambda: finalize_turn(text, reply, outpath))

        threading.Thread(target=worker).start()

    # --- finalize after worker thread returns ---
    def finalize_turn(text, reply, outpath):
        # Update text boxes immediately
        user_text.delete("1.0", tk.END)
        user_text.insert(tk.END, text)

        ai_text.delete("1.0", tk.END)
        ai_text.insert(tk.END, reply)

        # Show speaking status before TTS starts
        set_status("Speaking", "purple")

        def tts_worker():
            if outpath:   # None if "(no speech detected)"
                speak(reply, outpath)
            root.after(0, lambda: set_status("Ready", "green"))

        threading.Thread(target=tts_worker).start()


    # --- button setup ---
    button = ttk.Button(root, text="Hold to Talk")
    button.bind("<ButtonPress-1>", on_press)
    button.bind("<ButtonRelease-1>", on_release)
    button.pack(pady=20)

    root.mainloop()


if __name__ == "__main__":
    gui()
