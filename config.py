import os


REQUIRED_DIRS = ["sessions"]

def ensure_directories_exist():
    for d in REQUIRED_DIRS:
        os.makedirs(d, exist_ok=True)

def ensure_session_robot_dirs(session_dir):
    os.makedirs(session_dir, exist_ok=True)
    os.makedirs(os.path.join(session_dir, ROBOT_OUTBOX_DIRNAME), exist_ok=True)
    os.makedirs(os.path.join(session_dir, ROBOT_INBOX_DIRNAME), exist_ok=True)

OLLAMA_MODEL = "custom_1"
OLLAMA_URL = "http://localhost:11434"
WHISPER_MODEL = "base.en"
SAMPLE_RATE = 16000
CONNECT_TIMEOUT_SEC = 3.0
READ_TIMEOUT_SEC = 120.0
MIN_UTTERANCE_SEC = 0.2

ROBOT_OUTBOX_DIRNAME = "robot_outbox"
ROBOT_INBOX_DIRNAME = "robot_inbox"
DEFAULT_ROBOT_NAME = "clas"

WAIT_FOR_NAO_DONE = True
NAO_DONE_TIMEOUT_SEC = 30.0

# True = Robot chat. False = Computer chat.
USE_NAO_BACKEND = True
