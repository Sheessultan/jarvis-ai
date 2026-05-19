from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import dotenv_values
import os
import time
import mtranslate as mt

# ==========================================
# LOAD ENV VARIABLES
# ==========================================

env_vars = dotenv_values(".env")

InputLanguage = env_vars.get("InputLanguage", "en-US")

# ==========================================
# HTML FOR SPEECH RECOGNITION
# ==========================================

HtmlCode = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Speech Recognition</title>
</head>

<body>

<button id="start">Start</button>
<button id="stop">Stop</button>

<h2 id="output"></h2>

<script>

let recognition;
const output = document.getElementById("output");

document.getElementById("start").onclick = function() {{

    recognition = new(window.SpeechRecognition || window.webkitSpeechRecognition)();

    recognition.lang = "{InputLanguage}";
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = function(event) {{

        let transcript = "";

        for (let i = 0; i < event.results.length; i++) {{
            transcript += event.results[i][0].transcript;
        }}

        output.innerHTML = transcript;
    }};

    recognition.start();
}};

document.getElementById("stop").onclick = function() {{

    if(recognition){{
        recognition.stop();
    }}
}};

</script>

</body>
</html>
"""

# ==========================================
# CREATE DATA FOLDER
# ==========================================

os.makedirs("Data", exist_ok=True)

html_path = os.path.abspath("Data/Voice.html")

with open(html_path, "w", encoding="utf-8") as file:
    file.write(HtmlCode)

# ==========================================
# CHROME OPTIONS
# ==========================================

chrome_options = Options()

chrome_options.add_argument("--use-fake-ui-for-media-stream")
chrome_options.add_argument("--disable-infobars")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--start-maximized")

# IMPORTANT
# Headless OFF rakho speech recognition ke liye
# chrome_options.add_argument("--headless=new")

# ==========================================
# START CHROME
# ==========================================

try:

    service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(
        service=service,
        options=chrome_options
    )

except Exception as e:

    print("Chrome Driver Error:")
    print(e)

    exit()

# ==========================================
# TRANSLATOR
# ==========================================

def UniversalTranslator(text):

    try:
        return mt.translate(text, "en", "auto")

    except:
        return text

# ==========================================
# QUERY FORMATTER
# ==========================================

def QueryModifier(query):

    query = query.strip().lower()

    if not query:
        return ""

    question_words = [
        "what",
        "who",
        "where",
        "when",
        "why",
        "how",
        "can you",
        "which"
    ]

    if any(query.startswith(word) for word in question_words):

        if not query.endswith("?"):
            query += "?"

    else:

        if not query.endswith("."):
            query += "."

    return query.capitalize()

# ==========================================
# SPEECH RECOGNITION
# ==========================================

def SpeechRecognition():

    try:

        driver.get(f"file:///{html_path}")

        time.sleep(2)

        start_button = driver.find_element(By.ID, "start")

        start_button.click()

        print("\nListening...\n")

        last_text = ""

        stable_count = 0

        while True:

            try:

                text = driver.find_element(By.ID, "output").text.strip()

                if text:

                    print(f"\r{text}", end="")

                    if text == last_text:

                        stable_count += 1

                    else:

                        stable_count = 0

                    last_text = text

                    # Stop after stable voice
                    if stable_count >= 15:

                        driver.find_element(By.ID, "stop").click()

                        print("\n")

                        if "en" not in InputLanguage.lower():

                            text = UniversalTranslator(text)

                        return QueryModifier(text)

                time.sleep(0.3)

            except Exception:
                pass

    except Exception as e:

        print(f"Speech Recognition Error: {e}")

        return ""

# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":

    print("\n========== SPEECH TO TEXT ==========\n")

    while True:

        try:

            text = SpeechRecognition()

            if text:

                print(f"\nYou Said: {text}\n")

        except KeyboardInterrupt:

            print("\nExiting...")

            driver.quit()

            break

        except Exception as e:

            print(f"Main Error: {e}")