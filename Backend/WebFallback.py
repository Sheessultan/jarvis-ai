"""Web search when MongoDB / chat history has no useful answer."""

import re
from Backend.config import WEB_SEARCH_FALLBACK
from Backend.WebSearchProvider import is_web_worthy

_FACTUAL = (
    "what is", "what's", "who is", "who's", "when did", "where is", "how much",
    "how many", "latest", "news", "khabar", "price", "weather", "mausam",
    "temperature", "score", "match", "ipl", "cricket", "stock", "define",
    "meaning", "kya hai", "kaun hai", "kab hai", "kahan hai", "kitne",
    "aaj ka", "abhi ka", "current", "today", "update", "release", "version",
    "search", "dhundo", "google", "web", "internet", "batao", "batado",
    "24 ghante", "live", "2024", "2025", "2026",
)

_UNKNOWN = (
    "don't know", "do not know", "not sure", "no information", "cannot find",
    "can't find", "unable to find", "don't have", "do not have", "no data",
    "not in my", "nahi pata", "maloom nahi", "nahi mila", "pata nahi",
    "mujhe nahi", "main nahi janta", "no access", "search needed",
    "check online", "web search", "internet pe", "google karo",
)


def answer_indicates_unknown(text: str) -> bool:
    if not text:
        return True
    low = text.lower()
    return any(p in low for p in _UNKNOWN)


def _word_overlap(query: str, history: list) -> int:
    qw = set(re.findall(r"[a-z0-9]+", query.lower()))
    qw -= {"the", "a", "an", "is", "are", "ka", "ki", "ke", "ko", "se", "me", "hai", "kya"}
    if len(qw) < 2:
        return 0
    score = 0
    for msg in history[-12:]:
        if msg.get("role") != "assistant":
            continue
        aw = set(re.findall(r"[a-z0-9]+", (msg.get("content") or "").lower()))
        score = max(score, len(qw & aw))
    return score


def should_search_web(query: str, history: list, answer: str = None) -> bool:
    if not WEB_SEARCH_FALLBACK or not query.strip():
        return False
    if not is_web_worthy(query):
        return False

    q = query.lower()
    factual = any(k in q for k in _FACTUAL) or "?" in query
    search_intent = any(
        x in q
        for x in ("search", "news", "khabar", "ipl", "match", "weather", "latest", "google", "web")
    ) or ("batao" in q and len(q.split()) >= 3)

    if answer and answer_indicates_unknown(answer):
        return True

    if not factual and not search_intent:
        return False

    # Almost empty chat history → no DB knowledge yet
    if len(history) <= 2:
        return True

    if _word_overlap(query, history) < 2:
        return True

    return False


def web_search_notice(lang: str) -> str:
    from Backend.Language import normalize_language
    lang = normalize_language(lang)
    notices = {
        "hi": "यह जानकारी डेटाबेस में नहीं थी, मैंने वेब पर खोजा:",
        "ur": "یہ ڈیٹا بیس میں نہیں تھا، میں نے ویب پر تلاش کی:",
        "roman": "Boss, ye cheez database me nahi thi — maine web search ki:",
        "en": "Not in memory — I searched the web:",
    }
    return notices.get(lang, notices["roman"])
