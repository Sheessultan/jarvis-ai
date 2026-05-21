from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import dotenv_values
from Backend.Language import get_stt_locale, prepare_query, get_display_language
from Backend.config import FAST_MODE
from Backend import MongoDB as db
from Backend.Language import detect_language
import os
import time
import threading

env_vars = dotenv_values(".env")

_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>STT</title></head>
<body>
<button id="start">Start</button>
<button id="stop">Stop</button>
<h2 id="output"></h2>
<script>
let recognition, listening = false, paused = false;

function startRec() {{
    if (paused) return;
    try {{
        recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = "{locale}";
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.onresult = function(e) {{
            if (paused) return;
            let t = "";
            for (let i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
            document.getElementById("output").innerHTML = t;
        }};
        recognition.onend = function() {{
            if (listening && !paused) try {{ recognition.start(); }} catch(err) {{}}
        }};
        recognition.start();
        listening = true;
    }} catch(err) {{}}
}}

function pauseRec() {{
    paused = true;
    listening = false;
    if (recognition) try {{ recognition.stop(); }} catch(err) {{}}
    document.getElementById("output").innerHTML = "";
}}

function resumeRec() {{
    paused = false;
    document.getElementById("output").innerHTML = "";
    startRec();
}}

document.getElementById("start").onclick = function() {{ paused = false; startRec(); }};
document.getElementById("stop").onclick = function() {{
    listening = false;
    if (recognition) recognition.stop();
}};
window.onload = function() {{ startRec(); }};
</script>
</body>
</html>
"""


def _current_stt_locale() -> str:
    return get_stt_locale()


def _write_voice_html():
    os.makedirs("Data", exist_ok=True)
    path = os.path.abspath("Data/Voice.html")
    with open(path, "w", encoding="utf-8") as file:
        file.write(_HTML_TEMPLATE.format(locale=_current_stt_locale()))
    return path


html_path = _write_voice_html()

chrome_options = Options()
chrome_options.add_argument("--use-fake-ui-for-media-stream")
chrome_options.add_argument("--disable-infobars")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-background-networking")
chrome_options.add_argument("--window-size=900,500")
if FAST_MODE:
    chrome_options.add_argument("--mute-audio")

try:
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
except Exception as e:
    print("Chrome Driver Error:", e)
    exit()

_speech_ready = False
_STABLE_NEEDED = 5 if FAST_MODE else 8
_POLL_SEC = 0.07 if FAST_MODE else 0.12


def _warm_page():
    global _speech_ready
    try:
        driver.get(f"file:///{html_path}")
        time.sleep(0.45 if FAST_MODE else 0.8)
        _speech_ready = True
    except Exception as e:
        print(f"STT warm error: {e}")


threading.Thread(target=_warm_page, daemon=True).start()

_last_assistant_reply = ""
_TTS_COOLDOWN = 1.4 if FAST_MODE else 1.8


def set_last_assistant_reply(text: str) -> None:
    global _last_assistant_reply
    _last_assistant_reply = (text or "").strip().lower()


def pause_listening() -> None:
    """Stop mic while assistant speaks — prevents hearing own TTS."""
    try:
        driver.execute_script("if (typeof pauseRec === 'function') pauseRec();")
    except Exception:
        pass


def clear_stt_buffer() -> None:
    try:
        driver.execute_script("document.getElementById('output').innerHTML = '';")
    except Exception:
        pass


def wait_after_tts(cooldown: float = None) -> None:
    """Cooldown after speech so speakers/mic echo fades."""
    time.sleep(cooldown if cooldown is not None else _TTS_COOLDOWN)
    clear_stt_buffer()


def is_echo_of_assistant(text: str) -> bool:
    """Reject transcript that matches what Nexus just said."""
    if not text or not _last_assistant_reply:
        return False
    t = text.strip().lower()
    r = _last_assistant_reply
    if len(t) < 4:
        return False
    if t in r or r in t:
        return True
    tw = set(t.split())
    rw = set(r.split())
    if len(tw) < 3:
        return False
    overlap = len(tw & rw) / len(tw)
    if overlap >= 0.5:
        return True
    echo_phrases = (
        "madad karne", "madad ke liye", "kya chahie", "bata dena", "main yahan",
        "tumhari madad", "how may i help", "how can i help",
    )
    return any(p in t for p in echo_phrases) and overlap >= 0.35


def SpeechRecognition():
    global _speech_ready
    try:
        global html_path
        html_path = _write_voice_html()
        if not _speech_ready:
            _warm_page()

        clear_stt_buffer()
        driver.execute_script(
            "if (typeof resumeRec === 'function') resumeRec();"
            " else if (typeof startRec === 'function') startRec();"
        )
        try:
            driver.find_element(By.ID, "start").click()
        except Exception:
            pass

        print(f"\nListening ({_current_stt_locale()})...\n")

        last_text = ""
        last_saved = ""
        stable = 0

        while True:
            try:
                text = driver.find_element(By.ID, "output").text.strip()
                if text:
                    print(f"\r{text}", end="", flush=True)
                    if text != last_saved:
                        lang = detect_language(text)
                        db.save_heard_speech(text, status="interim", language=lang)
                        last_saved = text
                    if text == last_text:
                        stable += 1
                    else:
                        stable = 0
                    last_text = text
                    if stable >= _STABLE_NEEDED:
                        if is_echo_of_assistant(text):
                            print("\n(Ignored: assistant echo — listening again)\n")
                            last_text = ""
                            last_saved = ""
                            stable = 0
                            clear_stt_buffer()
                            driver.execute_script(
                                "if (typeof resumeRec === 'function') resumeRec();"
                            )
                            continue
                        driver.execute_script(
                            "listening=false; if(recognition) recognition.stop();"
                        )
                        try:
                            driver.find_element(By.ID, "stop").click()
                        except Exception:
                            pass
                        print("\n")
                        final = prepare_query(text)
                        db.save_heard_speech(
                            text,
                            status="final",
                            language=detect_language(text),
                        )
                        return final
                time.sleep(_POLL_SEC)
            except Exception:
                pass
    except Exception as e:
        print(f"Speech Recognition Error: {e}")
        db.save_heard_speech("", status="error", language=None)
        return ""


def QueryModifier(query):
    return prepare_query(query)


if __name__ == "__main__":
    while True:
        t = SpeechRecognition()
        if t:
            print(t)
