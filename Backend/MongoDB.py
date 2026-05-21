"""
MongoDB storage for Nexus Intelligence — chats, content, voice logs, sessions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from dotenv import dotenv_values
import json
import os
import threading
import uuid

env_vars = dotenv_values(".env")


def _clean(value) -> str:
    if not value:
        return ""
    return str(value).strip().strip('"').strip("'")


MONGO_URI = _clean(env_vars.get("MongoURI")) or "mongodb://localhost:27017"
MONGO_DB_NAME = _clean(env_vars.get("MongoDBName")) or "nexus_intelligence"
USE_MONGO = _clean(env_vars.get("UseMongoDB", "true")).lower() in ("1", "true", "yes")
MAX_HISTORY = int(_clean(env_vars.get("MongoMaxHistory")) or "200")

Username = _clean(env_vars.get("Username")) or "User"
Assistantname = _clean(env_vars.get("Assistantname")) or "Nexus"

SESSION_FILE = os.path.join("Data", "session_id.txt")
LEGACY_CHATLOG = r"Data\ChatLog.json"

_client = None
_db = None
_connected = False
_lock = threading.Lock()
_session_id = None
_msg_cache: list = []
_cache_loaded = False


def _utcnow():
    return datetime.now(timezone.utc)


def is_connected() -> bool:
    return _connected and USE_MONGO


def get_session_id() -> str:
    global _session_id
    if _session_id:
        return _session_id
    os.makedirs("Data", exist_ok=True)
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            sid = f.read().strip()
            if sid:
                _session_id = sid
                return _session_id
    _session_id = str(uuid.uuid4())
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        f.write(_session_id)
    return _session_id


def new_session() -> str:
    """Start a fresh conversation session."""
    global _session_id
    _session_id = str(uuid.uuid4())
    os.makedirs("Data", exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        f.write(_session_id)
    if _connected:
        _db["sessions"].insert_one({
            "session_id": _session_id,
            "username": Username,
            "assistant": Assistantname,
            "started_at": _utcnow(),
        })
    return _session_id


def connect() -> bool:
    global _client, _db, _connected
    if not USE_MONGO:
        print("MongoDB disabled (UseMongoDB=false). Using local JSON files.")
        return False
    try:
        from pymongo import MongoClient
        from pymongo.errors import PyMongoError

        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")
        _db = _client[MONGO_DB_NAME]

        _db["messages"].create_index([("session_id", 1), ("created_at", 1)])
        _db["sessions"].create_index("session_id", unique=True)
        _db["generated_content"].create_index("created_at")
        _db["voice_queries"].create_index("created_at")
        _db["heard_speech"].create_index([("session_id", 1), ("created_at", 1)])
        _db["system_events"].create_index("created_at")

        _connected = True
        get_session_id()
        _ensure_session_doc()
        migrate_legacy_json()
        print(f"MongoDB connected: {MONGO_DB_NAME} @ {MONGO_URI}")
        return True
    except Exception as e:
        _connected = False
        print(f"MongoDB connection failed: {e}")
        print("Fallback: Data\\ChatLog.json will be used until MongoDB is running.")
        return False


def _ensure_session_doc():
    if not _connected:
        return
    sid = get_session_id()
    _db["sessions"].update_one(
        {"session_id": sid},
        {
            "$setOnInsert": {
                "session_id": sid,
                "username": Username,
                "assistant": Assistantname,
                "started_at": _utcnow(),
            },
            "$set": {"last_active": _utcnow()},
        },
        upsert=True,
    )


def _col(name):
    if not _connected:
        connect()
    return _db[name] if _connected else None


def _cache_append(role: str, content: str):
    global _msg_cache
    _msg_cache.append({"role": role, "content": content})
    if len(_msg_cache) > MAX_HISTORY:
        _msg_cache = _msg_cache[-MAX_HISTORY:]


def _persist_message_async(doc: dict):
    def _run():
        try:
            if not _connected:
                connect()
            if _connected:
                _col("messages").insert_one(doc)
        except Exception as e:
            print(f"Mongo save: {e}")

    threading.Thread(target=_run, daemon=True).start()


def save_message(
    role: str,
    content: str,
    *,
    language: str = None,
    source: str = "chatbot",
    metadata: dict = None,
    sync: bool = False,
):
    """Save message — memory cache first, MongoDB in background."""
    _cache_append(role, content)

    if not USE_MONGO:
        return _save_message_json(role, content)

    if not _connected:
        connect()
    if not is_connected():
        return _save_message_json(role, content)

    doc = {
        "session_id": get_session_id(),
        "username": Username,
        "assistant": Assistantname,
        "role": role,
        "content": content,
        "language": language,
        "source": source,
        "metadata": metadata or {},
        "created_at": _utcnow(),
    }
    if sync:
        with _lock:
            _col("messages").insert_one(doc)
    else:
        _persist_message_async(doc)


def save_messages_bulk(messages: list, source: str = "chatbot"):
    for m in messages:
        save_message(m.get("role", "user"), m.get("content", ""), source=source)


def _load_cache_from_db(limit: int):
    global _msg_cache, _cache_loaded
    if not is_connected():
        _msg_cache = _load_json_messages()[-limit:]
        _cache_loaded = True
        return
    cursor = (
        _col("messages")
        .find(
            {"session_id": get_session_id()},
            {"_id": 0, "role": 1, "content": 1},
        )
        .sort("created_at", -1)
        .limit(limit)
    )
    docs = list(cursor)
    docs.reverse()
    _msg_cache = [{"role": d["role"], "content": d["content"]} for d in docs]
    _cache_loaded = True


def get_recent_messages(limit: int = None) -> list:
    """Fast read from RAM cache; loads DB once per session."""
    from Backend.config import LLM_CONTEXT

    limit = limit or LLM_CONTEXT
    global _cache_loaded
    if not _cache_loaded:
        if not _connected and USE_MONGO:
            connect()
        _load_cache_from_db(max(limit, 20))
    return list(_msg_cache[-limit:])


def has_messages() -> bool:
    if _msg_cache:
        return True
    if not is_connected():
        return len(_load_json_messages()) > 0
    if not _connected and USE_MONGO:
        connect()
    if is_connected():
        return _col("messages").count_documents({"session_id": get_session_id()}) > 0
    return False


def get_formatted_chatlog(user_label: str = None, assistant_label: str = None) -> str:
    user_label = user_label or Username
    assistant_label = assistant_label or Assistantname
    lines = []
    for entry in get_recent_messages(limit=500):
        if entry.get("role") == "user":
            lines.append(f"{user_label}: {entry.get('content', '')}")
        elif entry.get("role") == "assistant":
            lines.append(f"{assistant_label}: {entry.get('content', '')}")
    return "\n".join(lines)


def save_heard_speech(text: str, *, status: str = "heard", language: str = None):
    """Save everything the mic picks up (interim + final) to MongoDB."""
    if not text and status != "empty":
        return

    def _run():
        if not USE_MONGO:
            return
        try:
            if not _connected:
                connect()
            if not is_connected():
                return
            from Backend.Language import detect_language

            _col("heard_speech").insert_one({
                "session_id": get_session_id(),
                "username": Username,
                "text": text or "",
                "status": status,
                "language": language or (detect_language(text) if text else None),
                "created_at": _utcnow(),
            })
        except Exception as e:
            print(f"Heard speech save: {e}")

    threading.Thread(target=_run, daemon=True).start()


def save_voice_query(query: str, language: str = None, decision: list = None):
    def _run():
        if not is_connected():
            return
        try:
            _col("voice_queries").insert_one({
                "session_id": get_session_id(),
                "username": Username,
                "query": query,
                "language": language,
                "decision": decision or [],
                "created_at": _utcnow(),
            })
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def save_generated_content(topic: str, content: str, filepath: str = None):
    if not is_connected():
        return
    _col("generated_content").insert_one({
        "session_id": get_session_id(),
        "username": Username,
        "topic": topic,
        "content": content,
        "filepath": filepath,
        "created_at": _utcnow(),
    })


def log_event(event_type: str, payload: dict = None):
    if not is_connected():
        return
    _col("system_events").insert_one({
        "session_id": get_session_id(),
        "event_type": event_type,
        "payload": payload or {},
        "created_at": _utcnow(),
    })


def migrate_legacy_json():
    """Import old Data/ChatLog.json into MongoDB once."""
    if not is_connected() or not os.path.exists(LEGACY_CHATLOG):
        return
    if _col("messages").count_documents({}) > 0:
        return
    try:
        with open(LEGACY_CHATLOG, "r", encoding="utf-8") as f:
            old = json.load(f)
        if not old:
            return
        for item in old:
            if item.get("role") and item.get("content"):
                save_message(
                    item["role"],
                    item["content"],
                    source="migrated_json",
                    metadata={"migrated": True},
                )
        print(f"Migrated {len(old)} messages from ChatLog.json to MongoDB.")
    except Exception as e:
        print(f"Migration skip: {e}")


# --- JSON fallback when MongoDB is offline ---

def _load_json_messages() -> list:
    try:
        with open(LEGACY_CHATLOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_json_messages(messages: list):
    os.makedirs("Data", exist_ok=True)
    trimmed = messages[-MAX_HISTORY:]
    with open(LEGACY_CHATLOG, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, indent=2, ensure_ascii=False)


def _save_message_json(role: str, content: str):
    msgs = _load_json_messages()
    msgs.append({"role": role, "content": content})
    _save_json_messages(msgs)


def ensure_connected():
    if USE_MONGO and not _connected:
        connect()


# Lazy connect — faster app startup (Main calls ensure on init)
