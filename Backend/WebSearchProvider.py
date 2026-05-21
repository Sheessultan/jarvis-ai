"""
Web search for Nexus — Wikipedia + Google News RSS (no Bing/DDG scrape).
DDG text search is optional (often blocked by DNS on some networks).
"""

from __future__ import annotations

import re
import warnings
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from Backend.config import WEB_USE_DDGS, NEWS_API_KEY, USE_NEWS_API, NEWS_API_COUNTRY

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _USER_AGENT}

_DDGS_DISABLED = False  # auto-off after DNS failure

_NEWS_HINTS = (
    "news", "khabar", "headline", "latest", "breaking", "aaj ka",
    "24 ghante", "ghante ka", "update", "ipl", "cricket", "match",
)

_STRIP_PATTERNS = (
    r"\b(search karke|search kar|web search|google par|internet pe|online search|dhundo|find)\b",
    r"\b(mujhe|chahiye|please|boss|jarvis|nexus|intelligence)\b",
    r"\b(tum|aap|kya|hai|ho|hain)\b",
    r"\b(batao|batado|bata do|bata dena|sunao|bolo)\b",
)

_SKIP_WEB = (
    "favourite", "favorite", "pasand", "database", "data waste", "memory",
    "db se", "mongo", "pura jawab", "padhkar", "padh kar", "read full",
    "sunao pura", "tum kaun", "tumhe kaun banaya", "who are you",
    "who made you", "kaun ho", "exit", "so jao",
)

_TOPIC_MAP = {
    "react": "React (software) JavaScript UI library Meta",
    "node": "Node.js JavaScript runtime",
    "python": "Python programming language",
    "javascript": "JavaScript programming language",
}

_STATE_NAMES = {
    "tamilnadu": "Tamil Nadu",
    "tamil nadu": "Tamil Nadu",
    "uttar pradesh": "Uttar Pradesh",
    "madhya pradesh": "Madhya Pradesh",
    "west bengal": "West Bengal",
    "andhra pradesh": "Andhra Pradesh",
    "himachal pradesh": "Himachal Pradesh",
    "jammu kashmir": "Jammu and Kashmir",
    "delhi": "Delhi",
    "mumbai": "Maharashtra",
    "punjab": "Punjab",
    "gujarat": "Gujarat",
    "rajasthan": "Rajasthan",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "bihar": "Bihar",
    "odisha": "Odisha",
    "assam": "Assam",
}


def clean_search_query(prompt: str) -> str:
    t = (prompt or "").strip()
    for pat in _STRIP_PATTERNS:
        t = re.sub(pat, " ", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" .,?")
    return t if len(t) >= 3 else (prompt or "").strip()


def _normalize_state(text: str) -> str | None:
    low = text.lower()
    for key, name in _STATE_NAMES.items():
        if key in low:
            return name
    return None


def is_web_worthy(query: str) -> bool:
    """Should this question use web/Wikipedia search?"""
    low = (query or "").lower().strip()
    if len(low) < 4:
        return False
    if any(s in low for s in _SKIP_WEB):
        return False
    if re.search(r"kaun\s*sa", low):
        return False

    signals = (
        "search", "google", "web", "internet", "news", "khabar", "weather", "mausam",
        "ipl", "cricket", "match", "score", "latest", "price", "cm", "pm",
        "kya hai", "what is", "who is", "kaun hai", "bare mein", "baare mein",
        "ke bare", "about", "framework", "library", "technology", "define",
        "24 ghante", "aaj ka", "current", "chief minister",
    )
    return any(s in low for s in signals)


