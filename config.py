import io
import json
import os


REQUIRED_DIRS = ["sessions"]

_DEFAULTS = {
    "OLLAMA_MODEL": "gesturizer4",
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
    "USE_NAO_BACKEND": False,
    "COMPUTER": "macmini",
    "AUDIO_INPUT_NAME": "Scarlett Solo",
    "TTS_VOICE": "Joelle (Enhanced)",
    "UQ_PY3_API_BASE": "http://localhost:5001",
    "CONVERSE_MODEL": "gesturizer4",
    "CONVERSE_INTERLOCUTOR": None,
    "WATCHDOG_ENABLED": False,
    "WATCHDOG_MODE": True,
    "WATCHDOG_ACTIVATE_AFTER_TURN": 0,
    "WATCHDOG_INTERVAL_SEC": 30.0,
    "WATCHDOG_MAX_CONSECUTIVE_WITHOUT_USER": 2,
    "WATCHDOG_EPHEMERAL_SYSTEM_PROMPT": (
        "The participant has not spoken recently. Re-engage with one short, warm, "
        "context-aware line. Do not mention silence, timing, or that this is a watchdog prompt."
    ),
}


def _repo_root():
    return os.path.abspath(os.path.dirname(__file__))


def _default_uq_config_dir():
    return os.path.abspath(os.path.join(_repo_root(), "..", "uq-neuro-nao", "config"))


