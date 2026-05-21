"""
Live Windows context — active window, open apps, IP, optional screen vision.
"""

from __future__ import annotations

import base64
import ctypes
import os
import re
import subprocess
from io import BytesIO
from typing import Callable

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
_DATA = "Data"


def _ps(script: str, timeout: int = 12) -> str:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        return (r.stdout or r.stderr or "").strip()
    except Exception as e:
        return f"(error: {e})"


def get_active_window_title() -> str:
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        return (buf.value or "").strip() or "Unknown"
    except Exception:
        return "Unknown"


def get_open_window_titles(limit: int = 10) -> list[str]:
    titles: list[str] = []

    def _enum(hwnd, _):
        try:
            if not ctypes.windll.user32.IsWindowVisible(hwnd):
                return True
            n = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if n <= 0:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, n + 1)
            t = (buf.value or "").strip()
            if t and len(t) > 2 and t not in titles:
                titles.append(t)
        except Exception:
            pass
        return True

    try:
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum), 0)
    except Exception:
        pass
    return titles[:limit]


def get_local_ip_text() -> str:
    script = (
        "Get-NetIPAddress -AddressFamily IPv4 | "
        "Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } | "
        "Select-Object -First 5 IPAddress, InterfaceAlias | "
        "Format-Table -AutoSize | Out-String -Width 200"
    )
    out = _ps(script)
    if out and "IPAddress" in out:
        return out.strip()
    # fallback
    out2 = _ps("ipconfig | findstr /i \"IPv4\"")
    return out2.strip() or "IP detect nahi ho payi boss."


def format_ip_reply() -> str:
    from Backend.Language import ui_message
    ip_block = get_local_ip_text()
    return ui_message("ip_header", body=ip_block)


def capture_screen_png() -> str | None:
    try:
        from PIL import ImageGrab
        os.makedirs(_DATA, exist_ok=True)
        path = os.path.abspath(os.path.join(_DATA, "live_screen.png"))
        img = ImageGrab.grab(all_screens=True)
        img.save(path, format="PNG")
        return path
    except Exception as e:
        print(f"Screen capture: {e}")
        return None


def _screen_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def describe_screen_with_vision(query: str, on_chunk: Callable[[str], None] | None = None) -> str:
    """Gemini/OpenRouter vision — kya screen pe dikh raha hai."""
    path = capture_screen_png()
    if not path:
        from Backend.Language import ui_message
        return ui_message("screen_fail")

    try:
        from Backend.LLM import vision_describe
        return vision_describe(
            query or "Screen pe kya dikh raha hai — Roman Hinglish mein short batao.",
            path,
            on_chunk=on_chunk,
        )
    except Exception as e:
        print(f"Vision: {e}")
        active = get_active_window_title()
        wins = ", ".join(get_open_window_titles(6))
        from Backend.Language import is_english_ui
        if is_english_ui():
            return (
                f"Vision unavailable. Active window: {active}. "
                f"Open windows: {wins}."
            )
        return (
            f"Vision API abhi nahi chali. Active window: {active}. "
            f"Open windows: {wins}."
        )


def build_live_context(query: str = "", include_vision: bool = False) -> str:
    active = get_active_window_title()
    windows = get_open_window_titles(8)
    win_line = ", ".join(windows) if windows else "(none)"
    parts = [
        f"ACTIVE_WINDOW: {active}",
        f"OPEN_WINDOWS: {win_line}",
    ]
    if wants_ip_in_context(query):
        parts.append(f"LOCAL_IP:\n{get_local_ip_text()}")
    if include_vision:
        desc = describe_screen_with_vision(query)
        parts.append(f"SCREEN_VISION:\n{desc[:2000]}")
    return "\n".join(parts)


def wants_ip_in_context(query: str) -> bool:
    from Backend.QueryNormalize import wants_ip_info, latin_hint
    h = latin_hint(query)
    return wants_ip_info(query) or "ip" in h


def handle_direct_query(query: str) -> str | None:
    """Instant PC actions / answers — IP, window control, apps, screen."""
    from Backend.QueryNormalize import latin_hint, wants_ip_info, wants_screen_read
    from Backend.SystemControl import open_chrome_simple
    from Backend.WindowsControl import (
        minimize_window,
        extract_window_target,
        shutdown_system,
        lock_workstation,
        open_youtube,
        cancel_shutdown,
    )

    h = latin_hint(query)

    if wants_ip_info(query):
        return format_ip_reply()

    if "minimize" in h or "minimise" in h:
        ok, msg = minimize_window(extract_window_target(query))
        return msg

    if "shutdown" in h and "cancel" not in h:
        ok, msg = shutdown_system(restart=False)
        return msg

    if "restart" in h or "reboot" in h:
        ok, msg = shutdown_system(restart=True)
        return msg

    if "cancel" in h and "shutdown" in h:
        ok, msg = cancel_shutdown()
        return msg

    if "lock" in h and "unlock" not in h:
        ok, msg = lock_workstation()
        return msg

    if "youtube" in h and any(
        w in h for w in ("open", "kholo", "start", "chalao", "karo", "launch")
    ):
        ok, msg = open_youtube()
        return msg

    if wants_screen_read(query):
        return describe_screen_with_vision(query)

    if any(w in h for w in ("browser", "chrome")) and any(
        w in h for w in ("open", "kholo", "start", "chalao", "karo", "launch")
    ):
        return open_chrome_simple()

    if "cmd" in h and any(w in h for w in ("kholo", "open", "start", "chalao", "karo")):
        try:
            subprocess.Popen(["cmd.exe"], creationflags=CREATE_NO_WINDOW)
            from Backend.Language import ui_message
            return ui_message("cmd_open")
        except Exception as e:
            return f"CMD open fail: {e}"

    if re.search(r"powershell", h) and any(w in h for w in ("kholo", "open", "start")):
        from Backend.SystemControl import handle_powershell
        return handle_powershell("Start-Process powershell")

    return None
