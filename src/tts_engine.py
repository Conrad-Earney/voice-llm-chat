import subprocess
import os


def speak(text, output_path=None):
    text = (text or "").strip()
    if not text:
        print("[TTS skipped: empty text]")
        return
    
    voice = "Samantha"

    if output_path:
        if not output_path.endswith(".aiff"):
            output_path += ".aiff"

        print("[TTS (say) rendering to {}]".format(output_path))
        rc = subprocess.call(["say", "-v", voice, "-o", output_path, text])
        if rc == 0 and os.path.exists(output_path):
            subprocess.call(["afplay", output_path])
        print("[TTS (say) finished]")
    else:
        print("[TTS (say) about to speak {} chars]".format(len(text)))
        subprocess.call(["say", "-v", voice, text])
        print("[TTS (say) finished]")
