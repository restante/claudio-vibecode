"""Hold and release the key Claude Code's voice mode listens to (space, in `hold` mode).

This presses a key in whatever window is in front, so the Claude terminal must be focusable and
the screen unlocked. macOS needs Accessibility permission for the terminal app that started the hub.
"""

from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
import threading

import psutil

MAX_HOLD = 90.0  # seconds; a phone that loses its connection must not leave space held down
_APPS = {
    "Apple_Terminal": "Terminal",
    "iTerm.app": "iTerm",
    "ghostty": "Ghostty",
    "WezTerm": "WezTerm",
    "vscode": "Visual Studio Code",
    "kitty": "kitty",
    "Alacritty": "Alacritty",
    "Hyper": "Hyper",
    "WarpTerminal": "Warp",
}
REPEAT_DELAY = 0.35  # seconds before a held key starts repeating
REPEAT_EVERY = 0.033  # then about 30 repeats a second
_timer: threading.Timer | None = None
_stop: threading.Event | None = None
_held = False


def app_for(term_program: str) -> str | None:
    return _APPS.get(term_program)


def _mac_trusted() -> bool:
    lib = ctypes.CDLL(
        "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
    )
    lib.AXIsProcessTrusted.restype = ctypes.c_bool
    return bool(lib.AXIsProcessTrusted())


def _mac_key(down: bool, repeat: bool = False) -> None:
    quartz = ctypes.CDLL(
        "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
    )
    core = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    quartz.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
    quartz.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
    quartz.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    core.CFRelease.argtypes = [ctypes.c_void_p]
    quartz.CGEventSetIntegerValueField.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int64]
    event = quartz.CGEventCreateKeyboardEvent(None, 49, down)  # 49 = space
    if repeat:
        quartz.CGEventSetIntegerValueField(event, 8, 1)  # kCGKeyboardEventAutorepeat
    quartz.CGEventPost(0, event)  # kCGHIDEventTap
    core.CFRelease(event)


class KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_uint16), ("wScan", ctypes.c_uint16), ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t),
    ]  # fmt: skip


class _InputUnion(ctypes.Union):
    # MOUSEINPUT is the largest member (32 bytes on 64-bit); keep the union that big.
    _fields_ = [("ki", KeyboardInput), ("pad", ctypes.c_byte * 32)]


class Input(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_uint32), ("u", _InputUnion)]


def _win_key(down: bool) -> None:
    flags = 0 if down else 0x0002  # KEYEVENTF_KEYUP
    item = Input(type=1, ki=KeyboardInput(wVk=0x20, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0))
    sent = ctypes.windll.user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(item))  # type: ignore[attr-defined]
    if sent != 1:
        raise OSError(
            "Windows refused the key press (is the target window running as administrator?)"
        )


def _linux_key(down: bool) -> None:
    subprocess.run(["xdotool", "keydown" if down else "keyup", "space"], check=False)


def available() -> tuple[bool, str]:
    """Whether the key can be sent here, and if not, what to fix."""
    if sys.platform == "darwin":
        if not _mac_trusted():
            return False, (
                "macOS Accessibility permission is missing: System Settings > Privacy & Security >"
                " Accessibility, allow the terminal app you start Claude from, then `/vibe"
                " off` and `on`."
            )
        return True, ""
    if sys.platform == "win32":
        return True, ""
    if shutil.which("xdotool"):
        return True, ""
    return False, "install xdotool to use the voice button on Linux (X11 only)"


def ancestors(pid: int | None) -> list[int]:
    """`pid` and its parents, nearest first: the terminal window owns one of them."""
    chain: list[int] = []
    try:
        proc = psutil.Process(pid) if pid else None
        while proc is not None and proc.pid not in chain and proc.pid > 4:
            chain.append(proc.pid)
            proc = proc.parent()
    except psutil.Error:
        pass
    return chain


def _activate(app: str | None, pid: int | None = None) -> None:
    """Bring the window running this Claude session to the front, best effort."""
    chain = ancestors(pid)
    if sys.platform == "win32":
        # AppActivate focuses the window owned by a process id; try each ancestor until one has one.
        ids = ",".join(str(p) for p in chain)
        if ids:
            script = (
                "$s = New-Object -ComObject WScript.Shell; "
                f"foreach ($p in @({ids})) {{ if ($s.AppActivate($p)) {{ break }} }}"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                check=False, capture_output=True, timeout=10,
            )  # fmt: skip
    elif sys.platform == "darwin":
        for p in chain:
            script = (
                'tell application "System Events" to set frontmost of '
                f"(first process whose unix id is {p}) to true"
            )
            done = subprocess.run(["osascript", "-e", script], capture_output=True, check=False)
            if done.returncode == 0:
                return
        if app:
            subprocess.run(
                ["osascript", "-e", f'tell application "{app}" to activate'], check=False
            )
    # Linux: no portable way; the terminal must already be in front.


def _send(down: bool, repeat: bool = False) -> None:
    if sys.platform == "darwin":
        _mac_key(down, repeat)
    elif sys.platform == "win32":
        _win_key(down)
    else:
        _linux_key(down)


def _repeat(stop: threading.Event) -> None:
    """A held key repeats on a real keyboard; Claude's voice mode reads that as "still held"."""
    if stop.wait(REPEAT_DELAY):
        return
    while not stop.wait(REPEAT_EVERY):
        try:
            _send(True, repeat=True)
        except OSError:
            return


def _release() -> None:
    global _held, _timer, _stop
    if _stop is not None:
        _stop.set()
        _stop = None
    if _held:
        _send(False)
        _held = False
    if _timer:
        _timer.cancel()
        _timer = None


def hold(down: bool, app: str | None = None, pid: int | None = None) -> tuple[bool, str]:
    """Press (`down`) or release the voice key. Returns (ok, message)."""
    global _held, _timer, _stop
    ok, why = available()
    if not ok:
        return False, why
    if down:
        if _held:
            return True, ""
        _activate(app, pid)
        try:
            _send(True)
        except OSError as error:
            return False, str(error)
        _held = True
        _stop = threading.Event()
        threading.Thread(target=_repeat, args=(_stop,), daemon=True).start()
        _timer = threading.Timer(MAX_HOLD, _release)
        _timer.daemon = True
        _timer.start()
    else:
        _release()
    return True, ""
