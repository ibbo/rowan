#!/usr/bin/env python3
"""
FastAPI + HTMX web interface for the Scottish Country Dance agent.
Uses Server-Sent Events (SSE) for real-time streaming updates.
"""

import asyncio
import base64
import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, Request, Form, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from authlib.integrations.starlette_client import OAuth, OAuthError
from cryptography.fernet import Fernet, InvalidToken
import uvicorn

from scd_agent import SCDAgent
from lesson_planner import LessonPlannerAgent
from database import DatabasePool
from langchain_core.messages import HumanMessage, AIMessage
from settings import get_llm_settings, set_llm_settings, init_settings_db
from llm_providers import get_provider, list_providers

# Load environment
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="ChatSCD - Scottish Country Dance Assistant")

# OAuth session middleware (used by Authlib for state/PKCE handling)
OAUTH_SESSION_SECRET = os.getenv("OAUTH_SESSION_SECRET", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=OAUTH_SESSION_SECRET, max_age=86400)

# Static files
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# Templates
templates = Jinja2Templates(directory="templates")

# Global agent instances
agent: Optional[SCDAgent] = None
lesson_planner: Optional[LessonPlannerAgent] = None
agent_ready = False
agent_cache: Dict[tuple, SCDAgent] = {}
lesson_planner_cache: Dict[tuple, LessonPlannerAgent] = {}

# Chat history database path
CHAT_DB_PATH = "data/chat_history.db"

# Admin session management
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", secrets.token_hex(32))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_COOKIE_NAME = "admin_session"
SERIALIZER = URLSafeTimedSerializer(ADMIN_SECRET_KEY)

# User session + OAuth configuration
USER_SESSION_COOKIE = "user_session"
USER_SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
OAUTH_STATE_SECRET = os.getenv("OAUTH_STATE_SECRET", secrets.token_hex(32))
OAUTH_STATE_SERIALIZER = URLSafeTimedSerializer(OAUTH_STATE_SECRET)

USER_SETTINGS_SECRET = os.getenv("USER_SETTINGS_SECRET")

# Dev auth bypass (only enabled when DEV_AUTH=true)
DEV_AUTH_ENABLED = os.getenv("DEV_AUTH", "false").lower() == "true"

oauth = OAuth()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
FACEBOOK_CLIENT_ID = os.getenv("FACEBOOK_CLIENT_ID")
FACEBOOK_CLIENT_SECRET = os.getenv("FACEBOOK_CLIENT_SECRET")

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if FACEBOOK_CLIENT_ID and FACEBOOK_CLIENT_SECRET:
    oauth.register(
        name="facebook",
        client_id=FACEBOOK_CLIENT_ID,
        client_secret=FACEBOOK_CLIENT_SECRET,
        authorize_url="https://www.facebook.com/v19.0/dialog/oauth",
        access_token_url="https://graph.facebook.com/v19.0/oauth/access_token",
        api_base_url="https://graph.facebook.com/v19.0/",
        client_kwargs={"scope": "email,public_profile"},
    )


def verify_admin_session(request: Request) -> bool:
    """Verify if the request has a valid admin session."""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return False
    try:
        # Session expires after 24 hours
        data = SERIALIZER.loads(session_cookie, max_age=86400)
        return data.get("authenticated") == True
    except (BadSignature, SignatureExpired):
        return False


def create_admin_session() -> str:
    """Create a new admin session token."""
    return SERIALIZER.dumps({"authenticated": True})


def _utc_now_string() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _get_fernet() -> Fernet | None:
    if not USER_SETTINGS_SECRET:
        return None
    # Accept either a raw secret or a valid Fernet key.
    try:
        if len(USER_SETTINGS_SECRET) == 44:
            base64.urlsafe_b64decode(USER_SETTINGS_SECRET.encode())
            return Fernet(USER_SETTINGS_SECRET.encode())
    except Exception:
        pass
    key = base64.urlsafe_b64encode(hashlib.sha256(USER_SETTINGS_SECRET.encode()).digest())
    return Fernet(key)


def _encrypt_secret(value: str) -> str | None:
    if not value:
        return None
    fernet = _get_fernet()
    if not fernet:
        return None
    return fernet.encrypt(value.encode()).decode()


def _decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    fernet = _get_fernet()
    if not fernet:
        return None
    try:
        return fernet.decrypt(value.encode()).decode()
    except InvalidToken:
        return None


def init_chat_db():
    """Initialize the chat history database."""
    os.makedirs(os.path.dirname(CHAT_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(CHAT_DB_PATH)
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            provider_user_id TEXT NOT NULL,
            email TEXT,
            name TEXT,
            avatar_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(provider, provider_user_id)
        )
    """)

    # Create user sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Create user settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY,
            preferred_provider TEXT,
            preferred_model TEXT,
            preferred_temperature REAL,
            openai_api_key TEXT,
            google_api_key TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Create sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            browser_id TEXT,
            user_id TEXT,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Add browser_id column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN browser_id TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add title column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN title TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Add user_id column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)
    
    # Create index for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_session 
        ON messages(session_id, timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sessions_user
        ON sessions(user_id, last_active)
    """)
    
    conn.commit()
    conn.close()
    print(f"✅ Chat history database initialized at {CHAT_DB_PATH}")


