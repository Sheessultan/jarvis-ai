import datetime
from dotenv import dotenv_values
import os
from Backend.LLM import stream_chat, get_provider, get_model
from Backend.Language import (
    detect_language,
    set_reply_language,
    build_system_prompt,
    prepare_query,
)
from Backend.WebSearchProvider import fetch_web_results, is_web_worthy
from Backend import MongoDB as db
from Backend.config import FAST_MODE, SEARCH_MAX_TOKENS, LLM_CONTEXT

# =========================================
# LOAD ENV VARIABLES
# =========================================

env_vars = dotenv_values(".env")

Username = env_vars.get("Username", "User")
Assistantname = env_vars.get("Assistantname", "Jarvis")
# =========================================
# SYSTEM PROMPT
# =========================================

def _search_system(lang: str) -> str:
    return build_system_prompt(
        Assistantname,
        Username,
        lang,
        extra=(
            "Use ONLY the web search snippets below for facts. "
            "Give a clear short answer (2-6 sentences). "
            "If snippets are weak, say you could not find fresh data online."
        ),
    )

# =========================================
# CREATE DATA FOLDER
# =========================================

os.makedirs("Data", exist_ok=True)

# =========================================
# CHAT LOG FILE
# =========================================

# =========================================
# GOOGLE SEARCH
# =========================================

def GoogleSearch(query):
    """Web snippets — Wikipedia + News RSS (+ optional DDG)."""
    try:
        return fetch_web_results(query, fast=FAST_MODE)
    except Exception as e:
        print(f"Web search error: {e}")
        return f"Web search error: {e}"

# =========================================
# CLEAN ANSWER
# =========================================

def AnswerModifier(answer):

    lines = answer.split("\n")

    non_empty_lines = [line for line in lines if line.strip()]

    return "\n".join(non_empty_lines)

# =========================================
# DEFAULT CHAT
# =========================================

SystemChatBot = []

# =========================================
# REALTIME INFO
# =========================================

def Information():

    current = datetime.datetime.now()

    info = f"""
Current Date and Time Information:

Day: {current.strftime("%A")}
Date: {current.strftime("%d")}
Month: {current.strftime("%B")}
Year: {current.strftime("%Y")}
Time: {current.strftime("%H:%M:%S")}
"""

    return info

# =========================================
# MAIN AI FUNCTION
# =========================================

def _time_only_query(prompt: str) -> bool:
    q = prompt.lower()
    time_w = ("time", "date", "samay", "waqt", "tarikh", "kitne baje", "baje", "din")
    heavy = ("weather", "mausam", "news", "khabar", "score", "match")
    return any(w in q for w in time_w) and not any(w in q for w in heavy)


def RealtimeSearchEngine(prompt, on_chunk=None, language=None, save_messages=True):
    try:
        lang = language or detect_language(prompt)
        set_reply_language(lang)

        messages = db.get_recent_messages(LLM_CONTEXT)
        messages.append({"role": "user", "content": prompt})

        temp_system = [{"role": "system", "content": _search_system(lang)}, {"role": "system", "content": Information()}]
        if not (FAST_MODE and _time_only_query(prompt)) and is_web_worthy(prompt):
            snippets = GoogleSearch(prompt)[:3500]
            temp_system.append({
                "role": "system",
                "content": f"=== WEB SEARCH DATA ===\n{snippets}\n=== END ===",
            })

        answer = stream_chat(
            temp_system + messages,
            max_tokens=SEARCH_MAX_TOKENS,
            temperature=0.4,
            on_chunk=on_chunk,
        )
        if save_messages:
            db.save_message("user", prompt, language=lang, source="realtime")
            db.save_message("assistant", answer, language=lang, source="realtime")
        return AnswerModifier(answer)

    except Exception as e:
        print(f"Search error ({get_provider()}/{get_model()}): {e}")
        return f"Search error: {e}"

# =========================================
# MAIN LOOP
# =========================================

if __name__ == "__main__":

    print("\n========== AI CHATBOT ==========\n")

    while True:

        prompt = input("Enter Your Query: ")

        if prompt.lower() in ["exit", "quit", "bye"]:

            print("Goodbye!")

            break

        answer = RealtimeSearchEngine(prompt)

        print("\n")