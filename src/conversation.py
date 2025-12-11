import os
import json
from datetime import datetime

from config import SAMPLE_RATE
from src import audio_io, asr_whisper, llm_ollama


class ConversationManager:
    def __init__(self):
        self.history = []
        self.turn = 0

        # Holds the current turn's data until we know everything (including AI duration)
        self._pending_turn = None

        # --- session directory ---
        base = os.path.join(os.path.dirname(__file__), "..", "sessions")
        os.makedirs(base, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(base, f"session_{ts}")
        os.makedirs(self.session_dir)

        self.log_path = os.path.join(self.session_dir, "conversation_log.jsonl")

    # ---------------------------------------------------------
    # Logging: one row per turn, minimal fields
    # ---------------------------------------------------------
    def _log(self, record):
        """Append a single JSON record to the conversation log."""
        with open(self.log_path, "a") as f:
            json.dump(record, f)
            f.write("\n")

    # ---------------------------------------------------------
    # Phase 1 — Transcription only
    # ---------------------------------------------------------
    def transcribe_only(self, audio):
        """
        Saves input wav + returns transcription text.
        Also computes participant's speech duration and stores a pending log row.
        """
        self.turn += 1
        print(f"[ASR] transcribe_only start, turn {self.turn}")

        # Save input audio
        input_audio_path = os.path.join(
            self.session_dir, f"input_turn_{self.turn:03d}.wav"
        )
        print(f"[ASR] Saving input WAV to: {input_audio_path}")
        audio_io.save_wav(audio, input_audio_path)
        print("[ASR] Input WAV saved")

        # Compute participant duration in seconds
        # audio is a 1D float32 array at SAMPLE_RATE
        participant_duration_sec = float(len(audio)) / float(SAMPLE_RATE)
        print(f"[ASR] Participant duration (sec): {participant_duration_sec:.3f}")

        # Transcribe
        print("[ASR] Calling asr_whisper.transcribe…")
        text = asr_whisper.transcribe(audio)
        print(f"[ASR] Raw transcription: {text!r}")
        text = text.strip()
        print(f"[ASR] Stripped transcription: {text!r}")

        # Stash pending turn (we don't log yet, we still need AI text + duration)
        self._pending_turn = {
            "turn": self.turn,
            "participant_text": text,
            "ai_text": None,
            "participant_duration_sec": participant_duration_sec,
            "ai_duration_sec": None,
        }

        return text

    # ---------------------------------------------------------
    # Phase 2 — LLM reply only
    # ---------------------------------------------------------
    def reply_only(self, text):
        """
        Generates reply, updates history, and determines output path.
        Speaking is handled by GUI.

        Note: Logging is not finalised here; we still need the AI audio duration
        after TTS has finished.
        """
        if not text:
            reply = "(no speech detected)"
        else:
            reply = llm_ollama.generate_reply(text, self.history)

        # Prepare output audio path for TTS
        output_audio_path = os.path.join(
            self.session_dir, f"output_turn_{self.turn:03d}.aiff"
        )

        # Update conversation history for context
        self.history.append({"role": "participant", "content": text})
        self.history.append({"role": "ai", "content": reply})

        # Update the pending turn with AI text (if we have one)
        if self._pending_turn and self._pending_turn.get("turn") == self.turn:
            self._pending_turn["ai_text"] = reply
        else:
            # Fallback: if something got out of sync, create a standalone record
            self._pending_turn = {
                "turn": self.turn,
                "participant_text": text,
                "ai_text": reply,
                "participant_duration_sec": None,
                "ai_duration_sec": None,
            }

        return reply, output_audio_path

    # ---------------------------------------------------------
    # Phase 3 — Finalise log once AI audio exists
    # ---------------------------------------------------------
    def finalize_turn_log(self, ai_duration_sec):
        """
        Called after TTS has completed and the AI audio duration is known.
        Writes a single JSON line for the completed turn.
        """
        if not self._pending_turn:
            print("[LOG] No pending turn to finalise")
            return

        self._pending_turn["ai_duration_sec"] = ai_duration_sec

        self._log(self._pending_turn)
        print(f"[LOG] Logged turn {self._pending_turn['turn']}")

        # Clear for next turn
        self._pending_turn = None
