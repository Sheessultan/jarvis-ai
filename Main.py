from Frontend.GUI import (
    GraphicalUserInterface,
    SetAsssistantStatus,
    ShowTextToScreen,
    TempDirectoryPath,
    SetMicrophoneStatus,
    AnswerModifier,
    QueryModifier,
    GetMicrophoneStatus,
    GetAssistantStatus,
)
from Backend.RealtimeSearchEngine import RealtimeSearchEngine
from Backend.Automation import Automation, extract_open_target
from Backend.SystemControl import (
    handle_powershell,
    handle_cmd,
    handle_browser,
    handle_email,
)
from Backend.AutoExecute import auto_execute_from_voice, wants_pc_action
from Backend.LiveContext import build_live_context, handle_direct_query
from Backend.QueryNormalize import wants_ip_info, wants_screen_read
from Backend.SpeechToText import (
    SpeechRecognition,
    pause_listening,
    set_last_assistant_reply,
    wait_after_tts,
)
from Backend.Chatbot import ChatBot
from Backend.TextToSpeech import TextToSpeech
from Backend.config import FAST_MODE
from Backend.Language import (
    detect_language,
    set_reply_language,
    get_display_language,
    dmm_keywords,
    multilingual_exit_notice,
    LANG_LABELS,
    ui_message,
)
from Backend.config import DEFAULT_LANGUAGE

from dotenv import dotenv_values
from Backend import MongoDB as db
from time import sleep
import subprocess
import threading
import os

env_vars = dotenv_values(".env")
Username = env_vars.get("Username", "User")
Assistantname = env_vars.get("Assistantname", "Assistant")

def _welcome_user():
    if DEFAULT_LANGUAGE == "en":
        return f"Hello {Assistantname}, how are you?"
    return f"Namaste {Assistantname}, kaise ho?"


def _welcome_assistant():
    if DEFAULT_LANGUAGE == "en":
        return (
            f"Welcome {Username}. I am ready. "
            f"Speak in English — I can control your PC, search the web, and read the screen."
        )
    return f"Welcome {Username} boss. Main theek hun. Batao kya madad chahiye?"


DefaultMessage = f"""{Username}: {_welcome_user()}
{Assistantname}: {_welcome_assistant()}"""

functions = [
    "open", "close", "play", "system", "content", "google search", "youtube search",
    "powershell", "cmd", "browser", "email", "chrome",
]


def ShowDefaultChatIfNoChats():
    if not db.has_messages():
        db.save_message("user", _welcome_user(), source="welcome")
        db.save_message("assistant", _welcome_assistant(), source="welcome")
        os.makedirs(TempDirectoryPath(""), exist_ok=True)
        with open(TempDirectoryPath("Responses.data"), "w", encoding="utf-8") as response_file:
            response_file.write(DefaultMessage)


def ChatLogIntegration():
    formatted_chatlog = db.get_formatted_chatlog(Username, Assistantname)
    os.makedirs(TempDirectoryPath(""), exist_ok=True)
    with open(TempDirectoryPath("Database.data"), "w", encoding="utf-8") as file:
        file.write(AnswerModifier(formatted_chatlog))


def ShowChatOnGUI():
    try:
        with open(TempDirectoryPath("Database.data"), "r", encoding="utf-8") as file:
            data = file.read().strip()
        if data:
            with open(TempDirectoryPath("Responses.data"), "w", encoding="utf-8") as response_file:
                response_file.write(data)
    except FileNotFoundError:
        pass


def InitialExecution():
    SetMicrophoneStatus("true")
    ShowTextToScreen("")
    threading.Thread(target=db.ensure_connected, daemon=True).start()
    ShowDefaultChatIfNoChats()
    ChatLogIntegration()
    ShowChatOnGUI()


