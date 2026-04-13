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
    "WAIT_FOR_ROBOT_DONE": True,
    "ROBOT_DONE_TIMEOUT_SEC": 30.0,
    "CHAT_PIPELINE": "computer_chat",
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
    "OPERATOR_REPLY_DELAY_ENABLED": False,
    "OPERATOR_REPLY_DELAY_CPM": 240.0,
    "OPERATOR_REPLY_DELAY_MIN_SEC": 1.0,
    "OPERATOR_REPLY_DELAY_MAX_SEC": 12.0,
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


def _parse_chat_pipeline(value, default=None):
    if value is None:
        return default

    norm = str(value).strip().lower()
    if norm == "robot_chat":
        return "robot_chat"
    if norm == "computer_chat":
        return "computer_chat"
    return default


def _delay_cfg_value(key, default_key, cast=None, local_key=None):
    cfg = _LOCAL_CFG.get("operator_reply_delay")
    if not isinstance(cfg, dict):
        cfg = _COMPUTER_CHAT_CFG.get("operator_reply_delay")
    if not isinstance(cfg, dict):
        cfg = _VOICE_CLIENT_CFG.get("operator_reply_delay")
    if not isinstance(cfg, dict):
        cfg = {}

    if (local_key or key) in _LOCAL_CFG:
        value = _LOCAL_CFG[local_key or key]
    elif key in cfg:
        value = cfg[key]
    else:
        value = _DEFAULTS[default_key]

    return cast(value) if cast else value


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
_VOICE_CLIENT_CFG = {}
_COMPUTER_CHAT_CFG = {}
_ROBOT_CHAT_CFG = {}
_RUNTIME_CFG = {}
_CONVERSATION_CFG = {}
_WATCHDOG_CFG = {}

if _parse_bool(os.getenv("VOICE_LLM_CHAT_DISABLE_UQ_PROFILE"), default=False):
    ACTIVE_PROJECT_ID = "disabled"
else:
    try:
        ACTIVE_PROJECT_ID, _PROJECT_PROFILE = _load_project_profile()
        _VOICE_CLIENT_CFG = _PROJECT_PROFILE.get("voice_client") or {}
        _COMPUTER_CHAT_CFG = _PROJECT_PROFILE.get("computer_chat") or {}
        _ROBOT_CHAT_CFG = _PROJECT_PROFILE.get("robot_chat") or {}
        _RUNTIME_CFG = _PROJECT_PROFILE.get("runtime") or {}
        _CONVERSATION_CFG = _PROJECT_PROFILE.get("conversation") or {}
        _WATCHDOG_CFG = _CONVERSATION_CFG.get("watchdog") or {}
    except Exception as e:
        ACTIVE_PROJECT_ID = "defaults"
        _PROJECT_PROFILE = {}
        _VOICE_CLIENT_CFG = {}
        _COMPUTER_CHAT_CFG = {}
        _ROBOT_CHAT_CFG = {}
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

    if key in _VOICE_CLIENT_CFG:
        value = _VOICE_CLIENT_CFG[key]
        return cast(value) if cast else value

    if key in _COMPUTER_CHAT_CFG:
        value = _COMPUTER_CHAT_CFG[key]
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
WAIT_FOR_ROBOT_DONE = _pick(
    "wait_for_robot_done",
    env_key="VOICE_LLM_CHAT_WAIT_FOR_ROBOT_DONE",
    default_key="WAIT_FOR_ROBOT_DONE",
    cast=lambda v: _parse_bool(v, _DEFAULTS["WAIT_FOR_ROBOT_DONE"]),
)
ROBOT_DONE_TIMEOUT_SEC = _pick(
    "robot_done_timeout_sec",
    env_key="VOICE_LLM_CHAT_ROBOT_DONE_TIMEOUT_SEC",
    default_key="ROBOT_DONE_TIMEOUT_SEC",
    cast=float,
)

mode_override = os.getenv("VOICE_LLM_CHAT_MODE")
if mode_override:
    CHAT_PIPELINE = _parse_chat_pipeline(mode_override, _DEFAULTS["CHAT_PIPELINE"])
else:
    CHAT_PIPELINE = _pick(
        "chat_pipeline",
        env_key="VOICE_LLM_CHAT_PIPELINE",
        default_key="CHAT_PIPELINE",
        cast=lambda v: _parse_chat_pipeline(v, _DEFAULTS["CHAT_PIPELINE"]),
    )

DEFAULT_ROBOT_NAME = (
    os.getenv("VOICE_LLM_CHAT_ROBOT_NAME")
    or _LOCAL_CFG.get("robot_name")
    or _ROBOT_CHAT_CFG.get("robot_name")
)
ROBOT_CHAT_ENABLED = CHAT_PIPELINE == "robot_chat"
ROBOT_CONFIGURED = bool(DEFAULT_ROBOT_NAME)
CONDITION = "robot" if ROBOT_CHAT_ENABLED else "computer"

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
        _parse_bool(_COMPUTER_CHAT_CFG.get("require_enter_before_speak"), False),
    )
)
REQUIRE_ENTER_FOR_WATCHDOG = bool(
    _parse_bool(
        os.getenv("VOICE_LLM_CHAT_REQUIRE_ENTER_FOR_WATCHDOG"),
        _parse_bool(_COMPUTER_CHAT_CFG.get("require_enter_for_watchdog"), False),
    )
)
CONVERSE_INTERLOCUTOR = (
    os.getenv("VOICE_LLM_CHAT_CONVERSE_INTERLOCUTOR")
    or _LOCAL_CFG.get("converse_interlocutor")
    or _COMPUTER_CHAT_CFG.get("converse_interlocutor")
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
    or _COMPUTER_CHAT_CFG.get("converse_model")
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

OPERATOR_REPLY_DELAY_ENABLED = _parse_bool(
    os.getenv("VOICE_LLM_CHAT_OPERATOR_REPLY_DELAY_ENABLED"),
    _parse_bool(
        _delay_cfg_value(
            "enabled",
            "OPERATOR_REPLY_DELAY_ENABLED",
            local_key="operator_reply_delay_enabled",
        ),
        _DEFAULTS["OPERATOR_REPLY_DELAY_ENABLED"],
    ),
)
OPERATOR_REPLY_DELAY_CPM = float(
    os.getenv("VOICE_LLM_CHAT_OPERATOR_REPLY_DELAY_CPM")
    or _delay_cfg_value("characters_per_minute", "OPERATOR_REPLY_DELAY_CPM")
)
OPERATOR_REPLY_DELAY_MIN_SEC = float(
    os.getenv("VOICE_LLM_CHAT_OPERATOR_REPLY_DELAY_MIN_SEC")
    or _delay_cfg_value("min_sec", "OPERATOR_REPLY_DELAY_MIN_SEC")
)
OPERATOR_REPLY_DELAY_MAX_SEC = float(
    os.getenv("VOICE_LLM_CHAT_OPERATOR_REPLY_DELAY_MAX_SEC")
    or _delay_cfg_value("max_sec", "OPERATOR_REPLY_DELAY_MAX_SEC")
)


def validate_mode_settings(robot_enabled=None):
    if robot_enabled is None:
        robot_enabled = ROBOT_CHAT_ENABLED

    if robot_enabled and not ROBOT_CONFIGURED:
        raise RuntimeError(
            "Robot mode is enabled but no robot name is configured. "
            "Set VOICE_LLM_CHAT_ROBOT_NAME, add robot_name to local_config.json, "
            "or load a uq-neuro-nao project profile with robot_chat.robot_name."
        )
