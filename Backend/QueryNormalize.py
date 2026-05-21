"""
Hindi/Devanagari voice → Latin hints for routing & PC actions.
"""

from __future__ import annotations

import re

# Devanagari / mixed → Latin tokens for matching
_REPLACEMENTS = (
    ("आईपी", " ip "),
    ("आइपी", " ip "),
    ("आई पी", " ip "),
    ("ब्राउज़र", " browser "),
    ("ब्राउजर", " browser "),
    ("ब्राउज", " browser "),
    ("ओपन", " open "),
    ("खोलो", " kholo "),
    ("खोल", " kholo "),
    ("चलाओ", " chalao "),
    ("चला", " chalao "),
    ("करो", " karo "),
    ("कर", " karo "),
    ("बताओ", " batao "),
    ("बता", " batao "),
    ("बंद", " band "),
    ("कमांडर", " cmd "),
    ("कमांड", " cmd "),
    ("पढ़कर", " padhkar "),
    ("पढ़", " padh "),
    ("पढ", " padh "),
    ("स्क्रीन", " screen "),
    ("डिस्प्ले", " display "),
    ("डिस्पले", " display "),
    ("सिस्टम", " system "),
    ("कंप्यूटर", " computer "),
    ("पीसी", " pc "),
    ("गूगल", " google "),
    ("यूट्यूब", " youtube "),
    ("युटुब", " youtube "),
    ("मिनिमाइज", " minimize "),
    ("मिनिमाइज़", " minimize "),
    ("शटडाउन", " shutdown "),
    ("शट डाउन", " shutdown "),
    ("रिस्टार्ट", " restart "),
    ("विंडो", " window "),
    ("नेक्सस", " nexus "),
    ("इंटेलिजेंस", " intelligence "),
    ("इन्टेलिजेंस", " intelligence "),
    ("लॉक", " lock "),
    ("बंद करो", " band karo "),
    ("बंद कर दो", " band kar do "),
    ("नोटपैड", " notepad "),
    ("क्रोम", " chrome "),
    ("ईमेल", " email "),
    ("मेल", " mail "),
    ("फोल्डर", " folder "),
    ("फाइल", " file "),
    ("वॉल्यूम", " volume "),
    ("म्यूट", " mute "),
    ("सर्च", " search "),
    ("धुंधो", " dhundo "),
    ("ढूंढ", " dhundo "),
    ("दिखाओ", " dikhao "),
    ("देख", " dekh "),
    ("लाइव", " live "),
    ("चल", " chal "),
    ("हैलो", " hello "),
    ("हेलो", " hello "),
)

_ACTION_LATIN = (
    "karo", "kholo", "chalao", "run", "open", "close", "start", "launch", "band",
    "bhejo", "likho", "search", "dhundo", "check", "dikhao", "list", "execute",
    "chal", "dekh", "mute", "volume", "notepad", "chrome", "gmail", "mail",
    "powershell", "cmd", "folder", "file", "app", "website", "google", "youtube",
    "system", "pc", "computer", "browser", "ip", "padh", "padhkar", "screen",
    "display", "batao", "bata", "khud", "mera", "meri", "mere",
    "minimize", "minimise", "shutdown", "restart", "lock", "maximize",
)

_SCREEN_READ = (
    "padh", "padhkar", "padh ke", "screen", "display", "dikhao kya", "kya chal",
    "kya likha", "read screen", "dekh kya", "live display", "screen pe",
    "display pe", "kya dikh", "screen read",
)

_IP_HINTS = ("ip", "ipv4", "wifi ip", "network address", "local ip")

_IP_ASK = ("batao", "bata", "kya", "kitni", "kitna", "tell", "mera", "meri", "mere",
           "system", "address", "check", "dikhao", "hai", "hain")


def latin_hint(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    for src, dst in _REPLACEMENTS:
        t = t.replace(src, dst)
    # Keep Latin letters/digits; collapse spaces
    t = re.sub(r"\s+", " ", t, flags=re.UNICODE)
    return t.lower().strip()


def wants_ip_info(query: str) -> bool:
    h = latin_hint(query)
    if not any(x in h for x in _IP_HINTS):
        if not re.search(r"आई\s*पी|ip", query, re.I):
            return False
    return any(x in h for x in _IP_ASK) or "system" in h or "mera" in h or "meri" in h


def wants_screen_read(query: str) -> bool:
    h = latin_hint(query)
    if any(w in h for w in _SCREEN_READ):
        return True
    return bool(re.search(r"पढ|स्क्रीन|डिस्प्ले|दिख", query))


def wants_pc_action_hint(query: str) -> bool:
    h = latin_hint(query)
    if len(h) < 2:
        return False
    if wants_ip_info(query) or wants_screen_read(query):
        return True
    return any(w in h for w in _ACTION_LATIN)
