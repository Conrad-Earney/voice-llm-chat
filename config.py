import io
import json
import os


REQUIRED_DIRS = ["sessions"]

_DEFAULTS = {
    "OLLAMA_MODEL": "custom_1",
    "OLLAMA_URL": "http://localhost:11434",
    "WHISPER_MODEL": "base.en",
    "SAMPLE_RATE": 16000,
    "CONNECT_TIMEOUT_SEC": 3.0,
    "READ_TIMEOUT_SEC": 120.0,
    "MIN_UTTERANCE_SEC": 0.2,
    "SILENCE_RMS_THRESHOLD": 0.005,
    "ROBOT_OUTBOX_DIRNAME": "robot_outbox",
    "ROBOT_INBOX_DIRNAME": "robot_inbox",
    "WAIT_FOR_NAO_DONE": True,
    "NAO_DONE_TIMEOUT_SEC": 30.0,
    "USE_NAO_BACKEND": True,
}


def _repo_root():
    return os.path.abspath(os.path.dirname(__file__))


def _default_uq_config_dir():
    return os.path.abspath(os.path.join(_repo_root(), "..", "uq-neuro-nao", "config"))


def _read_text(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_voice_profile_section(default_project_id="original"):
    config_dir = os.getenv("UQ_PROJECT_CONFIG_DIR", _default_uq_config_dir())
    project_id = os.getenv("UQ_PROJECT_ID", "").strip()

    if not project_id:
        selector_path = os.path.join(config_dir, "active_project.txt")
        if os.path.isfile(selector_path):
            project_id = _read_text(selector_path).strip()

    if not project_id:
        project_id = default_project_id

    profile_path = os.path.join(config_dir, "projects", "{}.json".format(project_id))
    if not os.path.isfile(profile_path):
        raise RuntimeError("Project profile not found: {}".format(profile_path))

    with io.open(profile_path, "r", encoding="utf-8") as f:
        profile = json.load(f)

    return project_id, (profile.get("voice_llm_chat") or {}), (profile.get("nao_worker") or {})


def ensure_directories_exist():
    for d in REQUIRED_DIRS:
        os.makedirs(d, exist_ok=True)


def ensure_session_robot_dirs(session_dir):
    os.makedirs(session_dir, exist_ok=True)
    os.makedirs(os.path.join(session_dir, ROBOT_OUTBOX_DIRNAME), exist_ok=True)
    os.makedirs(os.path.join(session_dir, ROBOT_INBOX_DIRNAME), exist_ok=True)


try:
    ACTIVE_PROJECT_ID, _VOICE_CFG, _NAO_CFG = _load_voice_profile_section()
except Exception as e:
    ACTIVE_PROJECT_ID = "defaults"
    _VOICE_CFG = {}
    _NAO_CFG = {}
    print("WARN: Falling back to built-in defaults ({}).".format(e))

OLLAMA_MODEL = _VOICE_CFG.get("ollama_model", _DEFAULTS["OLLAMA_MODEL"])
OLLAMA_URL = _VOICE_CFG.get("ollama_url", _DEFAULTS["OLLAMA_URL"])
WHISPER_MODEL = _VOICE_CFG.get("whisper_model", _DEFAULTS["WHISPER_MODEL"])
SAMPLE_RATE = int(_VOICE_CFG.get("sample_rate", _DEFAULTS["SAMPLE_RATE"]))
CONNECT_TIMEOUT_SEC = float(_VOICE_CFG.get("connect_timeout_sec", _DEFAULTS["CONNECT_TIMEOUT_SEC"]))
READ_TIMEOUT_SEC = float(_VOICE_CFG.get("read_timeout_sec", _DEFAULTS["READ_TIMEOUT_SEC"]))
MIN_UTTERANCE_SEC = float(_VOICE_CFG.get("min_utterance_sec", _DEFAULTS["MIN_UTTERANCE_SEC"]))
SILENCE_RMS_THRESHOLD = float(
    _VOICE_CFG.get("silence_rms_threshold", _DEFAULTS["SILENCE_RMS_THRESHOLD"])
)

ROBOT_OUTBOX_DIRNAME = _VOICE_CFG.get("robot_outbox_dirname", _DEFAULTS["ROBOT_OUTBOX_DIRNAME"])
ROBOT_INBOX_DIRNAME = _VOICE_CFG.get("robot_inbox_dirname", _DEFAULTS["ROBOT_INBOX_DIRNAME"])
if "robot_name" not in _NAO_CFG:
    raise RuntimeError("Missing nao_worker.robot_name in active project profile.")
DEFAULT_ROBOT_NAME = _NAO_CFG["robot_name"]

WAIT_FOR_NAO_DONE = bool(_VOICE_CFG.get("wait_for_nao_done", _DEFAULTS["WAIT_FOR_NAO_DONE"]))
NAO_DONE_TIMEOUT_SEC = float(_VOICE_CFG.get("nao_done_timeout_sec", _DEFAULTS["NAO_DONE_TIMEOUT_SEC"]))

# True = Robot chat. False = Computer chat.
USE_NAO_BACKEND = bool(_VOICE_CFG.get("use_nao_backend", _DEFAULTS["USE_NAO_BACKEND"]))

COMPUTER = "macmini"
AUDIO_INPUT_NAME = "Scarlett Solo"