def _get_chat_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(CHAT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_or_update_user(
    provider: str,
    provider_user_id: str,
    email: str | None,
    name: str | None,
    avatar_url: str | None,
) -> dict:
    """Create or update a user record and return the user dict."""
    conn = _get_chat_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE provider = ? AND provider_user_id = ?",
        (provider, provider_user_id),
    )
    row = cursor.fetchone()
    if row:
        cursor.execute(
            """
            UPDATE users
            SET email = ?, name = ?, avatar_url = ?, last_login = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (email, name, avatar_url, row["id"]),
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE id = ?", (row["id"],))
        user_row = cursor.fetchone()
    else:
        user_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO users (id, provider, provider_user_id, email, name, avatar_url)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, provider, provider_user_id, email, name, avatar_url),
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()

    conn.close()
    return dict(user_row) if user_row else {}


def create_user_session(user_id: str) -> tuple[str, str]:
    """Create a new user session token and expiry."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(seconds=USER_SESSION_TTL_SECONDS)
    expires_str = expires_at.strftime("%Y-%m-%d %H:%M:%S")

    conn = _get_chat_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO user_sessions (session_token, user_id, expires_at)
        VALUES (?, ?, ?)
        """,
        (token, user_id, expires_str),
    )
    conn.commit()
    conn.close()
    return token, expires_str


def delete_user_session(token: str):
    conn = _get_chat_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_sessions WHERE session_token = ?", (token,))
    conn.commit()
    conn.close()


def get_user_by_session_token(token: str) -> dict | None:
    conn = _get_chat_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT u.*
        FROM user_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.session_token = ?
          AND s.expires_at > ?
        """,
        (token, _utc_now_string()),
    )
    row = cursor.fetchone()
    if not row:
        # Cleanup expired session token
        cursor.execute("DELETE FROM user_sessions WHERE session_token = ?", (token,))
        conn.commit()
        conn.close()
        return None

    conn.close()
    return dict(row)


def get_current_user(request: Request) -> dict | None:
    token = request.cookies.get(USER_SESSION_COOKIE)
    if not token:
        return None
    return get_user_by_session_token(token)


def require_user(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def link_sessions_to_user(user_id: str, browser_id: str | None):
    if not browser_id:
        return
    conn = _get_chat_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE sessions
        SET user_id = ?
        WHERE browser_id = ? AND user_id IS NULL
        """,
        (user_id, browser_id),
    )
    conn.commit()
    conn.close()


def get_user_settings(user_id: str, include_secrets: bool = False) -> dict:
    conn = _get_chat_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "preferred_provider": None,
            "preferred_model": None,
            "preferred_temperature": None,
            "openai_api_key": None,
            "google_api_key": None,
            "openai_key_set": False,
            "google_key_set": False,
        }

    data = dict(row)
    openai_key = _decrypt_secret(data.get("openai_api_key")) if include_secrets else None
    google_key = _decrypt_secret(data.get("google_api_key")) if include_secrets else None

    return {
        "preferred_provider": data.get("preferred_provider"),
        "preferred_model": data.get("preferred_model"),
        "preferred_temperature": data.get("preferred_temperature"),
        "openai_api_key": openai_key if include_secrets else None,
        "google_api_key": google_key if include_secrets else None,
        "openai_key_set": bool(data.get("openai_api_key")),
        "google_key_set": bool(data.get("google_api_key")),
    }


def upsert_user_settings(
    user_id: str,
    preferred_provider: str | None,
    preferred_model: str | None,
    preferred_temperature: float | None,
    openai_api_key: str | None,
    google_api_key: str | None,
    clear_openai: bool,
    clear_google: bool,
    clear_provider: bool,
    clear_model: bool,
    clear_temperature: bool,
):
    conn = _get_chat_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM user_settings WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone() is not None

    updates = []
    params: list = []

    if clear_provider:
        updates.append("preferred_provider = NULL")
    elif preferred_provider is not None:
        updates.append("preferred_provider = ?")
        params.append(preferred_provider)
    if clear_model:
        updates.append("preferred_model = NULL")
    elif preferred_model is not None:
        updates.append("preferred_model = ?")
        params.append(preferred_model)
    if clear_temperature:
        updates.append("preferred_temperature = NULL")
    elif preferred_temperature is not None:
        updates.append("preferred_temperature = ?")
        params.append(preferred_temperature)

    if clear_openai:
        updates.append("openai_api_key = NULL")
    elif openai_api_key:
        encrypted = _encrypt_secret(openai_api_key)
        updates.append("openai_api_key = ?")
        params.append(encrypted)

    if clear_google:
        updates.append("google_api_key = NULL")
    elif google_api_key:
        encrypted = _encrypt_secret(google_api_key)
        updates.append("google_api_key = ?")
        params.append(encrypted)

    updates.append("updated_at = CURRENT_TIMESTAMP")

    if not exists:
        cursor.execute(
            """
            INSERT INTO user_settings (user_id, preferred_provider, preferred_model, preferred_temperature, openai_api_key, google_api_key)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                preferred_provider,
                preferred_model,
                preferred_temperature,
                _encrypt_secret(openai_api_key) if openai_api_key else None,
                _encrypt_secret(google_api_key) if google_api_key else None,
            ),
        )
        if clear_openai:
            cursor.execute("UPDATE user_settings SET openai_api_key = NULL WHERE user_id = ?", (user_id,))
        if clear_google:
            cursor.execute("UPDATE user_settings SET google_api_key = NULL WHERE user_id = ?", (user_id,))
    elif updates:
        params.append(user_id)
        cursor.execute(
            f"UPDATE user_settings SET {', '.join(updates)} WHERE user_id = ?",
            tuple(params),
        )

    conn.commit()
    conn.close()


