"""
Auto-execute PC actions — Nexus khud chalati hai, user ko "khud chalao" nahi bolti.
"""

from __future__ import annotations

import re
import asyncio
from Backend.Automation import Automation, extract_open_target
from Backend.SystemControl import (
    handle_powershell,
    handle_cmd,
    handle_browser,
    handle_email,
    open_url,
)
from Backend.LLM import chat as llm_chat
from Backend.QueryNormalize import latin_hint, wants_pc_action_hint, wants_ip_info

_ACTION_WORDS = (
    "karo", "kholo", "chalao", "run", "open", "close", "start", "launch", "band",
    "bhejo", "likho", "search", "dhundo", "check", "dikhao", "list", "execute",
    "chal", "dekh", "mute", "volume", "notepad", "chrome", "gmail", "mail",
    "powershell", "cmd", "folder", "file", "app", "website", "google", "youtube",
    "khud", "mera", "system", "pc", "computer", "chal", "on karo", "off karo",
)

_CHAT_ONLY = (
    "kaise ho", "how are you", "who are you", "tum kaun", "kya kar sakte",
    "thank you", "shukriya", "alvida", "bye", "theek hai", "samajh gaya",
)

_REFUSE_PATTERNS = (
    "khud chalao", "khud run", "aap khud", "you need to", "i cannot",
    "i can't", "main nahi kar", "nahi kar sakti", "unable to",
    "not able to", "manually", "apne aap", "yourself",
)


def wants_pc_action(query: str) -> bool:
    if wants_pc_action_hint(query):
        return True
    low = latin_hint(query) or (query or "").lower().strip()
    if len(low) < 3:
        return False
    if any(p in low for p in _CHAT_ONLY):
        if not any(w in low for w in ("karo", "kholo", "open", "run", "search", "powershell", "cmd", "ip", "browser")):
            return False
    return any(w in low for w in _ACTION_WORDS)


def infer_commands(query: str) -> list[str]:
    """Voice → automation command lines (supports multiple actions)."""
    q = query.strip()
    low = latin_hint(q) or q.lower()
    cmds = []

    if wants_ip_info(query) or " ip " in f" {low} " or low.startswith("ip ") or " ip" in low:
        cmds.append(
            "powershell Get-NetIPAddress -AddressFamily IPv4 | "
            "Where-Object { $_.IPAddress -notlike '127.*' } | "
            "Select-Object IPAddress, InterfaceAlias | Format-Table -AutoSize"
        )

    if any(w in low for w in ("powershell", "power shell")):
        cmds.append(f"powershell {q}")

    if any(w in low for w in ("cmd", "command prompt")) and "powershell" not in low:
        cmds.append(f"cmd {q}")

    if any(w in low for w in ("email", "mail bhej", "gmail", "mail kholo", "mail likho")):
        cmds.append(f"email {q}")

    if any(w in low for w in ("volume mute", "mute karo", "awaz band")):
        cmds.append("system mute")
    if any(w in low for w in ("volume up", "awaz badha")):
        cmds.append("system volume up")
    if any(w in low for w in ("volume down", "awaz kam")):
        cmds.append("system volume down")

    if "youtube" in low and any(w in low for w in ("search", "dhundo")):
        cmds.append(f"youtube search {q}")
    elif "youtube" in low and any(w in low for w in ("kholo", "open", "chalao", "karo", "start", "launch")):
        cmds.append("open youtube")

    if "minimize" in low or "minimise" in low:
        from Backend.WindowsControl import extract_window_target
        tgt = extract_window_target(q)
        cmds.append(f"system minimize {tgt}".strip())

    if "shutdown" in low and "cancel" not in low:
        cmds.append("system shutdown")
    if "restart" in low or "reboot" in low:
        cmds.append("system restart")
    if "lock" in low and "unlock" not in low:
        cmds.append("system lock")

    if any(w in low for w in ("google", "search", "dhundo")) and "youtube" not in low:
        if "search" in low or "dhundo" in low:
            cmds.append(f"google search {q}")

    if any(w in low for w in ("close", "band karo", "band kro")):
        cmds.append(f"close {extract_open_target(q)}")

    if "chrome" in low and any(w in low for w in ("open", "kholo", "start", "launch", "chalu")):
        cmds.append("open chrome")
    elif any(w in low for w in ("notepad", "calculator", "spotify", "vscode", "settings")):
        for app in ("notepad", "calculator", "spotify", "vscode", "settings", "explorer"):
            if app in low:
                cmds.append(f"open {app}")
                break
    elif any(w in low for w in ("open", "start", "launch", "kholo", "chalu")):
        cmds.append(f"open {extract_open_target(q)}")

    if any(w in low for w in ("chrome", "browser", "website", "url")) and "open chrome" not in cmds:
        if any(w in low for w in ("kholo", "open", "jao", "le jao")):
            cmds.append(f"browser {q}")

    if any(w in low for w in ("folder list", "files dikhao", "directory", "file list", "dir")):
        cmds.append("powershell Get-ChildItem")
    if "ipconfig" in low:
        cmds.append("powershell ipconfig")
    if any(w in low for w in ("task", "process")) and any(w in low for w in ("list", "dikhao", "check")):
        cmds.append("powershell Get-Process | Select-Object -First 12 Name, Id, CPU")

    # dedupe
    seen = set()
    out = []
    for c in cmds:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _llm_infer_commands(query: str) -> list[str]:
    """Fast LLM parse when rules miss."""
    try:
        raw = llm_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Parse Windows voice command. Output ONLY action lines (no explanation).\n"
                        "Formats (one per line):\n"
                        "OPEN:chrome\n"
                        "POWERSHELL:Get-ChildItem\n"
                        "CMD:dir\n"
                        "BROWSER:https://google.com\n"
                        "EMAIL:user text\n"
                        "GOOGLE:search words\n"
                        "SYSTEM:mute\n"
                        "NONE\n"
                        "If user wants action you MUST output a command, not NONE."
                    ),
                },
                {"role": "user", "content": query},
            ],
            max_tokens=120,
            temperature=0.1,
        )
        return _parse_llm_actions(raw)
    except Exception as e:
        print(f"LLM action parse: {e}")
        return []


