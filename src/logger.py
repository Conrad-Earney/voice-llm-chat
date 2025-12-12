import traceback
from datetime import datetime

DEBUG = False


def _ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def debug(tag, msg):
    if DEBUG:
        print(f"[{_ts()}] [{tag}] {msg}")


def info(tag, msg):
    print(f"[{_ts()}] [{tag}] {msg}")


def error(tag, msg):
    print(f"[{_ts()}] [{tag} ERROR] {msg}")


def exc(tag, e, msg=None):
    if msg:
        error(tag, f"{msg}: {repr(e)}")
    else:
        error(tag, repr(e))
    traceback.print_exc()
