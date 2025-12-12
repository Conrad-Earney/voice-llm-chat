import subprocess
import os

from src.logger import debug, error

TAG = "TTS"


def speak(text, output_path):
    """Render TTS to a file and play it."""

    text = (text or "").strip()
    if not text:
        debug(TAG, "Skipping: empty text")
        return

    if not output_path.endswith(".aiff"):
        output_path += ".aiff"

    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.isdir(out_dir):
        error(TAG, f"Output directory does not exist: {out_dir}")
        return

    debug(TAG, f"Rendering and playing: {output_path}")

    # Render
    try:
        subprocess.check_call(
            ["say", "-v", "Samantha (Enhanced)", "-o", output_path, text]
        )
    except subprocess.CalledProcessError as e:
        error(TAG, f"say failed: {e}")
        return

    # Play
    try:
        subprocess.check_call(["afplay", output_path])
    except subprocess.CalledProcessError as e:
        error(TAG, f"afplay failed: {e}")
    else:
        debug(TAG, "Complete")
