import os
import json
from datetime import datetime

from src.logger import debug, error

TAG = "ROBOTJOB"


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def _atomic_write_json(final_path, payload):
    tmp_path = final_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, final_path)  # atomic on macOS
        return True
    finally:
        # Best-effort cleanup if something went wrong before replace()
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def write_input_job(outbox_dir, turn_id, robot_name, participant_text,
                    input_audio_path=None, participant_duration_sec=None, extra=None):
    """
    Write a participant-input job JSON for the NAO repo to consume.
    """
    ensure_dir(outbox_dir)

    job = {
        "version": 1,
        "kind": "input",
        "turn_id": int(turn_id),
        "created_at": _now_iso(),
        "robot": robot_name,
        "participant_text": participant_text,
        "input_audio_path": input_audio_path,
        "participant_duration_sec": participant_duration_sec,
        "extra": extra or {},
    }

    final_path = os.path.join(outbox_dir, "turn_{:04d}.input.json".format(int(turn_id)))

    try:
        _atomic_write_json(final_path, job)
        debug(TAG, "Wrote input job: {}".format(final_path))
        return final_path
    except Exception as e:
        error(TAG, "Failed to write input job: {}".format(repr(e)))
        return None
