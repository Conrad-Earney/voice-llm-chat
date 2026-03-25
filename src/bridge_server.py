from flask import Flask, jsonify, request
import threading
import logging
import os
from datetime import datetime

from config import validate_mode_settings
from src.audio_io import Recorder
from src.conversation import ConversationManager
from src.logger import debug, exc

TAG = "BRIDGE"

app = Flask(__name__)

validate_mode_settings(robot_enabled=True)
rec = Recorder()                 # opens stream once (your audio_io.py already does this)
convo = ConversationManager(robot_enabled=True)    # creates session dir etc.

_lock = threading.Lock()
_is_listening = False
_recording_started_at = None

@app.post("/start")
def start():
    global _is_listening, _recording_started_at
    with _lock:
        if _is_listening:
            return jsonify({"ok": True, "already": True})
        _is_listening = True
        _recording_started_at = datetime.now().isoformat(timespec="milliseconds")
        rec.start()
    debug(TAG, "Recording started via /start")
    return jsonify({"ok": True})

@app.post("/stop")
def stop():
    global _is_listening, _recording_started_at
    with _lock:
        if not _is_listening:
            return jsonify({"ok": False, "error": "not_listening"}), 400
        _is_listening = False
        recording_started_at = _recording_started_at
        _recording_started_at = None

    audio = rec.stop()
    turn_id, text = convo.transcribe_only(audio, recording_started_at=recording_started_at)  # writes the input job to outbox already

    return jsonify({
    "ok": True,
    "turn_id": int(turn_id),
    "transcript": text or "",
    "session_dir": convo.session_dir,
    "to_robot_dir": convo.to_robot_dir,
    "from_robot_dir": convo.from_robot_dir,
    })


if __name__ == "__main__":
    # Listen on LAN so the robot can hit it
    if os.getenv("BRIDGE_VERBOSE", "0") != "1":
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(host="0.0.0.0", port=5055, threaded=True)