def get_effective_llm_settings(user_id: str | None) -> tuple[dict, str | None]:
    base = get_llm_settings()
    if not user_id:
        return base, None

    user_settings = get_user_settings(user_id, include_secrets=True)
    provider = user_settings["preferred_provider"] or base["provider"]
    model = user_settings["preferred_model"]
    if not model:
        if provider == base["provider"]:
            model = base["model"]
        else:
            try:
                provider_instance = get_provider(provider)
                models = provider_instance.list_available_models()
                model = models[0]["id"] if models else base["model"]
            except ValueError:
                provider = base["provider"]
                model = base["model"]
    temperature = (
        float(user_settings["preferred_temperature"])
        if user_settings["preferred_temperature"] is not None
        else base["temperature"]
    )

    api_key = None
    if provider == "openai":
        api_key = user_settings.get("openai_api_key")
    elif provider == "google":
        api_key = user_settings.get("google_api_key")

    return {
        "provider": provider,
        "model": model,
        "temperature": temperature,
    }, api_key


def _hash_api_key(api_key: str | None) -> str:
    if not api_key:
        return "none"
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_agent_for_settings(llm_settings: dict, api_key: str | None) -> SCDAgent:
    key = (
        llm_settings["provider"],
        llm_settings["model"],
        llm_settings["temperature"],
        _hash_api_key(api_key),
    )
    if key in agent_cache:
        return agent_cache[key]

    new_agent = SCDAgent(
        provider=llm_settings["provider"],
        model=llm_settings["model"],
        temperature=llm_settings["temperature"],
        api_key=api_key,
    )
    agent_cache[key] = new_agent
    return new_agent


def get_lesson_planner_for_settings(llm_settings: dict, api_key: str | None) -> LessonPlannerAgent:
    key = (
        llm_settings["provider"],
        llm_settings["model"],
        llm_settings["temperature"],
        _hash_api_key(api_key),
    )
    if key in lesson_planner_cache:
        return lesson_planner_cache[key]

    new_planner = LessonPlannerAgent(
        provider=llm_settings["provider"],
        model=llm_settings["model"],
        temperature=llm_settings["temperature"],
        api_key=api_key,
    )
    lesson_planner_cache[key] = new_planner
    return new_planner


def _ensure_session_access(
    session_id: str,
    user_id: str | None,
    browser_id: str | None,
    link_user: bool = False,
) -> bool:
    conn = _get_chat_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT session_id, user_id, browser_id FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    allowed = False
    if user_id:
        if row["user_id"] == user_id:
            allowed = True
        elif row["user_id"] is None and row["browser_id"] and browser_id == row["browser_id"]:
            allowed = True
            if link_user:
                cursor.execute(
                    "UPDATE sessions SET user_id = ? WHERE session_id = ?",
                    (user_id, session_id),
                )
                conn.commit()
    else:
        if row["user_id"] is None:
            if row["browser_id"] is None:
                allowed = True
            elif browser_id and row["browser_id"] == browser_id:
                allowed = True

    conn.close()
    return allowed


def save_message(
    session_id: str,
    role: str,
    content: str,
    browser_id: str | None = None,
    user_id: str | None = None,
):
    """Save a message to the chat history."""
    conn = _get_chat_conn()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT session_id, user_id, browser_id FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    row = cursor.fetchone()

    if row:
        if user_id:
            if row["user_id"] and row["user_id"] != user_id:
                conn.close()
                raise HTTPException(status_code=403, detail="Session belongs to another user")
            if not row["user_id"]:
                if row["browser_id"] and row["browser_id"] != browser_id:
                    conn.close()
                    raise HTTPException(status_code=403, detail="Session belongs to another browser")
                cursor.execute(
                    "UPDATE sessions SET user_id = ?, browser_id = COALESCE(browser_id, ?) WHERE session_id = ?",
                    (user_id, browser_id, session_id),
                )
        else:
            if row["user_id"]:
                conn.close()
                raise HTTPException(status_code=403, detail="Session belongs to another user")
            if row["browser_id"] and row["browser_id"] != browser_id:
                conn.close()
                raise HTTPException(status_code=403, detail="Session belongs to another browser")
            if browser_id and not row["browser_id"]:
                cursor.execute(
                    "UPDATE sessions SET browser_id = ? WHERE session_id = ?",
                    (browser_id, session_id),
                )
    else:
        cursor.execute(
            """
            INSERT INTO sessions (session_id, browser_id, user_id, title)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, browser_id, user_id, "New Chat"),
        )
    
    # Update last active time
    cursor.execute("""
        UPDATE sessions SET last_active = CURRENT_TIMESTAMP WHERE session_id = ?
    """, (session_id,))
    
    # Insert message
    cursor.execute("""
        INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)
    """, (session_id, role, content))
    
    conn.commit()
    conn.close()


def get_chat_history(
    session_id: str,
    limit: int = 100,
    user_id: str | None = None,
    browser_id: str | None = None,
) -> List[Dict]:
    """Retrieve chat history for a session."""
    if not _ensure_session_access(session_id, user_id, browser_id, link_user=True):
        raise HTTPException(status_code=403, detail="Unauthorized session access")

    conn = _get_chat_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT role, content, timestamp 
        FROM messages 
        WHERE session_id = ? 
        ORDER BY timestamp ASC
        LIMIT ?
    """, (session_id, limit))
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "role": row[0],
            "content": row[1],
            "timestamp": row[2]
        })
    
    conn.close()
    return messages


