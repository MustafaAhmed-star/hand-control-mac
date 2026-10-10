"""macOS actions: keys, volume, mouse and scrolling.

Uses only built-in macOS frameworks (through ctypes) and `osascript`,
so there are no extra Python packages to install.
"""

import ctypes
import ctypes.util
import subprocess

_cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics")
                              or "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
_cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation")
                              or "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
_ax = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class CGSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class CGRect(ctypes.Structure):
    _fields_ = [("origin", CGPoint), ("size", CGSize)]


def _fn(lib, name, restype, argtypes):
    f = getattr(lib, name)
    f.restype, f.argtypes = restype, argtypes
    return f


_create_key = _fn(_cg, "CGEventCreateKeyboardEvent", ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool])
_create_mouse = _fn(_cg, "CGEventCreateMouseEvent", ctypes.c_void_p,
                    [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32])
_create_event = _fn(_cg, "CGEventCreate", ctypes.c_void_p, [ctypes.c_void_p])
_get_location = _fn(_cg, "CGEventGetLocation", CGPoint, [ctypes.c_void_p])
_set_flags = _fn(_cg, "CGEventSetFlags", None, [ctypes.c_void_p, ctypes.c_uint64])
_set_field = _fn(_cg, "CGEventSetIntegerValueField", None, [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int64])
_post = _fn(_cg, "CGEventPost", None, [ctypes.c_uint32, ctypes.c_void_p])
_main_display = _fn(_cg, "CGMainDisplayID", ctypes.c_uint32, [])
_display_bounds = _fn(_cg, "CGDisplayBounds", CGRect, [ctypes.c_uint32])
_release = _fn(_cf, "CFRelease", None, [ctypes.c_void_p])
_is_trusted = _fn(_ax, "AXIsProcessTrusted", ctypes.c_bool, [])
try:
    # Not variadic, unlike CGEventCreateScrollWheelEvent, so it is safe to call through ctypes. macOS 13+.
    _create_scroll = _fn(_cg, "CGEventCreateScrollWheelEvent2", ctypes.c_void_p,
                         [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                          ctypes.c_int32, ctypes.c_int32, ctypes.c_int32])
except AttributeError:
    _create_scroll = None

_HID_TAP = 0
_FLAGS = {"ctrl": 0x40000, "cmd": 0x100000}
_MODIFIER_KEYS = {"ctrl": 59, "cmd": 55}
_ARROW_FLAGS = 0x800000 | 0x200000  # real arrow key presses carry the Fn and keypad flags
_ARROWS = {123, 124, 125, 126}
_MOUSE = {  # button: (down event, up event, drag event, button number)
    "left": (1, 2, 6, 0),
    "right": (3, 4, 7, 1),
}
_MOUSE_MOVED = 5
_CLICK_STATE = 1  # kCGMouseEventClickState: 2 makes a double click
_SCROLL_PIXELS = 0


def _send(event, flags=None):
    if not event:
        return
    if flags is not None:
        _set_flags(event, flags)
    _post(_HID_TAP, event)
    _release(event)


def press_key(keycode, modifiers=()):
    """Press a key (with Ctrl/Cmd held) in whichever app has keyboard focus."""
    flags = 0
    for mod in modifiers:
        flags |= _FLAGS[mod]
        _send(_create_key(None, _MODIFIER_KEYS[mod], True), flags)
    key_flags = flags | (_ARROW_FLAGS if keycode in _ARROWS else 0)
    _send(_create_key(None, keycode, True), key_flags)
    _send(_create_key(None, keycode, False), key_flags)
    for mod in reversed(modifiers):
        flags &= ~_FLAGS[mod]
        _send(_create_key(None, _MODIFIER_KEYS[mod], False), flags)


def change_volume(delta):
    """Raise or lower the system output volume without blocking the camera loop."""
    script = (
        "set v to (output volume of (get volume settings)) + ({})\n"
        "if v > 100 then set v to 100\n"
        "if v < 0 then set v to 0\n"
        "set volume output volume v"
    ).format(int(delta))
    subprocess.Popen(["osascript", "-e", script],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _cursor():
    event = _create_event(None)
    point = _get_location(event)
    _release(event)
    return point


def move_mouse(x, y, dragging=False):
    """Move the cursor to (x, y), each from 0 to 1 across the main screen."""
    bounds = _display_bounds(_main_display())
    point = CGPoint(bounds.origin.x + x * (bounds.size.width - 1),
                    bounds.origin.y + y * (bounds.size.height - 1))
    kind = _MOUSE["left"][2] if dragging else _MOUSE_MOVED
    _send(_create_mouse(None, kind, point, 0))


def mouse_button(button, down, clicks=1):
    """Press or release a mouse button where the cursor is."""
    down_type, up_type, _, number = _MOUSE[button]
    event = _create_mouse(None, down_type if down else up_type, _cursor(), number)
    if event:
        _set_field(event, _CLICK_STATE, clicks)
    _send(event)


def scroll(amount):
    """Scroll by `amount` pixels; positive moves the page up, like swiping up on a phone."""
    if _create_scroll is None:  # macOS 12 and older: fall back to arrow keys
        press_key(125 if amount > 0 else 126)
        return
    _send(_create_scroll(None, _SCROLL_PIXELS, 1, -int(amount), 0, 0))


def perform(action):
    """Carry out a controller.Action."""
    kind, args = action.kind, action.args
    if kind == "key":
        press_key(*args)
    elif kind == "volume":
        change_volume(*args)
    elif kind == "move":
        move_mouse(*args)
    elif kind == "button":
        mouse_button(*args)
    elif kind == "scroll":
        scroll(*args)


def can_press_keys():
    """True when macOS has granted Accessibility access, which keys and the mouse need."""
    return bool(_is_trusted())


def open_accessibility_settings():
    subprocess.Popen(["open", "x-apple.systempreferences:"
                      "com.apple.preference.security?Privacy_Accessibility"])
