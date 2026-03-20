import os
import json
import time
import numpy as np
from datetime import datetime

from config import (
    ensure_session_robot_dirs,
    SAMPLE_RATE,
    MIN_UTTERANCE_SEC,
    SILENCE_RMS_THRESHOLD,
    ROBOT_OUTBOX_DIRNAME,
    NAO_DONE_TIMEOUT_SEC,
    ROBOT_INBOX_DIRNAME,
    DEFAULT_ROBOT_NAME,
    ROBOT_ENABLED,
    validate_mode_settings,
)
from src import audio_io, asr_whisper, nao_converse

from src.logger import debug, error, exc
from src.robot_job import write_input_job

TAG_ASR = "ASR"
TAG_LOG = "LOG"
TAG_LLM = "LLM"


class ConversationManager:
    def __init__(self, robot_enabled=None, robot_name=None):
        self.history = []
        self.turn = 0
        self._pending_turn = None
        self.robot_enabled = ROBOT_ENABLED if robot_enabled is None else bool(robot_enabled)
        self.robot_name = robot_name or DEFAULT_ROBOT_NAME

        if self.robot_enabled:
            validate_mode_settings(robot_enabled=True)

        base = os.path.join(os.path.dirname(__file__), "..", "sessions")
        os.makedirs(base, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(base, f"session_{ts}")
        os.makedirs(self.session_dir, exist_ok=True)
        if self.robot_enabled:
            ensure_session_robot_dirs(self.session_dir)

        current_path = os.path.join(base, "CURRENT_SESSION.txt")
        with open(current_path, "w") as f:
            f.write(self.session_dir)

        self.log_path = os.path.join(self.session_dir, "conversation_log.jsonl")
        self.dialogue_path = os.path.join(self.session_dir, "session_dialogue.txt")

        # Jobs TO robot (_input.json)
        self.to_robot_dir = None

        # Results FROM robot (.done.json)
        self.from_robot_dir = None

        if self.robot_enabled:
            self.to_robot_dir = os.path.join(self.session_dir, ROBOT_INBOX_DIRNAME)
            self.from_robot_dir = os.path.join(self.session_dir, ROBOT_OUTBOX_DIRNAME)

    def _log(self, record):
        with open(self.log_path, "a") as f:
            json.dump(record, f)
            f.write("\n")

    def _atomic_write_text(self, final_path, text):
        tmp_path = final_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, final_path)

    def _dialogue_line(self, turn_id, speaker, text):
        safe_text = "" if text is None else str(text)
        return "turn_{} {}: {}".format(int(turn_id), speaker, json.dumps(safe_text, ensure_ascii=False))

    def _rewrite_session_dialogue(self):
        lines = []
        if os.path.isfile(self.log_path):
            with open(self.log_path, "r", encoding="utf-8") as f:
                for raw_line in f:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        record = json.loads(raw_line)
                    except Exception:
                        continue

                    turn_id = record.get("turn")
                    if turn_id is None:
                        continue

                    lines.append(self._dialogue_line(turn_id, "user", record.get("user", "")))
                    lines.append(self._dialogue_line(turn_id, "robot", record.get("ai_text", "")))

        # Use two blank lines between speaker turns for easier scanning.
        dialogue_text = "\n\n\n".join(lines)
        if dialogue_text:
            dialogue_text += "\n\n\n"
        self._atomic_write_text(self.dialogue_path, dialogue_text)

    def set_pending_ai_text(self, turn_id, ai_text):
        if self._pending_turn and self._pending_turn.get("turn") == turn_id:
            self._pending_turn["ai_text"] = ai_text

    # ---------------------------------------------------------
    # Phase 1 — Transcription only
    # ---------------------------------------------------------
    def transcribe_only(self, audio):
        """
        Saves input wav + returns (turn_id, transcription text).
        Also computes participant's speech duration and stores a pending log row.
        """
        self.turn += 1
        turn_id = self.turn

        debug(TAG_ASR, f"transcribe_only start, turn {turn_id}")

        # Compute participant duration first so we can short-circuit
        n_samples = len(audio) if audio is not None else 0
        participant_duration_sec = float(n_samples) / float(SAMPLE_RATE)
        debug(TAG_ASR, f"Participant duration (sec): {participant_duration_sec:.3f}")
        audio_rms = float(np.sqrt(np.mean(np.square(audio)))) if n_samples > 0 else 0.0
        debug(TAG_ASR, f"Participant RMS energy: {audio_rms:.6f}")

        input_audio_path = None

        # Too short / empty: skip saving WAV + skip Whisper
        if audio is None or n_samples == 0 or participant_duration_sec < MIN_UTTERANCE_SEC:
            debug(TAG_ASR, "Audio too short/empty; skipping Whisper")
            text = ""  # keep logs clean; GUI can display "(no speech detected)"
        elif audio_rms < SILENCE_RMS_THRESHOLD:
            debug(
                TAG_ASR,
                f"Audio below silence RMS threshold ({audio_rms:.6f} < {SILENCE_RMS_THRESHOLD:.6f}); skipping Whisper",
            )
            text = ""
        else:
            # Save input audio (only if we're going to transcribe)
            input_audio_path = os.path.join(self.session_dir, f"input_turn_{turn_id:03d}.wav")
            debug(TAG_ASR, f"Saving input WAV to: {input_audio_path}")
            audio_io.save_wav(audio, input_audio_path)
            debug(TAG_ASR, "Input WAV saved")

            # Transcribe
            debug(TAG_ASR, "Calling asr_whisper.transcribe…")
            text = asr_whisper.transcribe(audio)
            debug(TAG_ASR, f"Raw transcription: {text!r}")
            text = text.strip()
            debug(TAG_ASR, f"Stripped transcription: {text!r}")

        self._pending_turn = {
            "turn": turn_id,
            "user": text,
            "ai_text": None,
            "participant_duration_sec": participant_duration_sec,
            "ai_duration_sec": None,
        }

        if self.robot_enabled:
            try:
                write_input_job(
                    inbox_dir=self.to_robot_dir,
                    turn_id=turn_id,
                    robot_name=self.robot_name,
                    participant_text=text,
                    input_audio_path=input_audio_path,
                    participant_duration_sec=participant_duration_sec,
                )
            except Exception as e:
                error(TAG_ASR, "write_input_job failed: {}".format(repr(e)))

        return turn_id, text

    # ---------------------------------------------------------
    # Phase 2 — LLM reply only
    # ---------------------------------------------------------
    def reply_only(self, turn_id, text):
        """
        Generates reply, updates history, and determines output path.
        Speaking is handled by GUI.

        Logging is not finalised here; we still need AI audio duration.
        """
        output_audio_path = os.path.join(
            self.session_dir, f"output_turn_{turn_id:03d}.aiff"
        )

        if not text:
            reply = "(no speech detected)"
            outpath = None
        else:
            try:
                reply_data = nao_converse.converse(
                    prompt=text,
                    history=self.history,
                    turn_count=turn_id,
                )
                reply = reply_data["spoken_text"]
                outpath = output_audio_path
            except Exception as e:
                exc(TAG_LLM, e, msg="nao_converse failed")
                reply = "(UQ Py3 converse error — see terminal.)"
                outpath = None

        self.history.append({"role": "user", "content": text})
        if outpath is not None:  # only on successful LLM call
            self.history.append({"role": "assistant", "content": reply})

        if self._pending_turn and self._pending_turn.get("turn") == turn_id:
            self._pending_turn["ai_text"] = reply
        else:
            self._pending_turn = {
                "turn": turn_id,
                "user": text,
                "ai_text": reply,
                "participant_duration_sec": None,
                "ai_duration_sec": None,
            }

        return reply, outpath

    # ---------------------------------------------------------
    # Phase 3 — Finalise log once AI audio exists
    # ---------------------------------------------------------
    def finalize_turn_log(self, turn_id, ai_duration_sec):
        """
        Called after TTS has completed and the AI audio duration is known.
        Writes a single JSON line for the completed turn.
        """
        if not self._pending_turn:
            error(TAG_LOG, "No pending turn to finalise (turn {turn_id})")
            return

        if self._pending_turn.get("turn") != turn_id:
            error(
                TAG_LOG,
                f"Pending turn mismatch: pending={self._pending_turn.get('turn')} got={turn_id}"
            )
            return

        self._pending_turn["ai_duration_sec"] = ai_duration_sec

        self._log(self._pending_turn)
        self._rewrite_session_dialogue()
        debug(TAG_LOG, "Logged turn {}".format(self._pending_turn["turn"]))

        self._pending_turn = None

    # ---------------------------------------------------------
    # NAO-ONLY METHOD
    # ---------------------------------------------------------
    def wait_for_nao_done(self, turn_id, timeout_sec=None, poll_sec=0.05):
        if not self.robot_enabled or not self.from_robot_dir:
            raise RuntimeError("wait_for_nao_done called while robot mode is disabled.")

        if timeout_sec is None:
            timeout_sec = NAO_DONE_TIMEOUT_SEC

        done_path = os.path.join(self.from_robot_dir, "turn_{:04d}_output.json".format(int(turn_id)))

        t0 = time.time()
        while time.time() - t0 < timeout_sec:
            if os.path.isfile(done_path):
                with open(done_path, "r") as f:
                    return json.load(f)
            time.sleep(poll_sec)

        return None