def clear_chat_history(
    session_id: str,
    user_id: str | None = None,
    browser_id: str | None = None,
):
    """Clear chat history for a session."""
    if not _ensure_session_access(session_id, user_id, browser_id):
        raise HTTPException(status_code=403, detail="Unauthorized session access")

    conn = _get_chat_conn()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    
    conn.commit()
    conn.close()


def get_all_sessions(user_id: str | None = None, browser_id: str | None = None) -> List[Dict]:
    """Get all chat sessions with metadata, filtered by user_id or browser_id."""
    conn = _get_chat_conn()
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute("""
            SELECT 
                s.session_id,
                s.title,
                s.created_at,
                s.last_active,
                COUNT(m.id) as message_count,
                (
                    SELECT content 
                    FROM messages 
                    WHERE session_id = s.session_id AND role = 'user'
                    ORDER BY timestamp ASC 
                    LIMIT 1
                ) as first_message
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            WHERE s.user_id = ?
            GROUP BY s.session_id
            ORDER BY s.last_active DESC
        """, (user_id,))
    elif browser_id:
        cursor.execute("""
            SELECT 
                s.session_id,
                s.title,
                s.created_at,
                s.last_active,
                COUNT(m.id) as message_count,
                (
                    SELECT content 
                    FROM messages 
                    WHERE session_id = s.session_id AND role = 'user'
                    ORDER BY timestamp ASC 
                    LIMIT 1
                ) as first_message
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            WHERE s.browser_id = ? AND (s.user_id IS NULL OR s.user_id = '')
            GROUP BY s.session_id
            ORDER BY s.last_active DESC
        """, (browser_id,))
    else:
        # No user_id or browser_id: return empty list
        conn.close()
        return []
    
    sessions = []
    for row in cursor.fetchall():
        # Generate title from first message if not set
        title = row[1]
        if not title and row[5]:  # If no title but has first message
            # Use first 50 chars of first message as title
            title = row[5][:50] + ("..." if len(row[5]) > 50 else "")
        elif not title:
            title = "New Chat"
        
        sessions.append({
            "session_id": row[0],
            "title": title,
            "created_at": row[2],
            "last_active": row[3],
            "message_count": row[4],
            "preview": row[5][:100] if row[5] else "No messages yet"
        })
    
    conn.close()
    return sessions


def update_session_title(
    session_id: str,
    title: str,
    user_id: str | None = None,
    browser_id: str | None = None,
):
    """Update the title of a session."""
    if not _ensure_session_access(session_id, user_id, browser_id, link_user=True):
        raise HTTPException(status_code=403, detail="Unauthorized session access")

    conn = _get_chat_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE sessions SET title = ? WHERE session_id = ?
    """, (title, session_id))
    
    conn.commit()
    conn.close()


def create_new_session(browser_id: str | None = None, user_id: str | None = None) -> str:
    """Create a new chat session and return its ID."""
    session_id = str(uuid.uuid4())
    conn = _get_chat_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO sessions (session_id, browser_id, user_id, title) VALUES (?, ?, ?, ?)
    """, (session_id, browser_id, user_id, "New Chat"))
    
    conn.commit()
    conn.close()
    return session_id