def enrich_english_query(query: str) -> str:
    """Roman/Hindi → English search string for Wikipedia/RSS."""
    q = clean_search_query(query)
    low = q.lower()

    if not is_web_worthy(query):
        return q

    for key, eng in _TOPIC_MAP.items():
        if key in low:
            return eng

    if "bare mein" in low or "baare mein" in low or "ke bare" in low:
        topic = re.sub(
            r"\b(ke|ki|baare|bare|mein|kuchh|kuch|batao|framework|tell|explain)\b",
            " ",
            low,
            flags=re.I,
        )
        topic = re.sub(r"\s+", " ", topic).strip()
        if len(topic) >= 2:
            return f"{topic.title()} overview"

    state = _normalize_state(low)
    is_cm = bool(re.search(r"\bcm\b|chief\s*minister|mukhyamantri", low))
    is_pm = bool(re.search(r"\bpm\b|prime\s*minister|pradhan\s*mantri", low))

    if is_cm and state:
        return f"List of chief ministers of {state} current 2026"
    if is_cm:
        return f"Chief Minister of {state or 'Tamil Nadu'} current"

    if is_pm:
        return "Prime Minister of India current 2026"

    if re.search(r"kaun\s*hai\b|who\s+is\b", low) and not re.search(r"kaun\s*sa", low):
        topic = re.sub(
            r"\b(kaun|hai|ka|ke|ki|who|is|kya)\b", " ", low, flags=re.I
        )
        topic = re.sub(r"\s+", " ", topic).strip()
        if state:
            return f"{state} chief minister current"
        if topic and len(topic) > 2:
            return f"{topic.title()} current role"

    extras = []
    if "24" in low and "ghante" in low:
        extras.append("latest news India last 24 hours")
    if "aaj" in low:
        extras.append("today India")
    if "ipl" in low:
        extras.append("IPL cricket 2026 schedule")
    if "weather" in low or "mausam" in low:
        extras.append("weather forecast India")
    if extras:
        return f"{q} {' '.join(extras)}".strip()
    return q


def is_news_style_query(query: str) -> bool:
    low = (query or "").lower()
    return any(h in low for h in _NEWS_HINTS)


def _newsapi_search(query: str, max_items: int = 6) -> str:
    """NewsAPI.org — primary news source when API key is set."""
    if not USE_NEWS_API or not NEWS_API_KEY:
        return ""

    try:
        params = {
            "apiKey": NEWS_API_KEY,
            "pageSize": min(max_items, 10),
            "language": "en",
            "sortBy": "publishedAt",
        }

        if is_news_style_query(query):
            params["q"] = query
            url = "https://newsapi.org/v2/everything"
        else:
            params["q"] = query
            url = "https://newsapi.org/v2/everything"

        r = requests.get(url, params=params, headers=_HEADERS, timeout=15)
        if r.status_code == 401:
            print("NewsAPI: invalid API key — check NewsAPIKey in .env")
            return ""
        if r.status_code == 429:
            print("NewsAPI: rate limit — try later or upgrade plan")
            return ""
        r.raise_for_status()

        articles = r.json().get("articles") or []
        if not articles and is_news_style_query(query):
            r2 = requests.get(
                "https://newsapi.org/v2/top-headlines",
                params={
                    "apiKey": NEWS_API_KEY,
                    "country": NEWS_API_COUNTRY,
                    "q": query.split()[0] if query.split() else query,
                    "pageSize": min(max_items, 10),
                },
                headers=_HEADERS,
                timeout=15,
            )
            if r2.ok:
                articles = r2.json().get("articles") or []

        lines = []
        for art in articles[:max_items]:
            title = (art.get("title") or "").strip()
            desc = (art.get("description") or art.get("content") or "").strip()
            desc = re.sub(r"<[^>]+>", "", desc)[:320]
            source = (art.get("source") or {}).get("name") or ""
            published = (art.get("publishedAt") or "")[:10]
            link = (art.get("url") or "").strip()
            if not title:
                continue
            block = f"• {title}"
            if source or published:
                block += f" ({source} {published})".strip()
            if desc:
                block += f"\n  {desc}"
            if link:
                block += f"\n  {link}"
            lines.append(block)

        if lines:
            print(f"NewsAPI: {len(lines)} articles")
        return "\n".join(lines)
    except Exception as e:
        print(f"NewsAPI: {e}")
        return ""


