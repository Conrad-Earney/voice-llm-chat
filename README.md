# voice-llm-chat

Desktop voice chat with two experimental pipelines.

The active project profile defaults to `robot_chat`, because the shared codebase is primarily used for NAO-backed experiments. This checkout uses an ignored `local_config.json` to switch the local default to `computer_chat`.

- `computer_chat`: capture mic audio, transcribe locally, generate a reply through the shared `uq-neuro-nao` Py3 `/converse` path, and speak it on this machine
- `robot_chat`: capture mic audio and hand the turn off to the robot-side chat runner via session inbox/outbox files

The shared conversation core is intentionally reused across both pipelines to keep prompts, history handling, and turn structure aligned for experimental parity.

## Run

Computer-chat pipeline:

```bash
cd /Users/neurorobots/Desktop/repos/uq-neuro-nao
python3 -m src_py3.app

cd /Users/neurorobots/Desktop/repos/voice-llm-chat
python3 gui.py
```

Robot-chat pipeline:

```bash
VOICE_LLM_CHAT_MODE=robot_chat VOICE_LLM_CHAT_ROBOT_NAME=<robot-name> python3 gui.py
```

Bridge server for robot control:

```bash
VOICE_LLM_CHAT_MODE=robot_chat VOICE_LLM_CHAT_ROBOT_NAME=<robot-name> python3 -m src.bridge_server
```

## Configuration

Configuration precedence is:

1. Environment variables
2. `local_config.json` in the repo root
3. `uq-neuro-nao/config/projects/<active>.json` if available
4. Built-in defaults

Built-in default:

- `computer_chat`

Project profile sections:

- `voice_client`: desktop participant app settings, including audio capture, session inbox/outbox names, and selected `chat_pipeline`
- `computer_chat`: local computer-spoken reply settings
- `robot_chat`: robot-side runner settings

Useful environment variables:

- `VOICE_LLM_CHAT_MODE=computer_chat|robot_chat`
- `VOICE_LLM_CHAT_ROBOT_NAME=<robot-name>`
- `VOICE_LLM_CHAT_UQ_PY3_API=http://127.0.0.1:5001`
- `VOICE_LLM_CHAT_CONVERSE_INTERLOCUTOR=<name>`
- `VOICE_LLM_CHAT_AUDIO_INPUT_NAME=<device-name>`
- `VOICE_LLM_CHAT_TTS_VOICE=<macOS say voice>`
- `VOICE_LLM_CHAT_DISPLAY_TARGET=<display-id>` optionally pins the participant GUI to a specific display; by default it uses the first non-main display
- `VOICE_LLM_CHAT_PLACE_ON_TARGET_DISPLAY=0|1` controls whether the GUI is positioned to fill a chosen display before showing; default is `1`
- `VOICE_LLM_CHAT_START_FULLSCREEN=0|1` controls whether the GUI enters fullscreen after being placed on the target display; default is `1`
- `VOICE_LLM_CHAT_REQUIRE_ENTER_BEFORE_SPEAK=1` gates local speech until the operator presses `Return` while the participant GUI is focused
- `VOICE_LLM_CHAT_DISABLE_UQ_PROFILE=1`

This checkout currently uses `local_config.json` as a persistent local override:

```json
{
  "chat_pipeline": "computer_chat",
  "audio_input_name": "Scarlett Solo",
  "tts_voice": "Joelle (Enhanced)"
}
```

To switch this checkout back to the robot-chat pipeline, either:

- change `"chat_pipeline"` to `"robot_chat"` in `local_config.json`
- delete `local_config.json` so the active project profile default applies again

To bypass the local override temporarily, use:

```bash
VOICE_LLM_CHAT_MODE=robot_chat python3 gui.py
```
