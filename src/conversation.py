import os
import json
from datetime import datetime

from src import audio_io, asr_whisper, llm_ollama


class ConversationManager:
    def __init__(self):
        self.history = []
        self.turn = 0

        # --- session directory ---
        base = os.path.join(os.path.dirname(__file__), "..", "sessions")
        os.makedirs(base, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(base, f"session_{ts}")
        os.makedirs(self.session_dir)

        self.log_path = os.path.join(self.session_dir, "conversation_log.jsonl")

    # ---------------------------------------------------------
    # Logging
    # ---------------------------------------------------------
    def _log(self, record):
        record["timestamp"] = datetime.now().isoformat()
        with open(self.log_path, "a") as f:
            json.dump(record, f)
            f.write("\n")

    # ---------------------------------------------------------
    # Phase 1 — Transcription only
    # ---------------------------------------------------------
    def transcribe_only(self, audio):
        """
        Saves input wav + returns transcription text.
        """
        self.turn += 1
        print(f"[ASR] transcribe_only start, turn {self.turn}")

        input_audio_path = os.path.join(
            self.session_dir, f"input_turn_{self.turn:03d}.wav"
        )
        print(f"[ASR] Saving input WAV to: {input_audio_path}")
        audio_io.save_wav(audio, input_audio_path)
        print("[ASR] Input WAV saved")

        print("[ASR] Calling asr_whisper.transcribe…")
        text = asr_whisper.transcribe(audio)
        print(f"[ASR] Raw transcription: {text!r}")
        text = text.strip()
        print(f"[ASR] Stripped transcription: {text!r}")

        self._log({
            "turn": self.turn,
            "user_text": text,
            "assistant_text": None,
            "input_audio_path": input_audio_path,
            "output_audio_path": None
        })
        print("[ASR] Logged transcription")

        return text

    # ---------------------------------------------------------
    # Phase 2 — LLM reply only
    # ---------------------------------------------------------
    def reply_only(self, text):
        """
        Generates reply, updates history, and determines output path.
        Speaking is handled by GUI.
        """
        if not text:
            reply = "(no speech detected)"
        else:
            reply = llm_ollama.generate_reply(text, self.history)

        # Prepare output audio path (used by TTS)
        output_audio_path = os.path.join(
            self.session_dir, f"output_turn_{self.turn:03d}.aiff"
        )

        # Update conversation history
        self.history.append({"role": "user", "content": text})
        self.history.append({"role": "assistant", "content": reply})

        # Update the JSON log entry
        self._log({
            "turn": self.turn,
            "user_text": text,
            "assistant_text": reply,
            "input_audio_path": f"input_turn_{self.turn:03d}.wav",
            "output_audio_path": output_audio_path
        })

        return reply, output_audio_path
