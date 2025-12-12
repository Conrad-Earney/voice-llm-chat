from faster_whisper import WhisperModel
from config import WHISPER_MODEL
from src.logger import debug

TAG = "ASR"


model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="float32")


def transcribe(audio_array):
    debug(TAG, "Starting transcription")
    segments, _ = model.transcribe(audio_array, language="en")
    text = " ".join(s.text.strip() for s in segments)
    debug(TAG, f"Transcription complete ({len(text)} chars)")
    return text
