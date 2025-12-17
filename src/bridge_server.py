from flask import Flask, jsonify, request
import threading

from src.audio_io import Recorder
from src.conversation import ConversationManager
from src.logger import debug, exc

TAG = "BRIDGE"

app = Flask(__name__)

rec = Recorder()                 # opens stream once (your audio_io.py already does this)
convo = ConversationManager()    # creates session dir etc.

_lock = threading.Lock()
_is_listening = False

@app.post("/start")
def start():
    global _is_listening
    with _lock:
        if _is_listening:
            return jsonify({"ok": True, "already": True})
        _is_listening = True
        rec.start()
    debug(TAG, "Recording started via /start")
    return jsonify({"ok": True})

@app.post("/stop")
def stop():
    global _is_listening
    with _lock:
        if not _is_listening:
            return jsonify({"ok": False, "error": "not_listening"}), 400
        _is_listening = False

    audio = rec.stop()
    turn_id, text = convo.transcribe_only(audio)  # writes the input job to outbox already

    return jsonify({
    "ok": True,
    "turn_id": int(turn_id),
    "transcript": text or "",
    "session_dir": convo.session_dir,
    "outbox_dir": convo.outbox_dir,   # <-- add this
    })


if __name__ == "__main__":
    # Listen on LAN so the robot can hit it
    app.run(host="0.0.0.0", port=5055, threaded=True)
