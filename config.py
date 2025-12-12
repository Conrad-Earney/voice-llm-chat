import os


REQUIRED_DIRS = ["sessions"]

def ensure_directories_exist():
    for d in REQUIRED_DIRS:
        os.makedirs(d, exist_ok=True)

OLLAMA_MODEL = "custom_1"
OLLAMA_URL = "http://localhost:11434"
WHISPER_MODEL = "base.en"
TTS_VOICE = "default"
SAMPLE_RATE = 16000
CONNECT_TIMEOUT_SEC = 3.0
READ_TIMEOUT_SEC = 120.0
MIN_UTTERANCE_SEC = 0.2