def _read_text(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_json(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_bool(value, default=None):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)

    norm = str(value).strip().lower()
    if norm in ("1", "true", "yes", "on", "robot"):
        return True
    if norm in ("0", "false", "no", "off", "local", "voice"):
        return False
    return default


def _optional_json(path):
    if not os.path.isfile(path):
        return {}
    try:
        return _load_json(path)
    except Exception as e:
        print("WARN: Could not load {} ({}).".format(path, e))
        return {}


def _load_project_profile(default_project_id="original"):
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

    profile = _load_json(profile_path)
    return project_id, profile


def _load_local_override():
    override_path = os.getenv(
        "VOICE_LLM_CHAT_CONFIG",
        os.path.join(_repo_root(), "local_config.json"),
    )
    data = _optional_json(override_path)
    return override_path, data


def ensure_directories_exist():
    for d in REQUIRED_DIRS:
        os.makedirs(d, exist_ok=True)


def ensure_session_robot_dirs(session_dir):
    os.makedirs(session_dir, exist_ok=True)
    os.makedirs(os.path.join(session_dir, ROBOT_OUTBOX_DIRNAME), exist_ok=True)
    os.makedirs(os.path.join(session_dir, ROBOT_INBOX_DIRNAME), exist_ok=True)


ACTIVE_PROJECT_ID = None
_PROJECT_PROFILE = {}
_VOICE_CFG = {}
_NAO_CFG = {}
_RUNTIME_CFG = {}
_CONVERSATION_CFG = {}
_WATCHDOG_CFG = {}

if _parse_bool(os.getenv("VOICE_LLM_CHAT_DISABLE_UQ_PROFILE"), default=False):
    ACTIVE_PROJECT_ID = "disabled"
else:
    try:
        ACTIVE_PROJECT_ID, _PROJECT_PROFILE = _load_project_profile()
        _VOICE_CFG = _PROJECT_PROFILE.get("voice_llm_chat") or {}
        _NAO_CFG = _PROJECT_PROFILE.get("nao_worker") or {}
        _RUNTIME_CFG = _PROJECT_PROFILE.get("runtime") or {}
        _CONVERSATION_CFG = _PROJECT_PROFILE.get("conversation") or {}
        _WATCHDOG_CFG = _CONVERSATION_CFG.get("watchdog") or {}
    except Exception as e:
        ACTIVE_PROJECT_ID = "defaults"
        _PROJECT_PROFILE = {}
        _VOICE_CFG = {}
        _NAO_CFG = {}
        _RUNTIME_CFG = {}
        _CONVERSATION_CFG = {}
        _WATCHDOG_CFG = {}
        print("WARN: Falling back to built-in defaults ({}).".format(e))

LOCAL_CONFIG_PATH, _LOCAL_CFG = _load_local_override()


def _pick(key, local_key=None, env_key=None, default_key=None, cast=None):
    if env_key:
        env_val = os.getenv(env_key)
        if env_val not in (None, ""):
            return cast(env_val) if cast else env_val

    lookup_key = local_key or key.lower()
    if lookup_key in _LOCAL_CFG:
        value = _LOCAL_CFG[lookup_key]
        return cast(value) if cast else value

    if key in _VOICE_CFG:
        value = _VOICE_CFG[key]
        return cast(value) if cast else value

    value = _DEFAULTS[default_key or key]
    return cast(value) if cast else value


OLLAMA_MODEL = _pick("ollama_model", env_key="VOICE_LLM_CHAT_OLLAMA_MODEL", default_key="OLLAMA_MODEL")
OLLAMA_URL = _pick("ollama_url", env_key="VOICE_LLM_CHAT_OLLAMA_URL", default_key="OLLAMA_URL")
WHISPER_MODEL = _pick("whisper_model", env_key="VOICE_LLM_CHAT_WHISPER_MODEL", default_key="WHISPER_MODEL")
SAMPLE_RATE = _pick("sample_rate", env_key="VOICE_LLM_CHAT_SAMPLE_RATE", default_key="SAMPLE_RATE", cast=int)
CONNECT_TIMEOUT_SEC = _pick(
    "connect_timeout_sec",
    env_key="VOICE_LLM_CHAT_CONNECT_TIMEOUT_SEC",
    default_key="CONNECT_TIMEOUT_SEC",
    cast=float,
)
READ_TIMEOUT_SEC = _pick(
    "read_timeout_sec",
    env_key="VOICE_LLM_CHAT_READ_TIMEOUT_SEC",
    default_key="READ_TIMEOUT_SEC",
    cast=float,
)
MIN_UTTERANCE_SEC = _pick(
    "min_utterance_sec",
    env_key="VOICE_LLM_CHAT_MIN_UTTERANCE_SEC",
    default_key="MIN_UTTERANCE_SEC",
    cast=float,
)
SILENCE_RMS_THRESHOLD = _pick(
    "silence_rms_threshold",
    env_key="VOICE_LLM_CHAT_SILENCE_RMS_THRESHOLD",
    default_key="SILENCE_RMS_THRESHOLD",
    cast=float,
)

ROBOT_OUTBOX_DIRNAME = _pick(
    "robot_outbox_dirname",
    env_key="VOICE_LLM_CHAT_ROBOT_OUTBOX_DIRNAME",
    default_key="ROBOT_OUTBOX_DIRNAME",
)
ROBOT_INBOX_DIRNAME = _pick(
    "robot_inbox_dirname",
    env_key="VOICE_LLM_CHAT_ROBOT_INBOX_DIRNAME",
    default_key="ROBOT_INBOX_DIRNAME",
)
WAIT_FOR_NAO_DONE = _pick(
    "wait_for_nao_done",
    env_key="VOICE_LLM_CHAT_WAIT_FOR_NAO_DONE",
    default_key="WAIT_FOR_NAO_DONE",
    cast=lambda v: _parse_bool(v, _DEFAULTS["WAIT_FOR_NAO_DONE"]),
)
NAO_DONE_TIMEOUT_SEC = _pick(
    "nao_done_timeout_sec",
    env_key="VOICE_LLM_CHAT_NAO_DONE_TIMEOUT_SEC",
    default_key="NAO_DONE_TIMEOUT_SEC",
    cast=float,
)

mode_override = os.getenv("VOICE_LLM_CHAT_MODE")
if mode_override:
    USE_NAO_BACKEND = _parse_bool(mode_override, _DEFAULTS["USE_NAO_BACKEND"])
else:
    USE_NAO_BACKEND = _pick(
        "use_nao_backend",
        env_key="VOICE_LLM_CHAT_USE_NAO_BACKEND",
        default_key="USE_NAO_BACKEND",
        cast=lambda v: _parse_bool(v, _DEFAULTS["USE_NAO_BACKEND"]),
    )

DEFAULT_ROBOT_NAME = os.getenv("VOICE_LLM_CHAT_ROBOT_NAME") or _LOCAL_CFG.get("robot_name") or _NAO_CFG.get("robot_name")
ROBOT_ENABLED = bool(USE_NAO_BACKEND)
ROBOT_CONFIGURED = bool(DEFAULT_ROBOT_NAME)
CONDITION = "robot" if ROBOT_ENABLED else "voice"

COMPUTER = _pick("computer", env_key="VOICE_LLM_CHAT_COMPUTER", default_key="COMPUTER")
AUDIO_INPUT_NAME = _pick(
    "audio_input_name",
    env_key="VOICE_LLM_CHAT_AUDIO_INPUT_NAME",
    default_key="AUDIO_INPUT_NAME",
)
TTS_VOICE = _pick("tts_voice", env_key="VOICE_LLM_CHAT_TTS_VOICE", default_key="TTS_VOICE")
REQUIRE_ENTER_BEFORE_SPEAK = bool(
    _parse_bool(
        os.getenv("VOICE_LLM_CHAT_REQUIRE_ENTER_BEFORE_SPEAK"),
        _parse_bool(_NAO_CFG.get("require_enter_before_speak"), False),
    )
)
CONVERSE_INTERLOCUTOR = (
    os.getenv("VOICE_LLM_CHAT_CONVERSE_INTERLOCUTOR")
    or _LOCAL_CFG.get("converse_interlocutor")
    or _VOICE_CFG.get("converse_interlocutor")
    or _CONVERSATION_CFG.get("default_interlocutor")
    or _DEFAULTS["CONVERSE_INTERLOCUTOR"]
)
if CONVERSE_INTERLOCUTOR is not None:
    CONVERSE_INTERLOCUTOR = str(CONVERSE_INTERLOCUTOR).strip() or None
UQ_PY3_API_BASE = (
    os.getenv("UQ_PY3_API")
    or os.getenv("VOICE_LLM_CHAT_UQ_PY3_API")
    or _LOCAL_CFG.get("uq_py3_api_base")
    or (
        "http://127.0.0.1:{}".format(_RUNTIME_CFG.get("py3_api_port"))
        if _RUNTIME_CFG.get("py3_api_port")
        else None
    )
    or _DEFAULTS["UQ_PY3_API_BASE"]
)
CONVERSE_MODEL = (
    os.getenv("VOICE_LLM_CHAT_CONVERSE_MODEL")
    or _LOCAL_CFG.get("converse_model")
    or _VOICE_CFG.get("converse_model")
    or _RUNTIME_CFG.get("default_converse_model")
    or _DEFAULTS["CONVERSE_MODEL"]
)

WATCHDOG_ENABLED = _parse_bool(
    os.getenv("VOICE_LLM_CHAT_WATCHDOG_ENABLED"),
    _parse_bool(_LOCAL_CFG.get("watchdog_enabled"), _parse_bool(_WATCHDOG_CFG.get("enabled"), _DEFAULTS["WATCHDOG_ENABLED"])),
)
WATCHDOG_MODE = _parse_bool(
    os.getenv("VOICE_LLM_CHAT_WATCHDOG_MODE"),
    _parse_bool(_LOCAL_CFG.get("watchdog_mode"), _parse_bool(_WATCHDOG_CFG.get("watchdog_mode"), _DEFAULTS["WATCHDOG_MODE"])),
)
WATCHDOG_ACTIVATE_AFTER_TURN = int(
    os.getenv("VOICE_LLM_CHAT_WATCHDOG_ACTIVATE_AFTER_TURN")
    or _LOCAL_CFG.get("watchdog_activate_after_turn")
    or _WATCHDOG_CFG.get("activate_after_turn")
    or _DEFAULTS["WATCHDOG_ACTIVATE_AFTER_TURN"]
)
WATCHDOG_INTERVAL_SEC = float(
    os.getenv("VOICE_LLM_CHAT_WATCHDOG_INTERVAL_SEC")
    or _LOCAL_CFG.get("watchdog_interval_sec")
    or _WATCHDOG_CFG.get("interval_sec")
    or _DEFAULTS["WATCHDOG_INTERVAL_SEC"]
)
WATCHDOG_MAX_CONSECUTIVE_WITHOUT_USER = int(
    os.getenv("VOICE_LLM_CHAT_WATCHDOG_MAX_CONSECUTIVE_WITHOUT_USER")
    or _LOCAL_CFG.get("watchdog_max_consecutive_without_user")
    or _WATCHDOG_CFG.get("max_consecutive_without_user")
    or _DEFAULTS["WATCHDOG_MAX_CONSECUTIVE_WITHOUT_USER"]
)
WATCHDOG_EPHEMERAL_SYSTEM_PROMPT = (
    os.getenv("VOICE_LLM_CHAT_WATCHDOG_EPHEMERAL_SYSTEM_PROMPT")
    or _LOCAL_CFG.get("watchdog_ephemeral_system_prompt")
    or _WATCHDOG_CFG.get("ephemeral_system_prompt")
    or _DEFAULTS["WATCHDOG_EPHEMERAL_SYSTEM_PROMPT"]
)


def validate_mode_settings(robot_enabled=None):
    if robot_enabled is None:
        robot_enabled = ROBOT_ENABLED

    if robot_enabled and not ROBOT_CONFIGURED:
        raise RuntimeError(
            "Robot mode is enabled but no robot name is configured. "
            "Set VOICE_LLM_CHAT_ROBOT_NAME, add robot_name to local_config.json, "
            "or load a uq-neuro-nao project profile with nao_worker.robot_name."
        )
