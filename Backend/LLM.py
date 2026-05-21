"""
Unified LLM — Groq + OpenRouter (OR).
AIProvider: groq | openrouter | openai | auto
"""

import os

from dotenv import dotenv_values

env_vars = dotenv_values(".env")


def _clean(value) -> str:
    if not value:
        return ""
    return str(value).strip().strip('"').strip("'")


def _bool(key: str, default: bool = False) -> bool:
    v = env_vars.get(key)
    if v is None or not str(v).strip():
        return default
    return _clean(v).lower() in ("1", "true", "yes")


GroqAPIKey = _clean(env_vars.get("GroqAPIKey"))
OpenAIAPIKey = _clean(env_vars.get("OpenAIAPIKey"))
OpenRouterAPIKey = _clean(env_vars.get("OpenRouterAPIKey")) or OpenAIAPIKey
AIProvider = _clean(env_vars.get("AIProvider", "auto")).lower()

LLAMA4_GROQ = _clean(env_vars.get("Llama4GroqModel")) or "meta-llama/llama-4-scout-17b-16e-instruct"
LLAMA4_OPENROUTER = _clean(env_vars.get("Llama4OpenRouterModel")) or "meta-llama/llama-4-maverick"
_use_llama4 = _bool("UseLlama4", False)

GroqModel = _clean(env_vars.get("GroqModel")) or (
    LLAMA4_GROQ if _use_llama4 else "llama-3.1-8b-instant"
)
OpenRouterModel = _clean(env_vars.get("OpenRouterModel")) or _clean(env_vars.get("OpenAIModel"))
OpenAIBaseURL = _clean(env_vars.get("OpenAIBaseURL"))
OPENROUTER_BASE = _clean(env_vars.get("OpenRouterBaseURL")) or "https://openrouter.ai/api/v1"
GROQ_FALLBACK_TO_OR = _bool("GroqFallbackOpenRouter", True)

_groq_client = None
_openrouter_client = None
_active_provider = None


def _is_openrouter_key(key: str) -> bool:
    return bool(key) and key.startswith("sk-or-")


def is_llama4_enabled() -> bool:
    return _use_llama4


def _openrouter_model() -> str:
    if OpenRouterModel:
        return OpenRouterModel
    if _use_llama4:
        return LLAMA4_OPENROUTER
    return "meta-llama/llama-4-maverick"


def _openai_native_model() -> str:
    m = _clean(env_vars.get("OpenAIModel"))
    return m or "gpt-4o-mini"


def resolve_provider() -> str:
    """Returns: groq | openrouter | openai"""
    global _active_provider
    if _active_provider:
        return _active_provider

    prov = AIProvider
    if prov in ("or", "openrouter"):
        prov = "openrouter"
    elif prov == "openai" and _is_openrouter_key(OpenRouterAPIKey):
        prov = "openrouter"

    if prov == "groq":
        if not GroqAPIKey:
            raise ValueError("AIProvider=groq but GroqAPIKey missing in .env")
        _active_provider = "groq"
    elif prov == "openrouter":
        if not OpenRouterAPIKey:
            raise ValueError("OpenRouterAPIKey / OpenAIAPIKey (sk-or-v1) missing in .env")
        _active_provider = "openrouter"
    elif prov == "openai":
        if not OpenAIAPIKey:
            raise ValueError("AIProvider=openai but OpenAIAPIKey missing in .env")
        _active_provider = "openai"
    else:
        if GroqAPIKey:
            _active_provider = "groq"
        elif OpenRouterAPIKey and _is_openrouter_key(OpenRouterAPIKey):
            _active_provider = "openrouter"
        elif OpenAIAPIKey:
            _active_provider = "openai"
        else:
            raise ValueError("No GroqAPIKey or OpenRouterAPIKey in .env")

    return _active_provider


def get_provider() -> str:
    return resolve_provider()


def get_model() -> str:
    p = resolve_provider()
    if p == "groq":
        return GroqModel
    if p == "openrouter":
        return _openrouter_model()
    return _openai_native_model()


def provider_label() -> str:
    return resolve_provider()


def _get_groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=GroqAPIKey)
    return _groq_client


