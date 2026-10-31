"""
Native Windows mouse backend for ZYRO.

Replaces pyautogui with direct SendInput calls. Two reasons:

  1. pyautogui is the single most frequently quarantined package in the
     Python ecosystem - it bundles screen capture, keyboard logging and
     mouse control, which is exactly the signature antivirus heuristics
     look for. It is dual-use by design, not malicious.
  2. Its scroll path is broken on Windows: it passes the raw click count
     as the wheel delta, but Windows counts deltas in units of 120, so
     scrolling produced a sub-notch nudge that applications discard.

Scope is deliberately limited to the pointer: movement, three buttons,
and the wheel. ZYRO cannot synthesise keyboard input at all, so it can
never type into another application.

Everything here uses documented Win32 APIs through ctypes.
"""
import ctypes
import time
from ctypes import wintypes


# --- Constants ---
INPUT_MOUSE = 0

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x01000
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

WHEEL_DELTA = 120
WM_MOUSEWHEEL = 0x020A

SM_CXSCREEN = 0
SM_CYSCREEN = 1

_ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


# The keyboard and hardware members are retained only because the Win32
# INPUT struct is a union of all three; SendInput rejects the call if
# cbSize is not sizeof(INPUT). No keyboard event is ever constructed.
class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
_user32.SendInput.restype = wintypes.UINT
_user32.GetSystemMetrics.argtypes = [ctypes.c_int]
_user32.GetSystemMetrics.restype = ctypes.c_int
_user32.GetCursorPos.argtypes = [ctypes.POINTER(_POINT)]
_user32.GetCursorPos.restype = wintypes.BOOL
_user32.WindowFromPoint.argtypes = [_POINT]
_user32.WindowFromPoint.restype = wintypes.HWND
_user32.PostMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t
]
_user32.PostMessageW.restype = wintypes.BOOL

_INPUT_SIZE = ctypes.sizeof(_INPUT)


def _send(*events):
    """Submit a batch of input events; returns how many Windows accepted."""
    if not events:
        return 0
    array = (_INPUT * len(events))(*events)
    return _user32.SendInput(len(events), array, _INPUT_SIZE)


def _mouse_event(flags, dx=0, dy=0, data=0):
    ev = _INPUT()
    ev.type = INPUT_MOUSE
    ev.mi.dx = dx
    ev.mi.dy = dy
    ev.mi.mouseData = ctypes.c_ulong(data & 0xFFFFFFFF).value
    ev.mi.dwFlags = flags
    ev.mi.time = 0
    ev.mi.dwExtraInfo = 0
    return ev


# --- Screen / cursor ---
def screen_size():
    """Return (width, height) of the primary display."""
    return _user32.GetSystemMetrics(SM_CXSCREEN), _user32.GetSystemMetrics(SM_CYSCREEN)


def cursor_position():
    """Return the current cursor position, or None if unavailable."""
    pt = _POINT()
    if not _user32.GetCursorPos(ctypes.byref(pt)):
        return None
    return pt.x, pt.y


def move_to(x, y):
    """Move the cursor to absolute screen coordinates."""
    width, height = screen_size()
    x = int(max(0, min(width - 1, x)))
    y = int(max(0, min(height - 1, y)))
    # SendInput expects absolute positions normalised across 0..65535.
    abs_x = int(x * 65535 / max(1, width - 1))
    abs_y = int(y * 65535 / max(1, height - 1))
    return _send(_mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, abs_x, abs_y))


# --- Buttons ---
def left_click():
    _send(_mouse_event(MOUSEEVENTF_LEFTDOWN))
    time.sleep(0.012)
    return _send(_mouse_event(MOUSEEVENTF_LEFTUP))


def right_click():
    _send(_mouse_event(MOUSEEVENTF_RIGHTDOWN))
    time.sleep(0.012)
    return _send(_mouse_event(MOUSEEVENTF_RIGHTUP))


def double_click(interval=0.09):
    left_click()
    time.sleep(interval)
    return left_click()


# --- Wheel ---
def wheel(notches):
    """Send properly scaled wheel notches. Returns events accepted."""
    notches = int(notches)
    if notches == 0:
        return 0
    sent = 0
    for _ in range(abs(notches)):
        delta = WHEEL_DELTA if notches > 0 else -WHEEL_DELTA
        sent += _send(_mouse_event(MOUSEEVENTF_WHEEL, data=delta))
        time.sleep(0.008)
    return sent


def wheel_to_window(notches):
    """Fallback: post wheel messages to the window under the cursor.

    Some windows ignore synthesised wheel input; posting the message
    directly to the receiving window avoids that.
    """
    pos = cursor_position()
    if pos is None or not notches:
        return 0
    hwnd = _user32.WindowFromPoint(_POINT(int(pos[0]), int(pos[1])))
    if not hwnd:
        return 0
    posted = 0
    for _ in range(abs(int(notches))):
        delta = WHEEL_DELTA if notches > 0 else -WHEEL_DELTA
        w_param = (int(delta) & 0xFFFF) << 16
        l_param = (int(pos[0]) & 0xFFFF) | ((int(pos[1]) & 0xFFFF) << 16)
        if _user32.PostMessageW(hwnd, WM_MOUSEWHEEL, w_param, l_param):
            posted += 1
        time.sleep(0.008)
    return posted
