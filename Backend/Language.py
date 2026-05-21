"""
Multilingual: Roman (Hinglish), Hindi, Urdu. English voice/replies disabled by default.
"""

import re
from dotenv import dotenv_values

env_vars = dotenv_values(".env")

try:
    from Backend.config import (
        DEFAULT_LANGUAGE,
        DISPLAY_LANGUAGE,
        DISABLE_ENGLISH,
        STT_LOCALE_OVERRIDE,
    )
except Exception:
    DEFAULT_LANGUAGE = "en"
    DISPLAY_LANGUAGE = "en"
    DISABLE_ENGLISH = False
    STT_LOCALE_OVERRIDE = ""

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_ARABIC = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")
_LATIN = re.compile(r"[A-Za-z]")

_ROMAN_HI = frozenset({
    "kya", "hai", "ho", "hain", "kaise", "kaisa", "main", "mujhe", "tum", "aap",
    "nahi", "nahin", "haan", "han", "bhai", "yaar", "kahan", "kab", "kyun", "kyu",
    "kaun", "kitna", "kitni", "chahiye", "karo", "karna", "bolo", "batao", "sunao",
    "theek", "thik", "accha", "acha", "bahut", "abhi", "kal", "aaj", "mat", "kar",
    "mera", "meri", "tera", "teri", "apka", "unka", "yeh", "ye", "woh", "wo",
    "kuch", "sab", "nhi", "pls", "please", "bata", "dekh", "chal", "ja", "aa",
})

# Mic (Chrome Web Speech): Roman Hinglish → en-IN; pure Hindi speech → hi-IN
_STT_LOCALES = {
    "auto": "en-IN",
    "roman": "en-IN",
    "hi": "hi-IN",
    "hindi": "hi-IN",
    "ur": "ur-PK",
    "urdu": "ur-PK",
    "en": "en-IN",
    "english": "en-IN",
}

# Hindi / Roman voices only — no en-US / en-IN English neural
TTS_VOICES = {
    "roman": "hi-IN-SwaraNeural",
    "hi": "hi-IN-SwaraNeural",
    "ur": "ur-PK-UzmaNeural",
    "en": "en-IN-NeerjaNeural",
}

LANG_LABELS = {
    "roman": "Roman / Hinglish",
    "hi": "Hindi",
    "ur": "Urdu",
    "en": "English",
}

_last_reply_lang = (
    DISPLAY_LANGUAGE
    if DISPLAY_LANGUAGE in TTS_VOICES
    else (DEFAULT_LANGUAGE if DEFAULT_LANGUAGE in TTS_VOICES else "en")
)


def normalize_language(lang: str) -> str:
    """Map English mode to Roman when disabled."""
    if not lang:
        return DEFAULT_LANGUAGE
    if DISABLE_ENGLISH and lang == "en":
        return "roman"
    if lang in TTS_VOICES:
        return lang
    return DEFAULT_LANGUAGE


def get_stt_locale() -> str:
    """Override with STTLocale in .env (e.g. en-IN or hi-IN)."""
    if STT_LOCALE_OVERRIDE:
        return STT_LOCALE_OVERRIDE
    explicit = (env_vars.get("STTLocale") or "").strip()
    if explicit:
        return explicit
    raw = (env_vars.get("InputLanguage") or DEFAULT_LANGUAGE or "en").strip().lower()
    if DISABLE_ENGLISH and raw in ("en", "english", "auto"):
        raw = "roman"
    return _STT_LOCALES.get(raw, "en-IN")


def get_display_language() -> str:
    return normalize_language(DISPLAY_LANGUAGE or DEFAULT_LANGUAGE)


def is_english_ui() -> bool:
    try:
        from Backend.config import UI_ENGLISH
        return UI_ENGLISH or get_display_language() == "en"
    except Exception:
        return get_display_language() == "en"


def detect_language(text: str) -> str:
    """Returns: roman | hi | ur (never English when DisableEnglish=true)."""
    if not text or not text.strip():
        return normalize_language(DEFAULT_LANGUAGE)

    t = text.strip()

    if _DEVANAGARI.search(t):
        return "hi"

    if _ARABIC.search(t):
        return "ur"

    if not _LATIN.search(t):
        return normalize_language(DEFAULT_LANGUAGE)

    words = set(re.findall(r"[a-zA-Z']+", t.lower()))
    if not words:
        return normalize_language(DEFAULT_LANGUAGE)

    if words & _ROMAN_HI:
        return "roman"

    casual = ("boss", "bhai", "yaar", "theek", "haan", "han", "nhi", "nahi", "ok")
    if words & set(casual):
        return "roman"

    if DEFAULT_LANGUAGE == "en" or DISPLAY_LANGUAGE == "en":
        return "en"

    if DISABLE_ENGLISH:
        return "roman"

    return "en"


def set_reply_language(lang: str) -> None:
    global _last_reply_lang
    _last_reply_lang = normalize_language(lang)


def get_reply_language() -> str:
    return normalize_language(_last_reply_lang)


