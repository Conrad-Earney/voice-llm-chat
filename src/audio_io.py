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
        self.input_channels = 1

        def callback(indata, _frames, _time, status):
            if status:
                error(TAG, f"WARNING: {status}")
            if self.is_recording:
                # Mac mini Scarlett Solo 4th Gen: mic is on channel 2 (index 1)
                if COMPUTER == "macmini" and self.input_channels >= 2 and indata.ndim == 2 and indata.shape[1] >= 2:
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

        default_channels = 2 if COMPUTER == "macmini" else 1
        try:
            # Resolve actual input device so channel count can be validated.
            resolved_device = device_index
            if resolved_device is None:
                default_dev = sd.default.device
                if isinstance(default_dev, (tuple, list)):
                    resolved_device = default_dev[0]
                else:
                    resolved_device = default_dev

            dev_info = sd.query_devices(resolved_device, "input")
            max_in = int(dev_info.get("max_input_channels", 0) or 0)
            if max_in <= 0:
                raise RuntimeError("selected input device has zero input channels")

            self.input_channels = min(default_channels, max_in)
            if self.input_channels < 1:
                self.input_channels = 1

            debug(TAG, f"Using input device '{dev_info.get('name', 'unknown')}' with channels={self.input_channels} (max_input_channels={max_in})")
        except Exception as e:
            error(TAG, f"Could not inspect input device channels ({e}); falling back to channels=1")
            self.input_channels = 1

        self.stream = sd.InputStream(
            device=device_index,   # None = default elsewhere
            samplerate=SAMPLE_RATE,
            channels=self.input_channels,
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
