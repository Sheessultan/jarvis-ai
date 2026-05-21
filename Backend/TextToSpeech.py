import pygame
import re
import asyncio
import edge_tts
import os
import threading
import uuid
import time
import glob
from Backend.Language import detect_language, get_reply_language, get_tts_voice, normalize_language
from Backend.config import TTS_RATE, TTS_RATE_ROMAN, SKIP_TTS_LONG, TTS_FULL_ANSWER, TTS_CHUNK_CHARS, FAST_MODE

DATA_DIR = "Data"
TTS_PITCH = "+2Hz"

_mixer_ready = False
_tts_lock = threading.Lock()
_loop = None


def _ensure_mixer():
    global _mixer_ready
    if not _mixer_ready:
        pygame.mixer.init(frequency=24000)
        _mixer_ready = True


def _get_loop():
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop


def _new_speech_path() -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, f"speech_{uuid.uuid4().hex}.mp3")


def _stop_playback():
    try:
        if _mixer_ready:
            pygame.mixer.music.stop()
            if hasattr(pygame.mixer.music, "unload"):
                pygame.mixer.music.unload()
    except Exception:
        pass


def _safe_remove(path: str, retries: int = 8):
    for _ in range(retries):
        try:
            if path and os.path.isfile(path):
                os.remove(path)
            return
        except OSError:
            time.sleep(0.12)


def _cleanup_old_speech_files(keep: int = 3):
    try:
        files = sorted(
            glob.glob(os.path.join(DATA_DIR, "speech_*.mp3")),
            key=os.path.getmtime,
            reverse=True,
        )
        for old in files[keep:]:
            _safe_remove(old, retries=3)
    except Exception:
        pass


async def _save_audio(text: str, voice: str, out_path: str, rate: str = None) -> None:
    comm = edge_tts.Communicate(text, voice, pitch=TTS_PITCH, rate=rate or TTS_RATE)
    await comm.save(out_path)


def _speak_file(path: str, func):
    _ensure_mixer()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    clock = pygame.time.Clock()
    while pygame.mixer.music.get_busy():
        if not func():
            break
        clock.tick(30)


def _split_tts_chunks(text: str, max_len: int = None) -> list[str]:
    """Split long answers so edge-tts reads the full reply."""
    max_len = max_len or TTS_CHUNK_CHARS
    text = re.sub(r"\n+", ". ", text.strip())
    if len(text) <= max_len:
        return [text]

    chunks = []
    parts = re.split(r"(?<=[.!?।])\s+", text)
    buf = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) > max_len:
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(part), max_len):
                chunks.append(part[i : i + max_len])
            continue
        if len(buf) + len(part) + 1 <= max_len:
            buf = f"{buf} {part}".strip() if buf else part
        else:
            if buf:
                chunks.append(buf)
            buf = part
    if buf:
        chunks.append(buf)
    return chunks or [text[:max_len]]


def TTS(Text, func=lambda r=None: True, language=None):
    text = str(Text).strip()
    if not text:
        return True

    lang = normalize_language(language or get_reply_language() or detect_language(text))
    voice = get_tts_voice(lang)
    rate = TTS_RATE_ROMAN if lang in ("roman", "hi", "ur") else TTS_RATE
    out_path = _new_speech_path()

    with _tts_lock:
        try:
            _stop_playback()
            time.sleep(0.05)
            loop = _get_loop()
            loop.run_until_complete(_save_audio(text, voice, out_path, rate=rate))
            if not os.path.isfile(out_path):
                print("TTS error: audio file was not created")
                return False
            _speak_file(out_path, func)
            return True
        except Exception as e:
            print(f"TTS error: {e}")
            return False
        finally:
            _stop_playback()
            time.sleep(0.05)
            _safe_remove(out_path)
            _cleanup_old_speech_files()


def TextToSpeech(Text, func=lambda r=None: True, language=None):
    """Speak full answer (chunked). SkipTTSLong=false by default."""
    text = str(Text).strip()
    if not text:
        return True

    lang = normalize_language(language or get_reply_language())

    if TTS_FULL_ANSWER:
        chunks = _split_tts_chunks(text)
        for i, chunk in enumerate(chunks):
            if not TTS(chunk, func, language=lang):
                return False
            if i < len(chunks) - 1:
                time.sleep(0.15)
        return True

    if SKIP_TTS_LONG and len(text) > 160:
        first = _split_tts_chunks(text, max_len=120)[0]
        TTS(first, func, language=lang)
        return True

    TTS(text, func, language=lang)
    return True


def TextToSpeechAsync(Text, language=None):
    threading.Thread(
        target=lambda: TextToSpeech(Text, language=language),
        daemon=True,
    ).start()
