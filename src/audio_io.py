import sounddevice as sd
import numpy as np
import sys
import wave
import time
from pynput import keyboard
from src.config import SAMPLE_RATE

class Recorder:
    def __init__(self):
        self.frames = []
        self.is_recording = False
        self.stream = None

    def start(self):
        self.frames = []
        self.is_recording = True

        def callback(indata, frames, time, status):
            if self.is_recording:
                self.frames.append(indata.copy())
            else:
                raise sd.CallbackStop

        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        self.stream.start()

    def stop(self):
        self.is_recording = False

        if self.stream:
            self.stream.stop()
            self.stream.close()

        if not self.frames:
            return np.zeros((0,), dtype="float32")

        audio = np.concatenate(self.frames, axis=0)
        return audio.squeeze()

def wait_for_enter_or_quit():
    sys.stdout.write("Press Enter to speak (or 'q' + Enter to quit): ")
    sys.stdout.flush()
    line = sys.stdin.readline()
    if not line:
        raise KeyboardInterrupt
    if line.strip().lower() == "q":
        raise KeyboardInterrupt

def record_fixed(duration=5):
    wait_for_enter_or_quit()
    print("Recording for {} seconds...".format(duration))
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    return np.squeeze(audio)

def record_while_space(max_duration=30):
    print("Hold SPACE to talk, release to stop.")
    frames = []
    recording = False
    start = None

    def on_press(key):
        nonlocal recording, start
        if key == keyboard.Key.space and not recording:
            recording = True
            start = time.time()
            print("Recording...")

    def on_release(key):
        nonlocal recording
        if key == keyboard.Key.space:
            recording = False
            print("Stopped recording.")

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    def callback(indata, frames_count, time_info, status):
        if recording:
            frames.append(indata.copy())
        elif frames and not recording:
            raise sd.CallbackStop
        if start and time.time() - start > max_duration:
            raise sd.CallbackStop

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                        callback=callback):
        while listener.is_alive():
            time.sleep(0.05)
            if not recording and frames:
                break
    listener.stop()

    if not frames:
        return np.zeros((0,), dtype="float32")
    return np.concatenate(frames, axis=0).squeeze()

def save_wav(audio, path):
    # audio: 1D float32 in [-1, 1]
    audio_i16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_i16.tobytes())
