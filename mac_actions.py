"""macOS actions: change the volume and press keys.

Uses only built-in macOS frameworks (through ctypes) and `osascript`,
so there are no extra Python packages to install.
"""

import ctypes
import ctypes.util
import subprocess

VOLUME_STEP = 6  # percent per step

# macOS virtual key codes
KEY_LEFT = 123
KEY_RIGHT = 124
KEY_SPACE = 49

_cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics")
                              or "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
_cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation")
                              or "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
_ax = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")

_cg.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
_cg.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
_cg.CGEventPost.restype = None
_cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
_cf.CFRelease.restype = None
_cf.CFRelease.argtypes = [ctypes.c_void_p]
_ax.AXIsProcessTrusted.restype = ctypes.c_bool
_ax.AXIsProcessTrusted.argtypes = []

_kCGHIDEventTap = 0


def press_key(keycode):
    """Press and release a key in whichever app has keyboard focus."""
    for down in (True, False):
        event = _cg.CGEventCreateKeyboardEvent(None, keycode, down)
        if event:
            _cg.CGEventPost(_kCGHIDEventTap, event)
            _cf.CFRelease(event)


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


def can_press_keys():
    """True when macOS has granted Accessibility access, which key presses need."""
    return bool(_ax.AXIsProcessTrusted())


def open_accessibility_settings():
    subprocess.Popen(["open", "x-apple.systempreferences:"
                      "com.apple.preference.security?Privacy_Accessibility"])
