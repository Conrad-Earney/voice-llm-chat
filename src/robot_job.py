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


def write_input_job(inbox_dir, turn_id, robot_name, participant_text,
                    input_audio_path=None, participant_duration_sec=None):
    """
    Write a participant-input job JSON for the NAO repo to consume.
    """
    ensure_dir(inbox_dir)

    job = {
        "robot": robot_name,
        "created_at": _now_iso(),
        "turn_id": int(turn_id),
        "user": participant_text,
        "participant_duration_sec": participant_duration_sec,
        "input_audio_path": input_audio_path,
    }

    final_path = os.path.join(inbox_dir, "turn_{:04d}_input.json".format(int(turn_id)))

    try:
        _atomic_write_json(final_path, job)
        debug(TAG, "Wrote input job: {}".format(final_path))
        return final_path
    except Exception as e:
        error(TAG, "Failed to write input job: {}".format(repr(e)))
        return None
