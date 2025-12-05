import os

REQUIRED_DIRS = ["sessions"]

def ensure_directories_exist():
    for d in REQUIRED_DIRS:
        os.makedirs(d, exist_ok=True)

OLLAMA_MODEL = "llama3.2:1b"
OLLAMA_URL = "http://localhost:11434"
WHISPER_MODEL = "base.en"
TTS_VOICE = "default"
SAMPLE_RATE = 16000
