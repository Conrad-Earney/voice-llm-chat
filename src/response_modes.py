from src.audio_io import get_audio_duration
from src.logger import debug, exc
from src.tts_engine import speak


TAG_ROBOT = "ROBOT"
TAG_TTS = "TTS"
TAG_LOG = "LOG"


class ResponseAdapter:
    def prepare_reply(self, convo, turn_id, text):
        raise NotImplementedError

    def complete_turn(self, convo, turn_id, reply, outpath):
        raise NotImplementedError


class LocalResponseAdapter(ResponseAdapter):
    def prepare_reply(self, convo, turn_id, text):
        return convo.reply_only(turn_id, text)

    def complete_turn(self, convo, turn_id, reply, outpath):
        if not outpath:
            try:
                convo.finalize_turn_log(turn_id, None)
            except Exception as e:
                exc(TAG_LOG, e, msg="finalize_turn_log failed (no TTS path)")
            return

        try:
            speak(reply, outpath)

            try:
                ai_duration = get_audio_duration(outpath)
                if ai_duration is not None:
                    debug(TAG_TTS, f"AI audio duration: {ai_duration:.3f} sec")
                else:
                    debug(TAG_TTS, "AI audio duration: None")
            except Exception as e:
                exc(TAG_TTS, e, msg="Could not get AI audio duration")
                ai_duration = None

            convo.finalize_turn_log(turn_id, ai_duration)

        except Exception as e:
            exc(TAG_TTS, e, msg="TTS worker failed")
            try:
                convo.finalize_turn_log(turn_id, None)
            except Exception as e2:
                exc(TAG_LOG, e2, msg="finalize_turn_log failed after TTS failure")


class RobotResponseAdapter(ResponseAdapter):
    def __init__(self, wait_for_done):
        self.wait_for_done = bool(wait_for_done)

    def prepare_reply(self, convo, turn_id, text):
        if not self.wait_for_done:
            return "(sent to robot)", None

        try:
            done = convo.wait_for_nao_done(turn_id)
        except Exception as e:
            exc(TAG_ROBOT, e, msg="wait_for_nao_done failed")
            done = None

        if done and done.get("ok"):
            segs = done.get("ai_segments_list") or []
            reply_text = " ".join([s[0] for s in segs if s and s[0]])
            if not reply_text:
                reply_text = "(robot spoke)"
        else:
            reply_text = "(robot worker timeout / error — see terminal)"

        return reply_text, None

    def complete_turn(self, convo, turn_id, reply, outpath):
        try:
            convo.finalize_turn_log(turn_id, None)
        except Exception as e:
            exc(TAG_LOG, e, msg="finalize_turn_log failed (robot mode)")