@app.on_event("startup")
async def startup_event():
    """Initialize the agents on startup."""
    global agent, lesson_planner, agent_ready
    print("🔧 Initializing SCD Agent...")
    init_chat_db()
    init_settings_db()
    
    # Load LLM settings
    llm_settings = get_llm_settings()
    print(f"📊 Using LLM: {llm_settings['provider']} / {llm_settings['model']}")
    
    try:
        # Create agents with configured provider/model
        agent = SCDAgent(
            provider=llm_settings["provider"],
            model=llm_settings["model"],
            temperature=llm_settings["temperature"]
        )
        
        # Initialize lesson planner agent
        lesson_planner = LessonPlannerAgent(
            provider=llm_settings["provider"],
            model=llm_settings["model"],
            temperature=llm_settings["temperature"]
        )

        agent_ready = True
        agent_cache[(
            llm_settings["provider"],
            llm_settings["model"],
            llm_settings["temperature"],
            _hash_api_key(None),
        )] = agent
        lesson_planner_cache[(
            llm_settings["provider"],
            llm_settings["model"],
            llm_settings["temperature"],
            _hash_api_key(None),
        )] = lesson_planner
        print("✅ Agent ready!")
        print("✅ Lesson Planner ready!")
    except RuntimeError as e:
        agent_ready = False
        print(f"⚠️ Default agent not initialized: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    print("🧹 Cleaning up...")
    pool = await DatabasePool.get_instance()
    await pool.close_all()
    print("✅ Cleanup complete")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main page."""
    user = get_current_user(request)
    oauth_providers = {
        "google": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "facebook": bool(FACEBOOK_CLIENT_ID and FACEBOOK_CLIENT_SECRET),
    }
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "current_user": user,
            "oauth_providers": oauth_providers,
            "dev_auth_enabled": DEV_AUTH_ENABLED,
        },
    )


@app.post("/api/query")
async def query_stream(request: Request):
    """
    Stream agent responses using Server-Sent Events (SSE).
    
    Expected JSON body:
    {
        "message": "Find me some 32-bar reels",
        "session_id": "optional-session-id",
        "browser_id": "optional-browser-id"
    }
    """
    data = await request.json()
    message = data.get("message", "").strip()
    session_id = data.get("session_id") or str(uuid.uuid4())
    browser_id = data.get("browser_id")
    user = get_current_user(request)
    user_id = user["id"] if user else None
    llm_settings, api_key = get_effective_llm_settings(user_id)
    
    if not message:
        return {"error": "Message is required"}
    
    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events from the agent."""
        try:
            try:
                agent_instance = get_agent_for_settings(llm_settings, api_key)
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'timestamp': datetime.now().isoformat()})}\n\n"
                return

            # Save user message to history
            save_message(session_id, "user", message, browser_id, user_id)
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Processing your query...', 'timestamp': datetime.now().isoformat()})}\n\n"
            
            # Stream from the agent graph
            config = {"configurable": {"thread_id": session_id}}
            
            async for chunk in agent_instance.graph.astream(
                {
                    "messages": [HumanMessage(content=message)],
                    "is_scd_query": False,
                    "route": ""
                },
                config
            ):
                if not isinstance(chunk, dict):
                    continue
                
                # Handle prompt checker
                if "prompt_checker" in chunk:
                    checker_data = chunk["prompt_checker"]
                    if checker_data.get("route") == "reject":
                        yield f"data: {json.dumps({'type': 'status', 'message': '❌ Query rejected - not about Scottish Country Dancing', 'timestamp': datetime.now().isoformat()})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'status', 'message': '✅ Query accepted - processing...', 'timestamp': datetime.now().isoformat()})}\n\n"
                
                # Handle dance planner
                if "dance_planner" in chunk:
                    planner_data = chunk["dance_planner"]
                    messages = planner_data.get("messages", [])
                    
                    for msg in messages:
                        # Check for tool calls
                        tool_calls = getattr(msg, "tool_calls", None)
                        if tool_calls:
                            for call in tool_calls:
                                tool_name = call.get("name", "tool")
                                tool_args = call.get("args", {})
                                
                                yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name, 'args': tool_args, 'timestamp': datetime.now().isoformat()})}\n\n"
                        # Note: We don't stream intermediate assistant messages here
                        # The final response will be sent after all tool calls complete
                
                # Handle tool executor
                if "tool_executor" in chunk:
                    executor_data = chunk["tool_executor"]
                    messages = executor_data.get("messages", [])
                    
                    for msg in messages:
                        call_id = getattr(msg, "tool_call_id", None)
                        content = getattr(msg, "content", "")
                        
                        # Parse tool results
                        try:
                            result = json.loads(content) if isinstance(content, str) else content
                            
                            # Extract dance information
                            dances = []
                            if isinstance(result, list):
                                dances = result[:5]  # First 5 dances
                            elif isinstance(result, dict):
                                if "dance" in result:
                                    dances = [result["dance"]]
                            
                            yield f"data: {json.dumps({'type': 'tool_result', 'dances': dances, 'timestamp': datetime.now().isoformat()})}\n\n"
                        except:
                            yield f"data: {json.dumps({'type': 'tool_result', 'result': str(content)[:200], 'timestamp': datetime.now().isoformat()})}\n\n"
                
                # Handle rejection
                if "rejection_handler" in chunk:
                    rejection_data = chunk["rejection_handler"]
                    messages = rejection_data.get("messages", [])
                    for msg in messages:
                        content = getattr(msg, "content", "")
                        if content:
                            yield f"data: {json.dumps({'type': 'final', 'message': content, 'timestamp': datetime.now().isoformat()})}\n\n"
                            return
            
            # Get final state and extract the final assistant response
            final_state = await agent_instance.graph.aget_state(config)
            final_response = ""
            if final_state and hasattr(final_state, "values"):
                messages = final_state.values.get("messages", [])
                # Find the last AI message that's not a tool call and not a system message
                for msg in reversed(messages):
                    # Skip messages with tool calls
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        continue
                    # Skip system messages
                    if hasattr(msg, "type") and msg.type == "system":
                        continue
                    # Get content and check if it's a substantive response
                    content = getattr(msg, "content", "")
                    if isinstance(content, str) and content and not content.startswith("You are"):
                        final_response = content
                        yield f"data: {json.dumps({'type': 'final', 'message': content, 'timestamp': datetime.now().isoformat()})}\n\n"
                        break
            
            # Save assistant response to history
            if final_response:
                save_message(session_id, "assistant", final_response, browser_id, user_id)
            
            # Send completion event
            yield f"data: {json.dumps({'type': 'complete', 'timestamp': datetime.now().isoformat()})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'timestamp': datetime.now().isoformat()})}\n\n"
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@app.post("/api/lesson-plan")
async def lesson_plan_stream(request: Request):
    """
    Stream lesson planner responses using Server-Sent Events (SSE).
    
    Expected JSON body:
    {
        "message": "Plan a 45 minute lesson focusing on strathspey poussette",
        "session_id": "optional-session-id",
        "browser_id": "optional-browser-id"
    }
    """
    data = await request.json()
    message = data.get("message", "").strip()
    session_id = data.get("session_id") or str(uuid.uuid4())
    browser_id = data.get("browser_id")
    user = get_current_user(request)
    user_id = user["id"] if user else None
    llm_settings, api_key = get_effective_llm_settings(user_id)
    
    if not message:
        return {"error": "Message is required"}
    
    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events from the lesson planner agent."""
        try:
            try:
                planner_instance = get_lesson_planner_for_settings(llm_settings, api_key)
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'timestamp': datetime.now().isoformat()})}\n\n"
                return

            # Save user message to history
            save_message(session_id, "user", message, browser_id, user_id)
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': '🎓 Planning your lesson...', 'timestamp': datetime.now().isoformat()})}\n\n"
            
            # Stream from the lesson planner graph
            config = {"configurable": {"thread_id": f"lesson_{session_id}"}}
            
            async for chunk in planner_instance.graph.astream(
                {
                    "messages": [HumanMessage(content=message)],
                    "lesson_plan": None,
                    "plan_status": "gathering"
                },
                config
            ):
                if not isinstance(chunk, dict):
                    continue
                
                # Handle planner node
                if "planner" in chunk:
                    planner_data = chunk["planner"]
                    messages = planner_data.get("messages", [])
                    
                    for msg in messages:
                        # Check for tool calls
                        tool_calls = getattr(msg, "tool_calls", None)
                        if tool_calls:
                            for call in tool_calls:
                                tool_name = call.get("name", "tool")
                                tool_args = call.get("args", {})
                                
                                # Friendly tool status messages
                                status_msg = {
                                    "find_dances": "🔍 Searching for dances...",
                                    "get_full_crib": f"📜 Getting full crib for dance {tool_args.get('dance_id', '')}...",
                                    "get_teaching_points_for_dance": f"📚 Getting teaching points...",
                                    "search_cribs": f"🔍 Searching cribs for '{tool_args.get('query', '')}'...",
                                    "search_manual": "📖 Consulting RSCDS manual...",
                                    "save_lesson_plan": "💾 Saving lesson plan...",
                                }.get(tool_name, f"🔧 Using {tool_name}...")
                                
                                yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name, 'args': tool_args, 'status': status_msg, 'timestamp': datetime.now().isoformat()})}\n\n"
                
                # Handle tool results
                if "tools" in chunk:
                    tools_data = chunk["tools"]
                    messages = tools_data.get("messages", [])
                    
                    for msg in messages:
                        tool_name = getattr(msg, "name", "")
                        content = getattr(msg, "content", "")
                        
                        yield f"data: {json.dumps({'type': 'tool_complete', 'tool': tool_name, 'timestamp': datetime.now().isoformat()})}\n\n"
            
            # Get final state to extract the lesson plan
            # The lesson planner returns formatted markdown in its final message
            final_response = ""
            lesson_markdown = ""
            
            # Re-invoke to get full response (since we can't get_state with compiled graph)
            result = await planner_instance.ainvoke(message, config)
            
            if result and "messages" in result:
                # Find the last AI message with content
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage) and msg.content:
                        final_response = msg.content
                        # Check if this looks like a lesson plan (contains markdown headers)
                        if "##" in final_response or "# " in final_response:
                            lesson_markdown = final_response
                        break
            
            # Send the final response
            if final_response:
                yield f"data: {json.dumps({'type': 'final', 'message': final_response, 'lesson_markdown': lesson_markdown, 'timestamp': datetime.now().isoformat()})}\n\n"
                save_message(session_id, "assistant", final_response, browser_id, user_id)
            
            # Send completion
            yield f"data: {json.dumps({'type': 'complete', 'timestamp': datetime.now().isoformat()})}\n\n"
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'timestamp': datetime.now().isoformat()})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/api/history/{session_id}")
async def get_history(session_id: str, request: Request):
    """Get chat history for a session."""
    try:
        browser_id = request.query_params.get("browser_id")
        user = get_current_user(request)
        user_id = user["id"] if user else None
        history = get_chat_history(session_id, user_id=user_id, browser_id=browser_id)
        return {"history": history}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/api/history/{session_id}")
async def delete_history(session_id: str, request: Request):
    """Clear chat history for a session."""
    try:
        browser_id = request.query_params.get("browser_id")
        user = get_current_user(request)
        user_id = user["id"] if user else None
        clear_chat_history(session_id, user_id=user_id, browser_id=browser_id)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sessions")
async def list_sessions(request: Request):
    """Get chat sessions for the current browser."""
    try:
        user = get_current_user(request)
        browser_id = request.query_params.get("browser_id")
        user_id = user["id"] if user else None
        sessions = get_all_sessions(user_id=user_id, browser_id=browser_id)
        return {"sessions": sessions}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sessions/new")
async def new_session(request: Request):
    """Create a new chat session."""
    try:
        data = await request.json()
        browser_id = data.get("browser_id")
        user = get_current_user(request)
        user_id = user["id"] if user else None
        session_id = create_new_session(browser_id, user_id=user_id)
        return {"session_id": session_id}
    except Exception as e:
        return {"error": str(e)}


@app.put("/api/sessions/{session_id}/title")
async def update_title(session_id: str, request: Request):
    """Update session title."""
    try:
        data = await request.json()
        title = data.get("title", "")
        user = get_current_user(request)
        browser_id = data.get("browser_id")
        user_id = user["id"] if user else None
        update_session_title(session_id, title, user_id=user_id, browser_id=browser_id)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
async def health():
    """Health check endpoint."""
    llm_settings = get_llm_settings()
    return {
        "status": "healthy",
        "agent_ready": agent_ready,
        "llm_provider": llm_settings["provider"],
        "llm_model": llm_settings["model"],
    }


# =============================================================================
# User Auth + Settings Routes
# =============================================================================

def _get_oauth_client(provider: str):
    if provider not in ("google", "facebook"):
        raise HTTPException(status_code=404, detail="Unknown provider")
    client = oauth.create_client(provider)
    if not client:
        raise HTTPException(status_code=500, detail=f"{provider.title()} OAuth not configured")
    return client


@app.get("/auth/dev-login")
async def dev_login(request: Request):
    """Development/test login route - creates a test user without OAuth."""
    if not DEV_AUTH_ENABLED:
        raise HTTPException(status_code=404, detail="Dev auth not enabled")
    
    # Get browser_id from query params
    browser_id = request.query_params.get("browser_id")
    next_url = request.query_params.get("next", "/")
    if not next_url.startswith("/"):
        next_url = "/"
    
    # Create or get test user
    user = create_or_update_user(
        provider="dev",
        provider_user_id="dev-test-user",
        email="dev@test.local",
        name="Test User",
        avatar_url=None,
    )
    
    # Link browser sessions to this user
    link_sessions_to_user(user["id"], browser_id)
    
    # Create user session
    session_token, _expires_at = create_user_session(user["id"])
    
    # Set cookie and redirect
    response = RedirectResponse(url=next_url, status_code=302)
    response.set_cookie(
        key=USER_SESSION_COOKIE,
        value=session_token,
        httponly=True,
        samesite="lax",
        max_age=USER_SESSION_TTL_SECONDS,
        secure=request.url.scheme == "https",
    )
    return response


@app.get("/auth/login/{provider}")
async def oauth_login(provider: str, request: Request):
    client = _get_oauth_client(provider)

    browser_id = request.query_params.get("browser_id")
    next_url = request.query_params.get("next", "/")
    if not next_url.startswith("/"):
        next_url = "/"
    state = OAUTH_STATE_SERIALIZER.dumps(
        {"browser_id": browser_id, "next": next_url}
    )
    redirect_uri = request.url_for("oauth_callback", provider=provider)

    return await client.authorize_redirect(request, redirect_uri, state=state)


@app.get("/auth/callback/{provider}")
async def oauth_callback(provider: str, request: Request):
    client = _get_oauth_client(provider)
    state_token = request.query_params.get("state")
    state_data = {}
    if state_token:
        try:
            state_data = OAUTH_STATE_SERIALIZER.loads(state_token, max_age=600)
        except Exception:
            state_data = {}

    browser_id = state_data.get("browser_id")
    next_url = state_data.get("next") or "/"
    if not next_url.startswith("/"):
        next_url = "/"

    try:
        token = await client.authorize_access_token(request)
    except OAuthError as e:
        return templates.TemplateResponse(
            "auth_error.html",
            {"request": request, "message": f"OAuth error: {e.error}"},
        )

    if provider == "google":
        user_info = await client.get("https://openidconnect.googleapis.com/v1/userinfo", token=token)
        profile = user_info.json()
        provider_user_id = profile.get("sub")
        email = profile.get("email")
        name = profile.get("name")
        avatar_url = profile.get("picture")
    else:
        user_info = await client.get("me?fields=id,name,email,picture", token=token)
        profile = user_info.json()
        provider_user_id = profile.get("id")
        email = profile.get("email")
        name = profile.get("name")
        avatar_url = None
        picture = profile.get("picture", {}).get("data", {})
        if picture:
            avatar_url = picture.get("url")

    if not provider_user_id:
        return templates.TemplateResponse(
            "auth_error.html",
            {"request": request, "message": "Unable to load user profile from provider."},
        )

    user = create_or_update_user(
        provider=provider,
        provider_user_id=provider_user_id,
        email=email,
        name=name,
        avatar_url=avatar_url,
    )

    link_sessions_to_user(user["id"], browser_id)

    session_token, _expires_at = create_user_session(user["id"])
    response = RedirectResponse(url=next_url, status_code=302)
    response.set_cookie(
        key=USER_SESSION_COOKIE,
        value=session_token,
        httponly=True,
        samesite="lax",
        max_age=USER_SESSION_TTL_SECONDS,
        secure=request.url.scheme == "https",
    )
    return response


@app.get("/auth/logout")
async def oauth_logout(request: Request):
    token = request.cookies.get(USER_SESSION_COOKIE)
    if token:
        delete_user_session(token)
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(USER_SESSION_COOKIE)
    return response


@app.get("/settings", response_class=HTMLResponse)
async def user_settings_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    settings = get_user_settings(user["id"])
    default_llm = get_llm_settings()
    providers = list_providers()
    models_data = {}
    for p in providers:
        provider_instance = get_provider(p["id"])
        models_data[p["id"]] = provider_instance.list_available_models()

    return templates.TemplateResponse(
        "user_settings.html",
        {
            "request": request,
            "user": user,
            "settings": settings,
            "providers": providers,
            "models_json": json.dumps(models_data),
            "settings_secret_configured": bool(USER_SETTINGS_SECRET),
            "default_llm": default_llm,
        },
    )


@app.post("/settings")
async def update_user_settings(request: Request):
    user = require_user(request)
    form = await request.form()

    preferred_provider_raw = form.get("preferred_provider", "")
    preferred_model_raw = form.get("preferred_model", "")
    preferred_temperature_raw = form.get("preferred_temperature", "")
    openai_api_key = form.get("openai_api_key") or None
    google_api_key = form.get("google_api_key") or None
    clear_openai = form.get("clear_openai") == "on"
    clear_google = form.get("clear_google") == "on"

    clear_provider = preferred_provider_raw == ""
    clear_model = preferred_model_raw == ""
    clear_temperature = preferred_temperature_raw == ""

    preferred_provider = None if clear_provider else preferred_provider_raw
    preferred_model = None if clear_model else preferred_model_raw

    temperature_val = None
    if preferred_temperature_raw:
        try:
            temperature_val = float(preferred_temperature_raw)
        except ValueError:
            temperature_val = None
            clear_temperature = True

    if (openai_api_key or google_api_key) and not USER_SETTINGS_SECRET:
        providers = list_providers()
        return templates.TemplateResponse(
            "user_settings.html",
            {
                "request": request,
                "user": user,
                "settings": get_user_settings(user["id"]),
                "providers": providers,
                "models_json": json.dumps({
                    p["id"]: get_provider(p["id"]).list_available_models()
                    for p in providers
                }),
                "settings_secret_configured": False,
                "default_llm": get_llm_settings(),
                "error": "USER_SETTINGS_SECRET is not configured; cannot store API keys.",
            },
            status_code=400,
        )

    upsert_user_settings(
        user_id=user["id"],
        preferred_provider=preferred_provider,
        preferred_model=preferred_model,
        preferred_temperature=temperature_val,
        openai_api_key=openai_api_key,
        google_api_key=google_api_key,
        clear_openai=clear_openai,
        clear_google=clear_google,
        clear_provider=clear_provider,
        clear_model=clear_model,
        clear_temperature=clear_temperature,
    )

    return RedirectResponse(url="/settings", status_code=302)

# =============================================================================
# Admin Routes
# =============================================================================

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, error: str = None, message: str = None):
    """Render the admin login page."""
    # If already authenticated, redirect to dashboard
    if verify_admin_session(request):
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "error": error,
        "message": message
    })


@app.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...)):
    """Process admin login."""
    if not ADMIN_PASSWORD:
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": "Admin password not configured. Set ADMIN_PASSWORD in .env file."
        })
    
    if password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/admin", status_code=302)
        session_token = create_admin_session()
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_token,
            httponly=True,
            samesite="lax",
            max_age=86400  # 24 hours
        )
        return response
    else:
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": "Invalid password. Please try again."
        })


@app.get("/admin/logout")
async def admin_logout():
    """Log out of admin session."""
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Render the admin dashboard."""
    if not verify_admin_session(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    # Get current settings
    llm_settings = get_llm_settings()
    providers = list_providers()
    
    # Build models data for JavaScript
    models_data = {}
    for p in providers:
        provider_instance = get_provider(p["id"])
        models_data[p["id"]] = provider_instance.list_available_models()
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "current_provider": llm_settings["provider"],
        "current_model": llm_settings["model"],
        "current_temperature": llm_settings["temperature"],
        "providers": providers,
        "models_json": json.dumps(models_data)
    })


