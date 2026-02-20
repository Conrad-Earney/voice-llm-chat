import numpy as np
import wave
from config import SAMPLE_RATE, COMPUTER, AUDIO_INPUT_NAME
import sounddevice as sd
import subprocess

from src.logger import debug, error

TAG = "REC"


class Recorder:
    def __init__(self):
        self.frames = []
        self.is_recording = False
        self.stream = None

        def callback(indata, _frames, _time, status):
            if status:
                error(TAG, f"WARNING: {status}")
            if self.is_recording:
                # Mac mini Scarlett Solo 4th Gen: mic is on channel 2 (index 1)
                if COMPUTER == "macmini" and indata.ndim == 2 and indata.shape[1] >= 2:
                    self.frames.append(indata[:, 1:2].copy())
                else:
                    self.frames.append(indata.copy())

        debug(TAG, "Initialising input stream (open once, keep open)")

        device_index = None
        if COMPUTER == "macmini":
            for i, d in enumerate(sd.query_devices()):
                name = d["name"]
                if AUDIO_INPUT_NAME.lower() in name.lower():
                    device_index = i
                    debug(TAG, f"Matched input device: {name} (index {i})")
                    break
            if device_index is None:
                error(TAG, "Scarlett device not found; falling back to default input")

        self.stream = sd.InputStream(
            device=device_index,   # None = default elsewhere
            samplerate=SAMPLE_RATE,
            channels=2 if COMPUTER == "macmini" else 1,
            dtype="float32",
            callback=callback,
        )
        self.stream.start()
        debug(TAG, "Input stream started")

    def start(self):
        debug(TAG, "start() called")
        self.frames = []
        self.is_recording = True

    def stop(self):
        debug(TAG, "stop() called (only stop capturing, not the stream)")
        self.is_recording = False

        if not self.frames:
            debug(TAG, "No frames, returning empty audio array")
            return np.zeros((0,), dtype="float32")

        try:
            audio = np.concatenate(self.frames, axis=0)
        except Exception as e:
            error(TAG, f"np.concatenate failed: {repr(e)}")
            return np.zeros((0,), dtype="float32")

        audio = audio.squeeze()
        debug(TAG, f"Returning audio, shape: {getattr(audio, 'shape', None)}")
        return audio

    def shutdown(self):
        debug(TAG, "shutdown() called – stopping/closing stream")
        self.is_recording = False

        if self.stream is None:
            debug(TAG, "No stream to shut down")
            return

        try:
            self.stream.stop()
        except Exception as e:
            error(TAG, f"stream.stop() in shutdown() raised: {repr(e)}")

        try:
            self.stream.close()
        except Exception as e:
            error(TAG, f"stream.close() in shutdown() raised: {repr(e)}")

        self.stream = None


def save_wav(audio, path):
    audio_i16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
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