"""Performance & model settings from .env"""

from dotenv import dotenv_values

env = dotenv_values(".env")


def _clean(v, default=""):
    if not v:
        return default
    return str(v).strip().strip('"').strip("'")


def _bool(key: str, default: bool = True) -> bool:
    return _clean(env.get(key), str(default)).lower() in ("1", "true", "yes")


FAST_MODE = _bool("FastMode", True)
LLM_MAX_TOKENS = int(_clean(env.get("LLMMaxTokens")) or ("220" if FAST_MODE else "380"))
LLM_CONTEXT = int(_clean(env.get("LLMContext")) or ("10" if FAST_MODE else "16"))
SEARCH_MAX_TOKENS = int(_clean(env.get("SearchMaxTokens")) or ("280" if FAST_MODE else "450"))
SKIP_TTS_LONG = _bool("SkipTTSLong", False)
TTS_FULL_ANSWER = _bool("TTSFullAnswer", True)
TTS_CHUNK_CHARS = int(_clean(env.get("TTSChunkChars")) or "450")
TTS_RATE = _clean(env.get("TTSRate")) or ("+42%" if FAST_MODE else "+32%")
TTS_RATE_ROMAN = _clean(env.get("TTSRateRoman")) or "+18%"
WEB_SEARCH_FALLBACK = _bool("WebSearchFallback", True)
# DDG uses Bing — often DNS-blocked; keep false, use Wikipedia + News RSS
WEB_USE_DDGS = _bool("WebUseDDGS", False)

# NewsAPI.org — supports newsapikey, NewsAPIKey, NEWS_API_KEY in .env
NEWS_API_KEY = (
    _clean(env.get("NewsAPIKey"))
    or _clean(env.get("newsapikey"))
    or _clean(env.get("NEWS_API_KEY"))
)
USE_NEWS_API = _bool("UseNewsAPI", bool(NEWS_API_KEY))
NEWS_API_COUNTRY = _clean(env.get("NewsAPICountry")) or "in"

# en | roman | hi | ur — replies + display language
DEFAULT_LANGUAGE = _clean(env.get("DefaultLanguage")) or "en"
DISPLAY_LANGUAGE = _clean(env.get("DisplayLanguage")) or DEFAULT_LANGUAGE
DISABLE_ENGLISH = _bool("DisableEnglish", False)
UI_ENGLISH = _bool("UIEnglish", DISPLAY_LANGUAGE == "en")
STT_LOCALE_OVERRIDE = _clean(env.get("STTLocale")) or ""
HUMAN_MODE = _bool("HumanMode", True)
AUTO_EXECUTE = _bool("AutoExecute", True)
# Dangerous: shutdown/restart — needs Admin + explicit .env flag
ALLOW_SHUTDOWN = _bool("AllowShutdown", False)
SHUTDOWN_DELAY_SEC = int(_clean(env.get("ShutdownDelaySec")) or "60")
