import ctypes
import os
from ctypes import POINTER, Structure, byref, c_double, c_int32, c_uint32

from src.logger import debug


TAG = "DISPLAY"


class _CGPoint(Structure):
    _fields_ = [("x", c_double), ("y", c_double)]


class _CGSize(Structure):
    _fields_ = [("width", c_double), ("height", c_double)]


class _CGRect(Structure):
    _fields_ = [("origin", _CGPoint), ("size", _CGSize)]


def _format_geometry(width, height, x, y):
    x_offset = "+{}".format(x) if x >= 0 else str(x)
    y_offset = "+{}".format(y) if y >= 0 else str(y)
    return "{}x{}{}{}".format(width, height, x_offset, y_offset)


def _load_core_graphics():
    try:
        cg = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
        )
    except Exception:
        return None

    display_id = c_uint32
    cg.CGGetActiveDisplayList.argtypes = [c_uint32, POINTER(display_id), POINTER(c_uint32)]
    cg.CGGetActiveDisplayList.restype = c_int32
    cg.CGMainDisplayID.argtypes = []
    cg.CGMainDisplayID.restype = display_id
    cg.CGDisplayBounds.argtypes = [display_id]
    cg.CGDisplayBounds.restype = _CGRect
    return cg


def _active_displays():
    cg = _load_core_graphics()
    if cg is None:
        return []

    count = c_uint32(0)
    if cg.CGGetActiveDisplayList(0, None, byref(count)) != 0 or count.value < 1:
        return []

    display_ids = (c_uint32 * count.value)()
    if cg.CGGetActiveDisplayList(count, display_ids, byref(count)) != 0:
        return []

    main_id = int(cg.CGMainDisplayID())
    displays = []
    for display_id in display_ids[: count.value]:
        bounds = cg.CGDisplayBounds(display_id)
        displays.append(
            {
                "id": int(display_id),
                "main": int(display_id) == main_id,
                "width": max(1, int(round(bounds.size.width))),
                "height": max(1, int(round(bounds.size.height))),
                "x": int(round(bounds.origin.x)),
                "y": int(round(bounds.origin.y)),
            }
        )

    return displays


def _pick_display(displays):
    target = os.getenv("VOICE_LLM_CHAT_DISPLAY_TARGET", "").strip()
    if target:
        for display in displays:
            if str(display["id"]) == target:
                return display

    for display in displays:
        if not display["main"]:
            return display

    return displays[0] if displays else None


def place_on_target_display(root, fallback_geometry):
    display = _pick_display(_active_displays())
    if display is None:
        root.geometry(fallback_geometry)
        return False

    debug(
        TAG,
        "Using display id={} main={} bounds={}x{}{}{}".format(
            display["id"],
            display["main"],
            display["width"],
            display["height"],
            "+{}".format(display["x"]) if display["x"] >= 0 else display["x"],
            "+{}".format(display["y"]) if display["y"] >= 0 else display["y"],
        ),
    )
    root.attributes("-fullscreen", False)
    root.geometry(
        _format_geometry(
            display["width"],
            display["height"],
            display["x"],
            display["y"],
        )
    )
    root.update_idletasks()
    return True
