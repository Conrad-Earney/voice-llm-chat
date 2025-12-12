import numpy as np
import wave
from config import SAMPLE_RATE
import sounddevice as sd
import subprocess

from src.logger import debug, error

TAG = "REC"


class Recorder:
    def __init__(self):
        self.frames = []
        self.is_recording = False
        self.stream = None

        def callback(indata, frames, time, status):
            if status:
                # Warnings should always be visible
                error(TAG, f"WARNING: {status}")
            if self.is_recording:
                # Copy is important; indata is reused by sounddevice
                self.frames.append(indata.copy())

        debug(TAG, "Initialising input stream (open once, keep open)")
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        self.stream.start()
        debug(TAG, "Input stream started")

    def start(self):
        debug(TAG, "start() called")
        self.frames = []
        self.is_recording = True
        debug(TAG, "Recording flag set to True")

    def stop(self):
        debug(TAG, "stop() called (only stop capturing, not the stream)")
        self.is_recording = False

        frame_count = len(self.frames) if self.frames is not None else 0
        debug(TAG, f"Frames collected: {frame_count}")

        if not self.frames:
            debug(TAG, "No frames, returning empty audio array")
            return np.zeros((0,), dtype="float32")

        try:
            debug(TAG, "Concatenating frames…")
            audio = np.concatenate(self.frames, axis=0)
            debug(TAG, "Concatenation done")
        except Exception as e:
            error(TAG, f"np.concatenate failed: {repr(e)}")
            return np.zeros((0,), dtype="float32")

        audio = audio.squeeze()
        debug(TAG, f"Returning audio, shape: {getattr(audio, "shape", None)}")
        return audio

    def shutdown(self):
        """Stop and close the underlying stream once, when the app exits."""
        debug(TAG, "shutdown() called – stopping/closing stream")
        self.is_recording = False

        if self.stream is None:
            debug(TAG, "No stream to shut down")
            return

        try:
            self.stream.stop()
            debug(TAG, "stream.stop() completed in shutdown()")
        except Exception as e:
            error(TAG, f"stream.stop() in shutdown() raised: {repr(e)}")

        try:
            self.stream.close()
            debug(TAG, "stream.close() completed in shutdown()")
        except Exception as e:
            error(TAG, f"stream.close() in shutdown() raised: {repr(e)}")

        self.stream = None
        debug(TAG, "Stream set to None")


def save_wav(audio, path):
    audio_i16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_i16.tobytes())


def get_audio_duration(path):
    try:
        info_txt = subprocess.check_output(["afinfo", path], text=True)
        for line in info_txt.splitlines():
            if "estimated duration" in line.lower():
                return float(line.split()[-2])
    except Exception:
        return None
