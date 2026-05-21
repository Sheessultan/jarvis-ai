"""
Full Windows control — windows, apps, shutdown, lock (ctypes + PowerShell).
Run Main.py as Administrator for shutdown/install-level actions.
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import time

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

user32 = ctypes.windll.user32
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9


def _enum_windows() -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                t = (buf.value or "").strip()
                if t:
                    out.append((hwnd, t))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def _find_hwnd(title_part: str) -> int | None:
    if not title_part:
        hwnd = user32.GetForegroundWindow()
        return hwnd if hwnd else None
    key = title_part.lower().strip()
    for hwnd, title in _enum_windows():
        if key in title.lower():
            return hwnd
    return None


def minimize_window(title_part: str = "") -> tuple[bool, str]:
    hwnd = _find_hwnd(title_part)
    if not hwnd:
        return False, f"Window '{title_part or 'active'}' nahi mili boss."
    user32.ShowWindow(hwnd, SW_MINIMIZE)
    return True, f"Window minimize ho gayi: {title_part or 'active'}."


def maximize_window(title_part: str = "") -> tuple[bool, str]:
    hwnd = _find_hwnd(title_part)
    if not hwnd:
        return False, "Window nahi mili."
    user32.ShowWindow(hwnd, SW_MAXIMIZE)
    return True, "Window maximize ho gayi boss."


def restore_window(title_part: str = "") -> tuple[bool, str]:
    hwnd = _find_hwnd(title_part)
    if not hwnd:
        return False, "Window nahi mili."
    user32.ShowWindow(hwnd, SW_RESTORE)
    return True, "Window restore ho gayi boss."


def focus_window(title_part: str) -> tuple[bool, str]:
    hwnd = _find_hwnd(title_part)
    if not hwnd:
        return False, f"'{title_part}' window nahi mili."
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    return True, f"'{title_part}' window focus ho gayi."


def open_youtube() -> tuple[bool, str]:
    try:
        from Backend.SystemControl import open_url
        open_url("https://www.youtube.com", use_chrome=True)
        return True, "YouTube Chrome me khul gaya boss."
    except Exception as e:
        return False, f"YouTube open fail: {e}"


def lock_workstation() -> tuple[bool, str]:
    try:
        ctypes.windll.user32.LockWorkStation()
        return True, "PC lock ho gaya boss."
    except Exception as e:
        return False, f"Lock fail: {e}"


def shutdown_system(restart: bool = False, delay_sec: int = 60) -> tuple[bool, str]:
    try:
        from Backend.config import ALLOW_SHUTDOWN, SHUTDOWN_DELAY_SEC
    except Exception:
        ALLOW_SHUTDOWN = False
        SHUTDOWN_DELAY_SEC = 60

    if not ALLOW_SHUTDOWN:
        return (
            False,
            "Shutdown band hai safety ke liye. .env mein AllowShutdown=true likho, "
            "phir Main.py Administrator se dubara chalao.",
        )

    delay = max(10, int(delay_sec or SHUTDOWN_DELAY_SEC))
    flag = "/r" if restart else "/s"
    try:
        subprocess.run(
            ["shutdown", flag, "/t", str(delay)],
            check=True,
            creationflags=CREATE_NO_WINDOW,
        )
        action = "restart" if restart else "shutdown"
        return (
            True,
            f"Boss, {delay} second mein system {action} hoga. Cancel: shutdown /a",
        )
    except Exception as e:
        act = "restart" if restart else "shutdown"
        return (
            False,
            f"{act} fail — Main.py ko Administrator se chalao. Error: {e}",
        )


def cancel_shutdown() -> tuple[bool, str]:
    try:
        subprocess.run(["shutdown", "/a"], check=True, creationflags=CREATE_NO_WINDOW)
        return True, "Shutdown cancel ho gaya boss."
    except Exception:
        return False, "Koi scheduled shutdown nahi tha ya cancel fail."


def extract_window_target(query: str) -> str:
    from Backend.QueryNormalize import latin_hint

    h = latin_hint(query)
    for word in (
        "nexus intelligence",
        "nexus",
        "chrome",
        "cursor",
        "notepad",
        "explorer",
        "settings",
        "youtube",
    ):
        if word in h:
            return word
    # Devanagari leftovers
    m = re.search(r"[\u0900-\u097F]+", query)
    if m and "nexus" in h:
        return "nexus"
    return ""


def run_system_command(command: str) -> tuple[bool, str]:
    """command like 'minimize', 'minimize nexus', 'shutdown', 'restart', 'lock'."""
    parts = (command or "").strip().split(maxsplit=1)
    if not parts:
        return False, "System command khali hai."
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("minimize", "minimise", "minimise_window"):
        return minimize_window(arg or extract_window_target(arg))
    if cmd in ("maximize", "maximise"):
        return maximize_window(arg)
    if cmd in ("restore", "normal"):
        return restore_window(arg)
    if cmd in ("focus", "switch"):
        return focus_window(arg) if arg else (False, "Kaun si window focus karni hai bolo.")
    if cmd == "lock":
        return lock_workstation()
    if cmd in ("shutdown", "shut", "band"):
        return shutdown_system(restart=False)
    if cmd in ("restart", "reboot"):
        return shutdown_system(restart=True)
    if cmd == "cancel_shutdown":
        return cancel_shutdown()
    if cmd == "youtube":
        return open_youtube()

    return False, f"Unknown system command: {cmd}"
