# from groq import Groq
# from dotenv import dotenv_values

# # LOAD ENV
# env_vars = dotenv_values(".env")

# GroqAPIKey = env_vars.get("GroqAPIKey")

# # GROQ CLIENT
# client = Groq(api_key=GroqAPIKey)

# # CHAT FUNCTION
# def ChatBot(prompt):

#     try:

#         completion = client.chat.completions.create(

#             model="llama-3.3-70b-versatile",

#             messages=[
#                 {
#                     "role": "system",
#                     "content": "You are a smart AI assistant."
#                 },
#                 {
#                     "role": "user",
#                     "content": prompt
#                 }
#             ],

#             temperature=0.7,
#             max_tokens=1024,
#             top_p=1,
#             stream=True

#         )

#         answer = ""

#         for chunk in completion:

#             if chunk.choices[0].delta.content:

#                 content = chunk.choices[0].delta.content

#                 print(content, end="", flush=True)

#                 answer += content

#         print("\n")

#         return answer

#     except Exception as e:

#         print(f"\nERROR: {e}\n")

# # MAIN LOOP
# if __name__ == "__main__":

#     print("\n========== JARVIS AI ==========\n")

#     while True:

#         question = input(">>> ")

#         if question.lower() in ["exit", "quit"]:

#             break

#         ChatBot(question)

def first_layer_dmm(query):
    """
    Simple Decision Making Module for JARVIS
    """

    if not query:
        return ["general hello"]

    query = query.lower().strip()
    output = []

    # EXIT COMMAND
    if any(word in query for word in ["exit", "quit", "bye", "stop jarvis"]):
        return ["exit"]

    # SYSTEM ACTIONS
    if any(word in query for word in ["open", "start", "launch"]):
        output.append("system open " + query)

    elif any(word in query for word in ["close", "shutdown"]):
        output.append("system close " + query)

    # YOUTUBE
    elif "youtube" in query:
        output.append("youtube search " + query)

    # GOOGLE SEARCH
    elif "google" in query or "search" in query:
        output.append("google search " + query)

    # REALTIME INFO
    elif any(word in query for word in ["weather", "news", "time", "date"]):
        output.append("realtime " + query)

    # IMAGE GENERATION
    elif any(word in query for word in ["image", "draw", "generate"]):
        output.append("generate image " + query)

    # DEFAULT CHAT
    else:
        output.append("general " + query)

    return output