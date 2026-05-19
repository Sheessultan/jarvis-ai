from googlesearch import search
from groq import Groq
from json import load, dump
import datetime
from dotenv import dotenv_values
import os

# =========================================
# LOAD ENV VARIABLES
# =========================================

env_vars = dotenv_values(".env")

Username = env_vars.get("Username", "User")
Assistantname = env_vars.get("Assistantname", "Jarvis")
GroqAPIKey = env_vars.get("GroqAPIKey")

# =========================================
# CHECK API KEY
# =========================================

if not GroqAPIKey:

    print("ERROR: GroqAPIKey not found in .env file")
    exit()

# =========================================
# GROQ CLIENT
# =========================================

client = Groq(api_key=GroqAPIKey)

# =========================================
# SYSTEM PROMPT
# =========================================

System = f"""
Hello, I am {Username}.

You are a highly advanced AI assistant named {Assistantname}.

Provide professional, accurate, and clear responses.
Use proper grammar, punctuation, and formatting.
"""

# =========================================
# CREATE DATA FOLDER
# =========================================

os.makedirs("Data", exist_ok=True)

# =========================================
# CHAT LOG FILE
# =========================================

CHATLOG_PATH = r"Data\ChatLog.json"

if not os.path.exists(CHATLOG_PATH):

    with open(CHATLOG_PATH, "w") as f:

        dump([], f)

# =========================================
# GOOGLE SEARCH
# =========================================

def GoogleSearch(query):

    try:

        results = list(search(query, advanced=True, num_results=5))

        Answer = f"Search results for '{query}':\n\n"

        for i in results:

            Answer += f"Title: {i.title}\n"
            Answer += f"Description: {i.description}\n\n"

        return Answer

    except Exception as e:

        return f"Google Search Error: {e}"

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

SystemChatBot = [

    {"role": "system", "content": System},

    {"role": "user", "content": "Hello"},

    {"role": "assistant", "content": "Hello Sir, how can I help you?"}

]

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

def RealtimeSearchEngine(prompt):

    global SystemChatBot

    try:

        with open(CHATLOG_PATH, "r") as f:

            messages = load(f)

    except:

        messages = []

    # Add user message
    messages.append({

        "role": "user",

        "content": prompt

    })

    # Google Search Data
    search_data = GoogleSearch(prompt)

    # Temporary system context
    temp_system = [

        {"role": "system", "content": System},

        {"role": "system", "content": Information()},

        {"role": "system", "content": search_data}

    ]

    try:

        completion = client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=temp_system + messages,

            temperature=0.7,

            max_tokens=2048,

            top_p=1,

            stream=True

        )

        Answer = ""

        print("\nAssistant:\n")

        for chunk in completion:

            content = chunk.choices[0].delta.content

            if content:

                print(content, end="", flush=True)

                Answer += content

        print("\n")

        Answer = Answer.strip().replace("</s>", "")

        # Save assistant reply
        messages.append({

            "role": "assistant",

            "content": Answer

        })

        with open(CHATLOG_PATH, "w") as f:

            dump(messages, f, indent=4)

        return AnswerModifier(Answer)

    except Exception as e:

        return f"Groq API Error: {e}"

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