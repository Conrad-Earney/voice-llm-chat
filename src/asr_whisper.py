from faster_whisper import WhisperModel
from src.config import WHISPER_MODEL

model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="float32")

def transcribe(audio_array, sample_rate):
    segments, _ = model.transcribe(audio_array, language="en")
    return " ".join([s.text.strip() for s in segments])
