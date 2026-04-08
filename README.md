# voice-llm-chat

Desktop voice chat with two experimental conditions.

The repo-level default is `robot`, because the shared codebase is primarily used for NAO-backed experiments. This checkout uses an ignored `local_config.json` to switch the local default to `voice`.

- `voice`: capture mic audio, transcribe locally, generate a reply through the shared `uq-neuro-nao` Py3 `/converse` path, and speak it on this machine
- `robot`: capture mic audio and hand the turn off to the robot worker via session inbox/outbox files

The shared conversation core is intentionally reused across both conditions to keep prompts, history handling, and turn structure aligned for experimental parity.

## Run

Voice condition:

```bash
cd /Users/neurorobots/Desktop/repos/uq-neuro-nao
python3 -m src_py3.app

cd /Users/neurorobots/Desktop/repos/voice-llm-chat
python3 gui.py
```

Robot condition:

```bash
VOICE_LLM_CHAT_MODE=robot VOICE_LLM_CHAT_ROBOT_NAME=<robot-name> python3 gui.py
```

Bridge server for robot control:

```bash
VOICE_LLM_CHAT_MODE=robot VOICE_LLM_CHAT_ROBOT_NAME=<robot-name> python3 -m src.bridge_server
```

## Configuration

Configuration precedence is:

1. Environment variables
2. `local_config.json` in the repo root
3. `uq-neuro-nao/config/projects/<active>.json` if available
4. Built-in defaults

Built-in default:

- `robot`

Useful environment variables:

- `VOICE_LLM_CHAT_MODE=voice|robot`
- `VOICE_LLM_CHAT_ROBOT_NAME=<robot-name>`
- `VOICE_LLM_CHAT_UQ_PY3_API=http://127.0.0.1:5001`
- `VOICE_LLM_CHAT_CONVERSE_MODEL=<model>`
- `VOICE_LLM_CHAT_CONVERSE_INTERLOCUTOR=<name>`
- `VOICE_LLM_CHAT_AUDIO_INPUT_NAME=<device-name>`
- `VOICE_LLM_CHAT_TTS_VOICE=<macOS say voice>`
- `VOICE_LLM_CHAT_DISPLAY_TARGET=<display-id>` optionally pins the participant GUI to a specific display; by default it uses the first non-main display
- `VOICE_LLM_CHAT_START_FULLSCREEN=0|1` controls whether the GUI enters fullscreen after being placed on the target display; default is `1`
- `VOICE_LLM_CHAT_REQUIRE_ENTER_BEFORE_SPEAK=1` gates local speech until the operator presses `Return`, keypad `Enter`, or `Space` while the participant GUI is focused
- `VOICE_LLM_CHAT_DISABLE_UQ_PROFILE=1`

This checkout currently uses `local_config.json` as a persistent local override:

```json
{
  "use_nao_backend": false,
  "audio_input_name": "Scarlett Solo",
  "tts_voice": "Zoe (Premium)"
}
```

To switch this checkout back to the robot condition, either:

- change `"use_nao_backend"` to `true` in `local_config.json`
- delete `local_config.json` so the repo default (`robot`) applies again

To bypass the local override temporarily, use:

```bash
VOICE_LLM_CHAT_MODE=robot python3 gui.py
```