def get_tts_voice(lang: str = None) -> str:
    lang = normalize_language(lang or get_reply_language())
    custom = env_vars.get(f"AssistantVoice_{lang}") or env_vars.get("AssistantVoice")
    if custom:
        v = custom.strip().strip('"').strip("'")
        if DISABLE_ENGLISH and ("en-US" in v or "en-GB" in v or "Neerja" in v or "Jenny" in v):
            return TTS_VOICES["roman"]
        return v
    return TTS_VOICES.get(lang, TTS_VOICES["roman"])


def language_instruction(lang: str) -> str:
    lang = normalize_language(lang)
    instructions = {
        "hi": "Reply ONLY in Hindi (Devanagari). Short, natural tone.",
        "ur": "Reply ONLY in Urdu (Arabic script). Short, natural tone.",
        "roman": (
            "Reply ONLY in Roman Hinglish (Latin letters). Indian casual tone. "
            "Use: haan, nahi, theek, boss, bhai, kya, kaise. "
            "Example: 'Haan boss, main abhi check karta hun.' "
            "NEVER use pure English sentences. NEVER use Devanagari or Urdu script."
        ),
        "en": (
            "Reply ONLY in clear English (for on-screen display). "
            "Friendly, concise, professional. No Hindi/Devanagari script. "
            "Use simple words the user can read on screen."
        ),
    }
    return instructions.get(lang, instructions.get("en", instructions["roman"]))


def ui_message(key: str, **kwargs) -> str:
    """User-facing system strings (English vs Roman)."""
    lang = get_display_language()
    table = {
        "ip_header": {
            "en": (
                "I checked your system IP:\n{body}\n"
                "This is your local Wi-Fi/LAN address on your router network."
            ),
            "roman": (
                "Boss, maine tumhare system ki IP check kar li:\n{body}\n"
                "Ye tumhari local/Wi-Fi IP hai — router pe bhi same subnet dikhega."
            ),
        },
        "action_ok": {
            "en": "Done. I ran this on your PC:\n{body}",
            "roman": "Haan boss, maine khud system pe kar diya:\n{body}",
        },
        "action_fail": {
            "en": "Some commands failed:\n{body}",
            "roman": "Boss, command fail ho gayi:\n{body}",
        },
        "youtube_open": {
            "en": "YouTube opened in Chrome.",
            "roman": "YouTube Chrome me khul gaya boss.",
        },
        "chrome_open": {
            "en": "Chrome browser opened.",
            "roman": "Chrome open ho gaya boss.",
        },
        "cmd_open": {
            "en": "Command Prompt opened.",
            "roman": "Boss, Command Prompt maine khud open kar diya.",
        },
        "screen_fail": {
            "en": "Screen capture failed.",
            "roman": "Screen capture fail ho gaya boss.",
        },
    }
    entry = table.get(key, {})
    template = entry.get(lang) or entry.get("en") or entry.get("roman") or key
    return template.format(**kwargs)


def build_system_prompt(assistant_name: str, username: str, lang: str, extra: str = "") -> str:
    lang = normalize_language(lang)
    try:
        from Backend.config import FAST_MODE, HUMAN_MODE
        from Backend.AssistantCapabilities import get_capabilities_prompt

        if HUMAN_MODE:
            short_rule = "2-5 sentences, natural human flow."
        elif FAST_MODE:
            short_rule = "1-2 sentences max."
        else:
            short_rule = "Short answers (1-4 sentences)."
        caps = get_capabilities_prompt(username)
    except Exception:
        short_rule = "Short answers."
        caps = ""

    base = (
        f"You are {assistant_name}, personal AI for {username} on Windows. "
        f"{language_instruction(lang)} {short_rule} "
        f"{caps}"
    )
    if extra:
        base += f"\n{extra}"
    return base


def prepare_query(text: str, lang: str = None) -> str:
    text = text.strip()
    if not text:
        return ""
    lang = normalize_language(lang or detect_language(text))
    if lang in ("hi", "ur", "roman"):
        return text
    return text


def query_for_dmm(text: str) -> str:
    return text.strip()


def dmm_keywords(text: str) -> str:
    try:
        from Backend.QueryNormalize import latin_hint
        return latin_hint(text)
    except Exception:
        return text.lower()


def multilingual_exit_notice(lang: str) -> str:
    lang = normalize_language(lang)
    notices = {
        "hi": "ठीक है, अलविदा!",
        "ur": "ٹھیک ہے، خدا حافظ!",
        "roman": "Theek hai boss, alvida!",
        "en": "Goodbye. Shutting down.",
    }
    return notices.get(lang, notices.get("en", notices["roman"]))


def tts_screen_notice(lang: str) -> list:
    lang = normalize_language(lang)
    notices = {
        "hi": ["पूरा जवाब स्क्रीन पर है।", "बाकी चैट में देखिए।"],
        "ur": ["مکمل جواب اسکرین پر ہے۔", "باقی چیٹ میں دیکھیں۔"],
        "roman": ["Poora jawab screen pe hai.", "Baaki chat mein dekho."],
        "en": ["Full answer is on screen.", "See the chat panel for details."],
    }
    return notices.get(lang, notices.get("en", notices["roman"]))
