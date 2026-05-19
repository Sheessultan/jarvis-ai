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
from Backend.Model import first_layer_dmm
from Backend.RealtimeSearchEngine import RealtimeSearchEngine
from Backend.Automation import Automation
from Backend.SpeechToText import SpeechRecognition
from Backend.Chatbot import ChatBot
from Backend.TextToSpeech import TextToSpeech

from dotenv import dotenv_values
from asyncio import run
from time import sleep
import subprocess
import threading
import json
import os


# Load environment variables
env_vars = dotenv_values(".env")
Username = env_vars.get("Username", "User")
Assistantname = env_vars.get("Assistantname", "Assistant")

DefaultMessage = f""" {Username}: Hello {Assistantname}, How are you?
{Assistantname}: Welcome {Username}. I am doing well. How may I help you? """

functions = ["open", "close", "play", "system", "content", "google search", "youtube search"]
subprocess_list = []


# Ensure a default chat log exists if no chats are logged
def ShowDefaultChatIfNoChats():
    try:
        with open(r'Data\ChatLog.json', "r", encoding='utf-8') as file:
            content = file.read().strip()

        if len(content) < 5:
            os.makedirs("Data", exist_ok=True)

            with open(r'Data\ChatLog.json', "w", encoding='utf-8') as file:
                file.write("[]")

            with open(TempDirectoryPath('Database.data'), 'w', encoding='utf-8') as temp_file:
                temp_file.write("")

            with open(TempDirectoryPath('Responses.data'), 'w', encoding='utf-8') as response_file:
                response_file.write(DefaultMessage)

    except FileNotFoundError:
        print("ChatLog.json not found. Creating default response.")
        os.makedirs("Data", exist_ok=True)

        with open(r'Data\ChatLog.json', "w", encoding='utf-8') as file:
            file.write("[]")

        with open(TempDirectoryPath('Responses.data'), 'w', encoding='utf-8') as response_file:
            response_file.write(DefaultMessage)


def ReadChatLogJson():
    try:
        with open(r'Data\ChatLog.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except:
        return []


def ChatLogIntegration():
    json_data = ReadChatLogJson()
    formatted_chatlog = ""

    for entry in json_data:
        if entry.get("role") == "user":
            formatted_chatlog += f"{Username}: {entry.get('content','')}\n"
        elif entry.get("role") == "assistant":
            formatted_chatlog += f"{Assistantname}: {entry.get('content','')}\n"

    os.makedirs(TempDirectoryPath(''), exist_ok=True)

    with open(TempDirectoryPath('Database.data'), 'w', encoding='utf-8') as file:
        file.write(AnswerModifier(formatted_chatlog))


def ShowChatOnGUI():
    try:
        with open(TempDirectoryPath('Database.data'), 'r', encoding='utf-8') as file:
            data = file.read().strip()

        if data:
            with open(TempDirectoryPath('Responses.data'), 'w', encoding='utf-8') as response_file:
                response_file.write(data)

    except FileNotFoundError:
        pass


def InitialExecution():
    SetMicrophoneStatus("true")
    ShowTextToScreen("")
    ShowDefaultChatIfNoChats()
    ChatLogIntegration()
    ShowChatOnGUI()


def MainExecution():
    try:
        TaskExecution = False
        ImageExecution = False
        ImageGenerationQuery = ""

        SetAsssistantStatus("Listening...")
        Query = SpeechRecognition()
        print(Query)

        if not Query:
            return False

        ShowTextToScreen(f"{Username}: {Query}")
        SetAsssistantStatus("Thinking...")

        Decision = first_layer_dmm(Query)

        print(f"\nDecision: {Decision}\n")

        G = any(i.startswith("general") for i in Decision)
        R = any(i.startswith("realtime") for i in Decision)

        Merged_query = " and ".join(
            [" ".join(i.split()[1:]) for i in Decision if i.startswith("general") or i.startswith("realtime")]
        )

        for q in Decision:
            if "generate" in q:
                ImageGenerationQuery = q
                ImageExecution = True

        for q in Decision:
            if any(q.startswith(func) for func in functions):
                Automation(list(Decision))
                TaskExecution = True
                break

        if ImageExecution:
            with open(r'Frontend\Files\ImageGeneration.data', "w") as file:
                file.write(f"{ImageGenerationQuery},True")

            subprocess.Popen(
                ['python', r"Backend\ImageGeneration.py"],
                shell=False
            )

        Answer = None

        if R:
            SetAsssistantStatus("Searching...")
            Answer = RealtimeSearchEngine(QueryModifier(Merged_query))

        else:
            for q in Decision:

                if "general" in q:
                    QueryFinal = q.replace("general", "")
                    Answer = ChatBot(QueryModifier(QueryFinal))

                elif "realtime" in q:
                    QueryFinal = q.replace("realtime", "")
                    Answer = RealtimeSearchEngine(QueryModifier(QueryFinal))

                elif "exit" in q:
                    TextToSpeech("Okay, Bye!")
                    os._exit(1)

                if Answer:
                    break

        if Answer:
            ShowTextToScreen(f"{Assistantname}: {Answer}")
            SetAsssistantStatus("Answering...")
            TextToSpeech(Answer)
            return True

    except Exception as e:
        print(f"Error in MainExecution: {e}")


# def FirstThread():
#     while True:
#         try:
#             CurrentStatus = str(GetMicrophoneStatus()).lower()

#             if CurrentStatus == "true":
#                 MainExecution()

#             elif CurrentStatus == "false":
#                 if "Available..." not in GetAssistantStatus():
#                     SetAsssistantStatus("Available...")

#             else:
#                 pass

#         except Exception as e:
#             print(f"Error in FirstThread: {e}")
#             sleep(1)

def FirstThread():
    while True:
        try:
            print("MIC:", GetMicrophoneStatus())
            print("Mic Status:", GetMicrophoneStatus())

            CurrentStatus = str(GetMicrophoneStatus()).lower()

            if CurrentStatus == "true":
                MainExecution()

            elif CurrentStatus == "false":
                if "Available..." not in GetAssistantStatus():
                    SetAsssistantStatus("Available...")

        except Exception as e:
            print(f"Error in FirstThread: {e}")
            sleep(1)

def first_layer_dmm(query: str):
    """
    Simple Decision Making Module (DMM)
    Converts user query into structured actions for JARVIS
    """

    if not query:
        return ["general empty query"]

    query = query.lower()
    decision = []

    # EXIT
    if any(word in query for word in ["exit", "quit", "bye", "stop jarvis"]):
        decision.append("exit")

    # SYSTEM CONTROL
    elif any(word in query for word in ["open", "start", "launch"]):
        decision.append("system open " + query)

    elif any(word in query for word in ["close", "shutdown", "stop app"]):
        decision.append("system close " + query)

    # YOUTUBE
    elif "youtube" in query:
        decision.append("youtube search " + query)

    # GOOGLE SEARCH
    elif "google" in query or "search" in query:
        decision.append("google search " + query)

    # REALTIME INFO
    elif any(word in query for word in ["weather", "news", "time", "date", "live"]):
        decision.append("realtime " + query)

    # IMAGE GENERATION
    elif any(word in query for word in ["generate image", "create image", "draw", "image"]):
        decision.append("generate image " + query)

    # DEFAULT → CHATBOT
    else:
        decision.append("general " + query)

    return decision
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