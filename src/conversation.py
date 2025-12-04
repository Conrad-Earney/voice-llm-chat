import os
import json
from datetime import datetime
from src import audio_io, asr_whisper, llm_ollama, tts_engine


class ConversationManager:
    def __init__(self):
        self.history = []
        self.turn = 0

        base = os.path.join(os.path.dirname(__file__), "..", "sessions")
        if not os.path.exists(base):
            os.makedirs(base)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(base, "session_" +   ts)
        os.makedirs(self.session_dir)

        self.log_path = os.path.join(self.session_dir, "conversation_log.jsonl")

    def _log_turn(self, record):
        record["timestamp"] = datetime.now().isoformat()
        with open(self.log_path, "a") as f:
            json.dump(record, f)
            f.write("\n")

    def process_turn(self):
        self.turn += 1

        # 1) Record
        audio = audio_io.record_while_space(max_duration=30)

        # 2) Save input audio
        input_audio_path = os.path.join(
            self.session_dir, "input_turn_{:03d}.wav".format(self.turn)
        )
        audio_io.save_wav(audio, input_audio_path)

        # 3) ASR
        text = asr_whisper.transcribe(audio, 16000).strip()
        if not text:
            print("User: [no speech detected]")
            self._log_turn({
                "turn": self.turn,
                "user_text": "",
                "assistant_text": "",
                "input_audio_path": input_audio_path,
                "output_audio_path": None,
            })
            return

        print("User:", text)

        # 4) LLM
        reply = llm_ollama.generate_reply(text, self.history)
        print("AI:", reply, "\n")

        # 5) TTS (and save output audio file)
        output_audio_path = os.path.join(
            self.session_dir, "output_turn_{:03d}.aiff".format(self.turn)
        )
        tts_engine.speak(reply, output_path=output_audio_path)

        # 6) Update history
        self.history.append({"role": "user", "content": text})
        self.history.append({"role": "assistant", "content": reply})

        # 7) Log everything
        self._log_turn({
            "turn": self.turn,
            "user_text": text,
            "assistant_text": reply,
            "input_audio_path": input_audio_path,
            "output_audio_path": output_audio_path,
        })

    def run_turn_with_audio(self, audio):
        self.turn += 1

        # Save input audio
        input_audio_path = os.path.join(
            self.session_dir, "input_turn_{:03d}.wav".format(self.turn)
        )
        audio_io.save_wav(audio, input_audio_path)

        # ASR
        text = asr_whisper.transcribe(audio, 16000).strip()
        print("User:", text)

        # Handle empty speech
        if not text:
            reply = "(no speech detected)"
            output_audio_path = None

        else:
            # LLM response
            reply = llm_ollama.generate_reply(text, self.history)
            print("AI:", reply)

            # Generate TTS output path but DON'T SPEAK here
            output_audio_path = os.path.join(
                self.session_dir, "output_turn_{:03d}.aiff".format(self.turn)
            )

        # Update history
        self.history.append({"role": "user", "content": text})
        self.history.append({"role": "assistant", "content": reply})

        # Log turn
        self._log_turn({
            "turn": self.turn,
            "user_text": text,
            "assistant_text": reply,
            "input_audio_path": input_audio_path,
            "output_audio_path": output_audio_path,
        })

        # Return values to GUI so GUI controls TTS
        return text, reply, output_audio_path
