import requests

from config import (
    CONVERSE_INTERLOCUTOR,
    CONVERSE_MODEL,
    CONNECT_TIMEOUT_SEC,
    READ_TIMEOUT_SEC,
    UQ_PY3_API_BASE,
)
from src.logger import debug, error


TAG = "UQPY3"


def segments_to_text(segments_list):
    parts = []
    for seg in (segments_list or []):
        try:
            txt = seg[0]
        except Exception:
            txt = None
        if txt:
            parts.append(txt)
    return " ".join(parts).strip()


def converse(prompt, history=None, turn_count=0, model=None, interlocutor=None, ephemeral_system=None):
    payload = {
        "model": model or CONVERSE_MODEL,
        "interlocutor": interlocutor or CONVERSE_INTERLOCUTOR,
        "turn_count": int(turn_count or 0),
        "history": history or [],
        "prompt": prompt,
    }
    if ephemeral_system:
        payload["ephemeral_system"] = str(ephemeral_system)

    url = UQ_PY3_API_BASE.rstrip("/") + "/converse"
    debug(TAG, "POST {}".format(url))

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=(CONNECT_TIMEOUT_SEC, READ_TIMEOUT_SEC),
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        error(TAG, "Error calling /converse: {}".format(e))
        raise RuntimeError(
            "Could not reach uq-neuro-nao Py3 /converse at {}. "
            "Start `python3 -m src_py3.app` in uq-neuro-nao.".format(url)
        )

    response_text = data.get("response") or ""
    segments_list = data.get("segments_list") or []
    spoken_text = segments_to_text(segments_list) or response_text.strip()
    return {
        "response_text": response_text.strip(),
        "spoken_text": spoken_text,
        "segments_list": segments_list,
    }
