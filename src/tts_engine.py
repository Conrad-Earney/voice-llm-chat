import subprocess
import os

_tts_proc = None  # global handle to the afplay subprocess


def stop_tts():
    """Stop audio playback immediately."""
    global _tts_proc
    if _tts_proc and _tts_proc.poll() is None:  # still running?
        try:
            _tts_proc.terminate()
        except:
            pass
    _tts_proc = None


def speak(text, output_path=None):
    """Render text to speech and play it, but allow interruption."""
    global _tts_proc

    text = (text or "").strip()
    if not text:
        print("[TTS skipped: empty text]")
        return

    voice = "Samantha"

    # -------------------------------
    # 1) Render audio file using say
    # -------------------------------
    if output_path:
        if not output_path.endswith(".aiff"):
            output_path += ".aiff"

        print("[TTS (say) rendering to {}]".format(output_path))
        rc = subprocess.call(["say", "-v", voice, "-o", output_path, text])

        if rc == 0 and os.path.exists(output_path):
            # ------------------------------------------
            # 2) Play using afplay NON-BLOCKING (Popen)
            # ------------------------------------------
            _tts_proc = subprocess.Popen(["afplay", output_path])
            _tts_proc.wait()  # block this thread, but stoppable via stop_tts()

        print("[TTS (say) finished]")

    else:
        # speak directly without saving file
        print("[TTS (say) about to speak {} chars]".format(len(text)))
        _tts_proc = subprocess.Popen(["say", "-v", voice, text])
        _tts_proc.wait()
        print("[TTS (say) finished]")