def first_layer_dmm(query: str):
    """Multilingual routing — keeps original query text for general chat."""
    if not query or not query.strip():
        return ["general "]

    original = query.strip()
    q = dmm_keywords(original)

    if any(w in q for w in ("exit", "quit", "bye", "alvida", "allah hafiz", "band karo", "bas karo", "stop jarvis")):
        return ["exit"]

    if any(w in q for w in ("powershell", "power shell")):
        return [f"powershell {original}", f"general {original}"]

    if any(w in q for w in ("cmd", "command prompt")) and any(
        x in q for x in ("run", "execute", "chalao", "karo", "dir", "ipconfig", "command")
    ):
        return [f"cmd {original}", f"general {original}"]

    if any(w in q for w in ("email", "mail bhej", "gmail", "mail kholo", "mail likho")):
        return [f"email {original}", f"general {original}"]

    if wants_ip_info(original) or (
        "ip" in q and any(x in q for x in ("batao", "bata", "system", "mera", "meri", "kitni", "kya"))
    ):
        return [f"powershell ipconfig", f"general {original}"]

    if wants_screen_read(original):
        return [f"general {original}"]

    if "minimize" in q or "minimise" in q:
        from Backend.WindowsControl import extract_window_target
        tgt = extract_window_target(original)
        cmd = f"system minimize {tgt}".strip()
        return [cmd, f"general {original}"]

    if "shutdown" in q and "cancel" not in q:
        return [f"system shutdown", f"general {original}"]

    if "restart" in q or "reboot" in q:
        return [f"system restart", f"general {original}"]

    if "lock" in q:
        return [f"system lock", f"general {original}"]

    if "youtube" in q and any(x in q for x in ("kholo", "open", "chalao", "karo", "start", "launch")):
        return ["open youtube"]

    if any(w in q for w in ("chrome", "browser", "website", "url kholo")) and any(
        x in q for x in ("kholo", "open", "chalu", "goto", "jao", "me", "karo")
    ):
        return [f"browser {original}", f"general {original}"]

    if any(w in q for w in ("open", "start", "launch", "kholo", "chalu")):
        target = extract_open_target(original)
        return [f"open {target}"]

    if any(w in q for w in ("close", "shutdown", "band karo", "band kro", "band kro")):
        return [f"close {extract_open_target(original)}"]

    if any(w in q for w in ("play", "bajao", "chalao")) and "youtube" not in q:
        return [f"play {original}"]

    if "youtube" in q or q.strip().startswith("yt "):
        return [f"youtube search {original}"]

    if any(w in q for w in ("web search", "internet pe", "web pe", "online search", "search karke", "search kar")):
        return [f"realtime {original}"]

    if any(w in q for w in ("google", "dhundo")) and "search" in q and "youtube" not in q:
        return [f"google search {original}"]

    _realtime_hints = (
        "weather", "mausam", "news", "khabar", "time", "samay", "waqt", "date",
        "tarikh", "live", "kitne baje", "ipl", "cricket", "match", "score",
        "latest", "aaj ka", "24 ghante", "price", "stock", "headline",
        "what is", "who is", "kya hai", "kaun hai", "search", "dhundo",
        "bare mein", "baare mein", "ke bare", "framework", "library",
        "internet se", "online", "google se", "web se",
    )
    if any(w in q for w in _realtime_hints):
        return [f"realtime {original}"]

    if "batao" in q and any(
        x in q
        for x in ("news", "ipl", "match", "weather", "aaj", "score", "web", "google", "react", "python")
    ):
        return [f"realtime {original}"]

    if any(w in q for w in ("generate image", "create image", "image banao", "tasveer", "draw")):
        return [f"generate image {original}"]

    return [f"general {original}"]