@app.post("/admin/api/settings")
async def update_admin_settings(request: Request):
    """Update LLM settings."""
    if not verify_admin_session(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        data = await request.json()
        provider = data.get("provider")
        model = data.get("model")
        temperature = float(data.get("temperature", 0))
        
        # Validate provider
        try:
            get_provider(provider)
        except ValueError as e:
            return {"success": False, "message": str(e)}
        
        # Save settings
        set_llm_settings(provider, model, temperature)
        
        return {"success": True, "message": "Settings saved. Restart server to apply."}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/admin/api/test-connection")
async def test_llm_connection(request: Request):
    """Test LLM connection with given settings."""
    if not verify_admin_session(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        data = await request.json()
        provider_name = data.get("provider")
        model = data.get("model")
        api_key = data.get("api_key")  # Optional override
        
        # Get provider and test connection
        provider = get_provider(provider_name)
        success, message = provider.validate_connection(model, api_key)
        
        return {"success": success, "message": message}
    except Exception as e:
        return {"success": False, "message": f"Test failed: {str(e)}"}


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ OPENAI_API_KEY not set. Users must provide their own API keys.")
    
    db_path = os.environ.get("SCDDB_SQLITE", "data/scddb/scddb.sqlite")
    if not Path(db_path).exists():
        print(f"❌ Database not found at {db_path}")
        exit(1)
    
    print("🚀 Starting ChatSCD Web Server...")
    print("📍 http://localhost:8000")
    
    uvicorn.run(
        "web_app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