def _google_news_rss(query: str, max_items: int = 6) -> str:
    try:
        enc = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={enc}&hl=en-IN&gl=IN&ceid=IN:en"
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        lines = []
        for item in root.findall(".//item")[:max_items]:
            title = (item.findtext("title") or "").strip()
            desc = re.sub(r"<[^>]+>", "", (item.findtext("description") or ""))[:300]
            pub = (item.findtext("pubDate") or "").strip()
            if title:
                block = f"• {title}"
                if pub:
                    block += f" ({pub})"
                if desc:
                    block += f"\n  {desc}"
                lines.append(block)
        return "\n".join(lines)
    except Exception as e:
        print(f"Google News RSS: {e}")
        return ""


def _wikipedia_snippets(query: str, limit: int = 3) -> str:
    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": limit,
                "utf8": 1,
            },
            headers=_HEADERS,
            timeout=14,
        )
        r.raise_for_status()
        hits = r.json().get("query", {}).get("search", [])
        if not hits:
            return ""

        pageids = [str(h["pageid"]) for h in hits]
        r2 = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "pageids": "|".join(pageids),
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "format": "json",
            },
            headers=_HEADERS,
            timeout=14,
        )
        r2.raise_for_status()
        pages = r2.json().get("query", {}).get("pages", {})
        lines = []
        for page in pages.values():
            title = page.get("title", "")
            extract = (page.get("extract") or "").strip()
            if extract:
                extract = extract[:700] + ("…" if len(extract) > 700 else "")
                lines.append(f"• {title}\n  {extract}")
        return "\n".join(lines)
    except Exception as e:
        print(f"Wikipedia: {e}")
        return ""


def _ddgs_text(query: str, max_results: int = 4) -> list[dict]:
    global _DDGS_DISABLED
    if not WEB_USE_DDGS or _DDGS_DISABLED:
        return []

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            from duckduckgo_search import DDGS
        with DDGS(timeout=20) as ddgs:
            rows = list(ddgs.text(query, max_results=max_results, region="in-en"))
            return rows
    except Exception as e:
        err = str(e).lower()
        if "dns" in err or "connect" in err or "refused" in err or "unreachable" in err:
            _DDGS_DISABLED = True
            print("Web: DDG/Bing blocked on this network — using Wikipedia/RSS only.")
        else:
            print(f"Web: DDG skip ({e})")
    return []


def _format_text_results(rows: list[dict]) -> str:
    if not rows:
        return ""
    lines = []
    for i, row in enumerate(rows, 1):
        title = (row.get("title") or "").strip()
        body = (row.get("body") or "").strip()
        href = (row.get("href") or "").strip()
        block = f"{i}. {title}"
        if body:
            block += f"\n   {body}"
        if href:
            block += f"\n   {href}"
        lines.append(block)
    return "\n".join(lines)


def fetch_web_results(query: str, *, fast: bool = True) -> str:
    raw = (query or "").strip()
    if not is_web_worthy(raw):
        return "No web search needed for this question — use chat memory."

    q = enrich_english_query(raw)
    if not q:
        return "Search query was empty."

    print(f"Web search: {q}")
    n = 3 if fast else 5
    sections = []

    wiki = _wikipedia_snippets(q, limit=3)
    if wiki:
        sections.append(f"Wikipedia:\n{wiki}")

    if is_news_style_query(raw) or is_news_style_query(q):
        news = _newsapi_search(q, max_items=n + 3)
        if news:
            sections.append(f"Latest news (NewsAPI):\n{news}")
        else:
            rss = _google_news_rss(q, max_items=n + 2)
            if rss:
                sections.append(f"Latest news (RSS):\n{rss}")

    text_rows = _ddgs_text(q, max_results=n)
    text_txt = _format_text_results(text_rows)
    if text_txt:
        sections.append(f"Web results:\n{text_txt}")

    if sections:
        return "\n\n".join(sections)[:3500]

    return (
        f"Could not fetch web data for: {q}\n"
        "Check internet/DNS, or ask again."
    )