def MainExecution():
    try:
        ImageExecution = False
        ImageGenerationQuery = ""

        SetAsssistantStatus("Listening...")
        Query = SpeechRecognition()
        if not Query:
            return False

        user_lang = get_display_language()
        set_reply_language(user_lang)
        heard_lang = detect_language(Query)
        print(f"Language: {LANG_LABELS.get(user_lang, user_lang)} (heard: {heard_lang})")

        ShowTextToScreen(f"{Username}: {Query}")
        SetAsssistantStatus("Thinking...")

        Decision = first_layer_dmm(Query)
        db.save_voice_query(Query, language=user_lang, decision=Decision)
        print(f"\nDecision: {Decision}\n")

        live_ctx = build_live_context(Query, include_vision=False)
        print(f"Live context: {live_ctx[:120]}...\n")

        direct_answer = handle_direct_query(Query)
        if direct_answer:
            print(f"Direct action: {direct_answer[:200]}...\n")

        R = any(i.startswith("realtime") for i in Decision)

        Merged_query = " and ".join(
            i.split(" ", 1)[1] if " " in i else ""
            for i in Decision
            if i.startswith("general") or i.startswith("realtime")
        ).strip() or Query

        for q in Decision:
            if "generate" in q:
                ImageGenerationQuery = q
                ImageExecution = True

        shell_answer = direct_answer
        auto_summary = ""
        if wants_pc_action(Query) and not R and not direct_answer:
            SetAsssistantStatus("Executing on PC...")
            auto_summary, _auto_cmds = auto_execute_from_voice(Query, Decision)
            if auto_summary:
                print(auto_summary[:300])

        _sync_cmds = ("powershell ", "cmd ", "email ", "browser ", "chrome ")
        automation_cmds = [
            c for c in Decision
            if any(c.startswith(f) for f in functions)
            and not any(c.startswith(p) for p in _sync_cmds)
        ]

        for q in Decision:
            if auto_summary:
                break
            if q.startswith("powershell "):
                SetAsssistantStatus("Running PowerShell...")
                shell_answer = handle_powershell(q.split(" ", 1)[1] if " " in q else original)
            elif q.startswith("cmd "):
                SetAsssistantStatus("Running CMD...")
                shell_answer = handle_cmd(q.split(" ", 1)[1] if " " in q else original)
            elif q.startswith("email "):
                SetAsssistantStatus("Opening Gmail...")
                shell_answer = handle_email(q.split(" ", 1)[1] if " " in q else original)
            elif q.startswith("browser ") or q.startswith("chrome "):
                SetAsssistantStatus("Opening Chrome...")
                payload = q.split(" ", 1)[1] if " " in q else original
                shell_answer = handle_browser(payload)

        if automation_cmds and not auto_summary and not direct_answer:
            def _run_auto(cmds):
                import asyncio
                asyncio.run(Automation(cmds))

            threading.Thread(target=_run_auto, args=(automation_cmds,), daemon=True).start()

        if ImageExecution:
            with open(r"Frontend\Files\ImageGeneration.data", "w") as file:
                file.write(f"{ImageGenerationQuery},True")
            subprocess.Popen(["python", r"Backend\ImageGeneration.py"], shell=False)

        Answer = direct_answer

        def _live_reply(partial: str):
            ShowTextToScreen(f"{Username}: {Query}\n{Assistantname}: {partial}")

        if not Answer:
            if R:
                SetAsssistantStatus("Searching...")
                Answer = RealtimeSearchEngine(Merged_query, on_chunk=_live_reply, language=user_lang)
            else:
                for q in Decision:
                    if q.startswith("general"):
                        payload = q.split(" ", 1)[1] if " " in q else Query
                        done_ctx = auto_summary or None
                        Answer = ChatBot(
                            payload,
                            on_chunk=_live_reply,
                            language=user_lang,
                            action_done=done_ctx,
                            live_context=live_ctx,
                        )

                    elif q.startswith("realtime"):
                        payload = q.split(" ", 1)[1] if " " in q else Query
                        Answer = RealtimeSearchEngine(
                            payload, on_chunk=_live_reply, language=user_lang
                        )

                    elif "exit" in q:
                        bye = multilingual_exit_notice(user_lang)
                        TextToSpeech(bye, language=user_lang)
                        os._exit(1)

                    if Answer:
                        break

        if auto_summary and not Answer:
            Answer = auto_summary
        elif auto_summary and Answer:
            Answer = f"{auto_summary}\n\n{Answer}"

        if shell_answer and not Answer:
            Answer = shell_answer
        elif shell_answer and Answer and shell_answer not in Answer:
            Answer = f"{shell_answer}\n\n{Answer}"

        if not Answer and (direct_answer or auto_summary):
            Answer = direct_answer or auto_summary

        if Answer:
            db.save_heard_speech(Answer, status="assistant_reply", language=user_lang)
            ShowTextToScreen(f"{Username}: {Query}\n{Assistantname}: {Answer}")
            SetAsssistantStatus("Answering...")
            set_last_assistant_reply(Answer)
            pause_listening()
            TextToSpeech(Answer, language=user_lang)
            wait_after_tts()
            SetAsssistantStatus("Available...")
            return True

    except Exception as e:
        print(f"Error in MainExecution: {e}")


def FirstThread():
    SetMicrophoneStatus("true")
    while True:
        try:
            SetMicrophoneStatus("true")
            MainExecution()
        except Exception as e:
            print(f"Error in FirstThread: {e}")
            sleep(0.25)


def SecondThread():
    try:
        GraphicalUserInterface()
    except Exception as e:
        print(f"Error in SecondThread: {e}")


if __name__ == "__main__":
    InitialExecution()
    thread1 = threading.Thread(target=FirstThread, daemon=True)
    thread1.start()
    SecondThread()
