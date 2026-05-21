"""
Windows system control — PowerShell, CMD, Chrome, Gmail, URLs.
"""

from __future__ import annotations

import os
import re
import subprocess
import urllib.parse
import webbrowser

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
]


def _chrome_exe() -> str | None:
    for p in _CHROME_PATHS:
        if os.path.isfile(p):
            return p
    return None


def extract_shell_text(query: str, shell: str) -> str:
    """Pull command text after powershell/cmd keywords."""
    q = query.strip()
    low = q.lower()
    for key in (f"{shell} ", f"{shell} se ", f"{shell} me ", f"run {shell} "):
        if key in low:
            idx = low.index(key.strip())
            return q[idx + len(key.strip()) :].strip()
    for key in (shell, "command prompt", "terminal"):
        if key in low:
            parts = re.split(rf"\b{key}\b", low, maxsplit=1, flags=re.I)
            if len(parts) > 1:
                return q[q.lower().find(parts[1]) :].strip() if parts[1] else q
    return q


def run_powershell(command: str, timeout: int = 45) -> str:
    command = command.strip()
    if not command:
        return "Boss, PowerShell command khali hai."
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if out:
            text = out[:2500]
            return f"PowerShell output:\n{text}"
        if err:
            return f"PowerShell error:\n{err[:800]}"
        return "PowerShell command complete ho gaya, koi output nahi aaya."
    except subprocess.TimeoutExpired:
        return "PowerShell time limit cross ho gaya boss, chhota command try karo."
    except Exception as e:
        return f"PowerShell fail: {e}"


def run_cmd(command: str, timeout: int = 45) -> str:
    command = command.strip()
    if not command:
        return "Boss, CMD command khali hai."
    try:
        r = subprocess.run(
            ["cmd", "/c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if out:
            return f"CMD output:\n{out[:2500]}"
        if err:
            return f"CMD error:\n{err[:800]}"
        return "CMD command complete ho gaya."
    except subprocess.TimeoutExpired:
        return "CMD time limit cross ho gaya."
    except Exception as e:
        return f"CMD fail: {e}"


def open_chrome_simple() -> str:
    chrome = _chrome_exe()
    if chrome:
        subprocess.Popen([chrome], creationflags=CREATE_NO_WINDOW)
        return "Chrome open ho gaya boss."
    webbrowser.open("https://www.google.com")
    return "Browser open ho gaya boss."


def open_url(url: str, use_chrome: bool = True) -> str:
    url = url.strip()
    if not url:
        return "URL khali hai."
    if not url.startswith(("http://", "https://")):
        if " " not in url and "." in url:
            url = "https://" + url
        else:
            url = "https://www.google.com/search?q=" + urllib.parse.quote(url)

    chrome = _chrome_exe()
    if use_chrome and chrome:
        subprocess.Popen([chrome, url], creationflags=CREATE_NO_WINDOW)
        return f"Chrome me khola: {url[:80]}"
    webbrowser.open(url)
    return f"Browser me khola: {url[:80]}"


def open_gmail_compose(to: str = "", subject: str = "", body: str = "") -> str:
    params = {"view": "cm", "fs": "1"}
    if to:
        params["to"] = to
    if subject:
        params["su"] = subject
    if body:
        params["body"] = body
    url = "https://mail.google.com/mail/?" + urllib.parse.urlencode(params)
    open_url(url, use_chrome=True)
    return (
        "Gmail compose khul gaya Chrome me. "
        "Ab check karke Send dabao boss."
        + (f" (To: {to})" if to else "")
    )


def parse_email_request(query: str) -> tuple[str, str, str]:
    """Best-effort parse to, subject, body from voice text."""
    to = ""
    subject = ""
    body = ""
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.\w+", query)
    if emails:
        to = emails[0]
    low = query.lower()
    if "subject" in low or "vishay" in low:
        m = re.search(r"(?:subject|vishay)\s*[:\-]?\s*(.+?)(?:body|message|$)", query, re.I)
        if m:
            subject = m.group(1).strip()[:120]
    if "body" in low or "message" in low:
        m = re.search(r"(?:body|message)\s*[:\-]?\s*(.+)$", query, re.I)
        if m:
            body = m.group(1).strip()[:500]
    if not body and to:
        body = query
    return to, subject, body


def handle_email(query: str) -> str:
    to, subject, body = parse_email_request(query)
    return open_gmail_compose(to, subject, body)


def handle_browser(query: str) -> str:
    q = query.lower()
    if "gmail" in q or "mail" in q or "email" in q:
        return handle_email(query)
    if "youtube" in q:
        return open_url("https://www.youtube.com")
    if "google" in q:
        return open_url("https://www.google.com")
    # extract URL-ish
    urls = re.findall(r"https?://\S+", query)
    if urls:
        return open_url(urls[0])
    # search phrase
    for prefix in ("chrome me kholo", "browser me", "website", "url", "kholo"):
        if prefix in q:
            rest = query[q.find(prefix) + len(prefix) :].strip()
            if rest:
                return open_url(rest)
    return open_url("https://www.google.com")


def handle_powershell(query: str) -> str:
    cmd = extract_shell_text(query, "powershell")
    # common voice mappings
    low = cmd.lower()
    if "folder list" in low or "dir" in low or "directory" in low:
        cmd = "Get-ChildItem"
    elif "ip address" in low or "ipconfig" in low:
        cmd = "ipconfig"
    elif "process" in low or "task" in low:
        cmd = "Get-Process | Select-Object -First 15 Name, CPU, WS"
    return run_powershell(cmd)


def handle_cmd(query: str) -> str:
    cmd = extract_shell_text(query, "cmd")
    low = cmd.lower()
    if "dir" in low or "folder" in low:
        cmd = "dir"
    return run_cmd(cmd)
