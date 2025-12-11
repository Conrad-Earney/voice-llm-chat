import numpy as np
import wave
from config import SAMPLE_RATE
import sounddevice as sd
import subprocess


class Recorder:
    def __init__(self, debug=False):
        self.frames = []
        self.is_recording = False
        self.stream = None
        self.debug = debug

        def callback(indata, frames, time, status):
            if status:
                # Warnings should always be visible
                print(f"[REC WARNING] {status}")
            if self.is_recording:
                # Copy is important; indata is reused by sounddevice
                self.frames.append(indata.copy())

        self._log("Initialising input stream (open once, keep open)")
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        self.stream.start()
        self._log("Input stream started")

    def _log(self, msg):
        """Internal debug logger."""
        if self.debug:
            print(f"[REC] {msg}")

    def _log_error(self, msg):
        """Errors should always be printed."""
        print(f"[REC ERROR] {msg}")

    def start(self):
        self._log("start() called")
        self.frames = []
        self.is_recording = True
        self._log("Recording flag set to True")

    def stop(self):
        self._log("stop() called (only stop capturing, not the stream)")
        self.is_recording = False

        frame_count = len(self.frames) if self.frames is not None else 0
        self._log(f"Frames collected: {frame_count}")

        if not self.frames:
            self._log("No frames, returning empty audio array")
            return np.zeros((0,), dtype="float32")

        try:
            self._log("Concatenating frames…")
            audio = np.concatenate(self.frames, axis=0)
            self._log("Concatenation done")
        except Exception as e:
            self._log_error(f"np.concatenate failed: {e!r}")
            return np.zeros((0,), dtype="float32")

        audio = audio.squeeze()
        self._log(f"Returning audio, shape: {getattr(audio, 'shape', None)}")
        return audio

    def shutdown(self):
        """Stop and close the underlying stream once, when the app exits."""
        self._log("shutdown() called – stopping/closing stream")
        self.is_recording = False

        if self.stream is None:
            self._log("No stream to shut down")
            return

        try:
            self.stream.stop()
            self._log("stream.stop() completed in shutdown()")
        except Exception as e:
            self._log_error(f"stream.stop() in shutdown() raised: {e!r}")

        try:
            self.stream.close()
            self._log("stream.close() completed in shutdown()")
        except Exception as e:
            self._log_error(f"stream.close() in shutdown() raised: {e!r}")

        self.stream = None
        self._log("Stream set to None")


def save_wav(audio, path):
    audio_i16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_i16.tobytes())

def get_audio_duration(path):
    try:
        info = subprocess.check_output(["afinfo", path], text=True)
        for line in info.splitlines():
            if "estimated duration" in line.lower():
                return float(line.split()[-2])
    except Exception:
        return None