def _parse_llm_actions(text: str) -> list[str]:
    cmds = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.upper() == "NONE":
            continue
        up = line.upper()
        if up.startswith("OPEN:"):
            cmds.append(f"open {line[5:].strip()}")
        elif up.startswith("POWERSHELL:"):
            cmds.append(f"powershell {line[11:].strip()}")
        elif up.startswith("CMD:"):
            cmds.append(f"cmd {line[4:].strip()}")
        elif up.startswith("BROWSER:"):
            cmds.append(f"browser {line[8:].strip()}")
        elif up.startswith("EMAIL:"):
            cmds.append(f"email {line[6:].strip()}")
        elif up.startswith("GOOGLE:"):
            cmds.append(f"google search {line[7:].strip()}")
        elif up.startswith("SYSTEM:"):
            cmds.append(f"system {line[7:].strip()}")
    return cmds


def _run_one(cmd: str) -> str:
    cmd = cmd.strip()
    if cmd.startswith("system "):
        from Backend.WindowsControl import run_system_command
        ok, msg = run_system_command(cmd[7:].strip())
        return msg if ok else f"FAIL: {msg}"
    if cmd.startswith("powershell "):
        return handle_powershell(cmd[11:])
    if cmd.startswith("cmd "):
        return handle_cmd(cmd[4:])
    if cmd.startswith("email "):
        return handle_email(cmd[6:])
    if cmd.startswith("browser ") or cmd.startswith("chrome "):
        p = cmd.split(" ", 1)[1] if " " in cmd else ""
        return handle_browser(p)
    return ""


def _sync_prefixes():
    return ("powershell ", "cmd ", "email ", "browser ", "chrome ", "system ")


def execute_commands(commands: list[str]) -> str:
    """Run commands; return Roman summary for user."""
    if not commands:
        return ""

    results = []
    bg_cmds = []

    for cmd in commands:
        if not cmd.strip():
            continue
        print(f"AutoExecute: {cmd}")
        if any(cmd.startswith(p) for p in _sync_prefixes()):
            out = _run_one(cmd)
            if out:
                results.append(out)
        elif cmd.startswith("open ") or cmd.startswith("close ") or cmd.startswith("google"):
            bg_cmds.append(cmd)
        else:
            bg_cmds.append(cmd)

    ok_cmds: list[str] = []
    fail_cmds: list[str] = []

    if bg_cmds:
        try:
            outcomes = asyncio.run(Automation(bg_cmds))
            for cmd, ok in zip(bg_cmds, outcomes or []):
                if ok is True:
                    ok_cmds.append(cmd)
                    results.append(f"OK: {cmd}")
                else:
                    fail_cmds.append(cmd)
                    results.append(f"FAIL: {cmd}")
        except Exception as e:
            fail_cmds.extend(bg_cmds)
            results.append(f"Automation error: {e}")

    if not results:
        return ""

    from Backend.Language import ui_message

    summary = "\n".join(results)
    if len(summary) > 1200:
        summary = summary[:1200] + "..."
    if fail_cmds and not ok_cmds:
        return ui_message("action_fail", body=summary)
    if fail_cmds:
        return ui_message("action_fail", body=summary) + "\n" + ui_message("action_ok", body="")
    return ui_message("action_ok", body=summary)


def auto_execute_from_voice(query: str, decision: list[str] | None = None) -> tuple[str, list[str]]:
    """
    Returns (spoken_summary, command_list).
    Empty summary = nothing to execute.
    """
    try:
        from Backend.config import AUTO_EXECUTE
        if not AUTO_EXECUTE:
            return "", []
    except Exception:
        pass

    if not wants_pc_action(query):
        return "", []

    cmds = []
    if decision:
        for d in decision:
            d = d.strip()
            if not d.startswith("general") and not d.startswith("realtime"):
                if " " in d:
                    cmds.append(d)
                else:
                    pass

    if not cmds:
        cmds = infer_commands(query)

    if not cmds and wants_pc_action(query):
        cmds = _llm_infer_commands(query)

    if not cmds:
        return "", []

    summary = execute_commands(cmds)
    return summary, cmds


def sanitize_refusal(answer: str, query: str) -> str:
    """If AI refused to act, run automation instead."""
    if not answer:
        return answer
    low = answer.lower()
    if any(p in low for p in _REFUSE_PATTERNS) and wants_pc_action(query):
        done, _ = auto_execute_from_voice(query)
        if done:
            return done
    return answer
