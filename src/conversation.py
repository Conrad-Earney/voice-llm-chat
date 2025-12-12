import os
import json
from datetime import datetime

from config import SAMPLE_RATE, MIN_UTTERANCE_SEC
from src import audio_io, asr_whisper, llm_ollama

from src.logger import debug, error, exc

TAG_ASR = "ASR"
TAG_LOG = "LOG"
TAG_LLM = "LLM"


class ConversationManager:
    def __init__(self):
        self.history = []
        self.turn = 0
        self._pending_turn = None

        base = os.path.join(os.path.dirname(__file__), "..", "sessions")
        os.makedirs(base, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(base, f"session_{ts}")
        os.makedirs(self.session_dir)

        self.log_path = os.path.join(self.session_dir, "conversation_log.jsonl")

    def _log(self, record):
        with open(self.log_path, "a") as f:
            json.dump(record, f)
            f.write("\n")

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

        # Too short / empty: skip saving WAV + skip Whisper
        if audio is None or n_samples == 0 or participant_duration_sec < MIN_UTTERANCE_SEC:
            debug(TAG_ASR, "Audio too short/empty; skipping Whisper")

            text = ""  # keep logs clean; GUI can display "(no speech detected)"

            self._pending_turn = {
                "turn": turn_id,
                "participant_text": text,
                "ai_text": None,
                "participant_duration_sec": participant_duration_sec,
                "ai_duration_sec": None,
            }

            return turn_id, text

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
            "participant_text": text,
            "ai_text": None,
            "participant_duration_sec": participant_duration_sec,
            "ai_duration_sec": None,
        }

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
                reply = llm_ollama.generate_reply(text, self.history)
                outpath = output_audio_path
            except Exception as e:
                # Keeps behavior the same (friendly message), but now we also get a traceback.
                exc(TAG_LLM, e, msg="generate_reply failed")
                reply = "(LLM error — see terminal.)"
                outpath = None

        self.history.append({"role": "participant", "content": text})
        if outpath is not None:  # only on successful LLM call
            self.history.append({"role": "ai", "content": reply})

        if self._pending_turn and self._pending_turn.get("turn") == turn_id:
            self._pending_turn["ai_text"] = reply
        else:
            self._pending_turn = {
                "turn": turn_id,
                "participant_text": text,
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
        debug(TAG_LOG, f"Logged turn {self._pending_turn["turn"]}")

        self._pending_turn = None