def _get_openrouter():
    global _openrouter_client
    if _openrouter_client is None:
        from openai import OpenAI
        base = OpenAIBaseURL if OpenAIBaseURL and "openrouter" in OpenAIBaseURL else OPENROUTER_BASE
        _openrouter_client = OpenAI(api_key=OpenRouterAPIKey, base_url=base)
    return _openrouter_client


def _get_openai_native():
    from openai import OpenAI
    return OpenAI(api_key=OpenAIAPIKey)


_logged_model = False


def _stream_openrouter(messages, model, max_tokens, temperature, top_p, on_chunk) -> str:
    extra = {}
    if _is_openrouter_key(OpenRouterAPIKey):
        extra["extra_headers"] = {
            "HTTP-Referer": "https://github.com/nexus-intelligence",
            "X-Title": "Nexus Intelligence",
        }
    completion = _get_openrouter().chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        stream=True,
        **extra,
    )
    parts = []
    for chunk in completion:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if not delta:
            continue
        parts.append(delta)
        if on_chunk:
            on_chunk("".join(parts))
    return "".join(parts)


def stream_chat(
    messages: list,
    max_tokens: int = 380,
    temperature: float = 0.45,
    top_p: float = 0.9,
    on_chunk=None,
) -> str:
    global _logged_model, _active_provider
    model = get_model()
    prov = resolve_provider()
    if not _logged_model:
        tag = "Llama 4" if _use_llama4 else "AI"
        print(f"{tag}: {prov} / {model}")
        _logged_model = True

    try:
        if prov == "groq":
            parts = []
            completion = _get_groq().chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stream=True,
            )
            for chunk in completion:
                delta = chunk.choices[0].delta.content
                if not delta:
                    continue
                parts.append(delta)
                if on_chunk:
                    on_chunk("".join(parts))
            return "".join(parts).replace("</s>", "").strip()

        if prov == "openrouter":
            return _stream_openrouter(
                messages, model, max_tokens, temperature, top_p, on_chunk
            ).replace("</s>", "").strip()

        completion = _get_openai_native().chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stream=True,
        )
        parts = []
        for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                parts.append(delta)
                if on_chunk:
                    on_chunk("".join(parts))
        return "".join(parts).replace("</s>", "").strip()

    except Exception as e:
        if prov == "groq" and GROQ_FALLBACK_TO_OR and OpenRouterAPIKey:
            print(f"Groq error ({e}) — switching to OpenRouter...")
            _active_provider = "openrouter"
            or_model = _openrouter_model()
            print(f"AI: openrouter / {or_model}")
            return _stream_openrouter(
                messages, or_model, max_tokens, temperature, top_p, on_chunk
            ).replace("</s>", "").strip()
        raise


def chat(
    messages: list,
    max_tokens: int = 380,
    temperature: float = 0.45,
    top_p: float = 0.9,
) -> str:
    return stream_chat(
        messages, max_tokens=max_tokens, temperature=temperature, top_p=top_p
    )


def vision_describe(
    query: str,
    image_path: str,
    on_chunk=None,
    max_tokens: int = 420,
) -> str:
    """Screen image → Roman Hinglish description (OpenRouter/Gemini vision)."""
    import base64

    if not os.path.isfile(image_path):
        return "Screen image nahi mili."

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    model = _openrouter_model()
    if "gemini" not in model.lower() and "gpt-4" not in model.lower():
        model = "google/gemini-2.0-flash-001"

    user_content = [
        {
            "type": "text",
            "text": (
                f"{query}\n\n"
                "Screen capture dekho. Roman Hinglish mein batao: "
                "kaun sa app/window, kya text/buttons dikh rahe hain, user kya kar sakta hai."
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        },
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "You see the user's Windows screen. "
                "Reply only in clear English, concise, for on-screen display."
            ),
        },
        {"role": "user", "content": user_content},
    ]

    prov = resolve_provider()
    if prov == "openrouter":
        return _stream_openrouter(
            messages, model, max_tokens, 0.35, 0.9, on_chunk
        ).strip() or "Screen samajh nahi aayi."

    # Groq / others: text-only fallback
    return stream_chat(
        [
            {
                "role": "system",
                "content": "No vision on this provider. Say you need OpenRouter + Gemini for screen read.",
            },
            {"role": "user", "content": query},
        ],
        max_tokens=120,
        on_chunk=on_chunk,
    )
