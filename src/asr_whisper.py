from faster_whisper import WhisperModel
from config import WHISPER_MODEL


model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="float32")

def transcribe(audio_array):
    segments, _ = model.transcribe(audio_array, language="en")
    return " ".join([s.text.strip() for s in segments])
