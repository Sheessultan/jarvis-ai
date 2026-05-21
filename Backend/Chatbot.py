import datetime
from dotenv import dotenv_values
from Backend.LLM import stream_chat, get_provider, get_model
from Backend.Language import detect_language, set_reply_language, build_system_prompt
from Backend.RealtimeSearchEngine import RealtimeSearchEngine
from Backend.WebFallback import should_search_web, web_search_notice
from Backend.WebSearchProvider import is_web_worthy
from Backend.AutoExecute import auto_execute_from_voice, wants_pc_action, sanitize_refusal
from Backend import MongoDB as db
from Backend.config import LLM_MAX_TOKENS, LLM_CONTEXT

env_vars = dotenv_values(".env")
Username = env_vars.get("Username")
Assistantname = env_vars.get("Assistantname")


def _needs_time_context(query: str) -> bool:
    q = query.lower()
    keys = ("time", "date", "day", "today", "clock", "hour", "samay", "waqt", "tarikh", "baje")
    return any(w in q for w in keys)


def RealtimeInformation():
    now = datetime.datetime.now()
    return f"Now: {now.strftime('%A %d %B %Y, %H:%M:%S')}."


def AnswerModifier(Answer):
    return "\n".join([line for line in Answer.split("\n") if line.strip()])


def ChatBot(
    Query,
    on_chunk=None,
    language=None,
    action_done: str = None,
    live_context: str = None,
):
    try:
        lang = language or detect_language(Query)
        set_reply_language(lang)

        if is_web_worthy(Query) and not wants_pc_action(Query) and not action_done:
            return RealtimeSearchEngine(Query, on_chunk=on_chunk, language=lang)

        messages = db.get_recent_messages(LLM_CONTEXT)
        messages.append({"role": "user", "content": Query})

        system = build_system_prompt(Assistantname, Username, lang)
        extra = "If you lack facts not in chat history, say briefly you will check the web."
        if action_done:
            extra = (
                f"SYSTEM ALREADY EXECUTED ON PC:\n{action_done}\n"
                "Confirm in the user's display language that YOU did it. "
                "Never say run it yourself or I cannot."
            )
        elif wants_pc_action(Query):
            extra += " User wants a PC action — assume Nexus executes it; never tell them to run manually."

        api_messages = [{"role": "system", "content": system + " " + extra}]
        if live_context:
            api_messages.append(
                {
                    "role": "system",
                    "content": (
                        "LIVE PC CONTEXT (screen/windows/IP — use this, do not guess):\n"
                        + live_context[:3500]
                    ),
                }
            )
        if _needs_time_context(Query):
            api_messages.append({"role": "system", "content": RealtimeInformation()})
        api_messages.extend(messages)

        try:
            from Backend.config import HUMAN_MODE
            temp = 0.72 if HUMAN_MODE else 0.4
        except Exception:
            temp = 0.4

        answer = stream_chat(
            api_messages,
            max_tokens=LLM_MAX_TOKENS,
            temperature=temp,
            on_chunk=on_chunk,
        )

        if not answer:
            answer = "Please try again."

        answer = sanitize_refusal(answer, Query)

        if should_search_web(Query, messages, answer) and not wants_pc_action(Query):
            web_answer = RealtimeSearchEngine(
                Query,
                on_chunk=on_chunk,
                language=lang,
                save_messages=False,
            )
            answer = f"{web_search_notice(lang)}\n{web_answer}"

        db.save_message("user", Query, language=lang, source="chatbot")
        db.save_message("assistant", answer, language=lang, source="chatbot")
        return answer

    except Exception as e:
        print(f"ChatBot error ({get_provider()}/{get_model()}): {e}")
        return "Connection issue, please try again."
