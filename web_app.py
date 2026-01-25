#!/usr/bin/env python3
"""
FastAPI + HTMX web interface for the Scottish Country Dance agent.
Uses Server-Sent Events (SSE) for real-time streaming updates.
"""

import asyncio
import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, Request, Form, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import uvicorn

from scd_agent import SCDAgent
from lesson_planner import LessonPlannerAgent
from dance_tools import mcp_client
from langchain_core.messages import HumanMessage, AIMessage
from settings import get_llm_settings, set_llm_settings, init_settings_db
from llm_providers import get_provider, list_providers

# Load environment
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="ChatSCD - Scottish Country Dance Assistant")

# Static files
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# Templates
templates = Jinja2Templates(directory="templates")

# Global agent instances
agent: Optional[SCDAgent] = None
lesson_planner: Optional[LessonPlannerAgent] = None
agent_ready = False

# Chat history database path
CHAT_DB_PATH = "data/chat_history.db"

# Admin session management
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", secrets.token_hex(32))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_COOKIE_NAME = "admin_session"
SERIALIZER = URLSafeTimedSerializer(ADMIN_SECRET_KEY)


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


def init_chat_db():
    """Initialize the chat history database."""
    os.makedirs(os.path.dirname(CHAT_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(CHAT_DB_PATH)
    cursor = conn.cursor()
    
    # Create sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            browser_id TEXT,
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
    
    conn.commit()
    conn.close()
    print(f"✅ Chat history database initialized at {CHAT_DB_PATH}")


def save_message(session_id: str, role: str, content: str, browser_id: str = None):
    """Save a message to the chat history."""
    conn = sqlite3.connect(CHAT_DB_PATH)
    cursor = conn.cursor()
    
    # Ensure session exists
    if browser_id:
        cursor.execute("""
            INSERT OR IGNORE INTO sessions (session_id, browser_id) VALUES (?, ?)
        """, (session_id, browser_id))
        # Update browser_id if session exists but browser_id is null
        cursor.execute("""
            UPDATE sessions SET browser_id = ? WHERE session_id = ? AND browser_id IS NULL
        """, (browser_id, session_id))
    else:
        cursor.execute("""
            INSERT OR IGNORE INTO sessions (session_id) VALUES (?)
        """, (session_id,))
    
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


def get_chat_history(session_id: str, limit: int = 100) -> List[Dict]:
    """Retrieve chat history for a session."""
    conn = sqlite3.connect(CHAT_DB_PATH)
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


def clear_chat_history(session_id: str):
    """Clear chat history for a session."""
    conn = sqlite3.connect(CHAT_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    
    conn.commit()
    conn.close()


def get_all_sessions(browser_id: str = None) -> List[Dict]:
    """Get all chat sessions with metadata, optionally filtered by browser_id."""
    conn = sqlite3.connect(CHAT_DB_PATH)
    cursor = conn.cursor()
    
    if browser_id:
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
            WHERE s.browser_id = ?
            GROUP BY s.session_id
            ORDER BY s.last_active DESC
        """, (browser_id,))
    else:
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
            GROUP BY s.session_id
            ORDER BY s.last_active DESC
        """)
    
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


def update_session_title(session_id: str, title: str):
    """Update the title of a session."""
    conn = sqlite3.connect(CHAT_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE sessions SET title = ? WHERE session_id = ?
    """, (title, session_id))
    
    conn.commit()
    conn.close()


def create_new_session(browser_id: str = None) -> str:
    """Create a new chat session and return its ID."""
    session_id = str(uuid.uuid4())
    conn = sqlite3.connect(CHAT_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO sessions (session_id, browser_id, title) VALUES (?, ?, ?)
    """, (session_id, browser_id, "New Chat"))
    
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
    
    await mcp_client.setup()
    agent_ready = True
    print("✅ Agent ready!")
    print("✅ Lesson Planner ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    print("🧹 Cleaning up...")
    await mcp_client.close()
    print("✅ Cleanup complete")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main page."""
    return templates.TemplateResponse("index.html", {"request": request})


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
    
    if not message:
        return {"error": "Message is required"}
    
    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events from the agent."""
        try:
            # Save user message to history
            save_message(session_id, "user", message, browser_id)
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Processing your query...', 'timestamp': datetime.now().isoformat()})}\n\n"
            
            # Check if agent needs initialization
            if not agent_ready:
                yield f"data: {json.dumps({'type': 'status', 'message': 'Initializing agent...', 'timestamp': datetime.now().isoformat()})}\n\n"
                await asyncio.sleep(0.1)
            
            # Stream from the agent graph
            config = {"configurable": {"thread_id": session_id}}
            
            async for chunk in agent.graph.astream(
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
            final_state = await agent.graph.aget_state(config)
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
                save_message(session_id, "assistant", final_response, browser_id)
            
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
    
    if not message:
        return {"error": "Message is required"}
    
    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events from the lesson planner agent."""
        try:
            # Save user message to history
            save_message(session_id, "user", message, browser_id)
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': '🎓 Planning your lesson...', 'timestamp': datetime.now().isoformat()})}\n\n"
            
            # Check if lesson planner is ready
            if not lesson_planner:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Lesson planner not initialized', 'timestamp': datetime.now().isoformat()})}\n\n"
                return
            
            # Stream from the lesson planner graph
            config = {"configurable": {"thread_id": f"lesson_{session_id}"}}
            
            async for chunk in lesson_planner.graph.astream(
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
            result = await lesson_planner.ainvoke(message, config)
            
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
                save_message(session_id, "assistant", final_response, browser_id)
            
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
async def get_history(session_id: str):
    """Get chat history for a session."""
    try:
        history = get_chat_history(session_id)
        return {"history": history}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/api/history/{session_id}")
async def delete_history(session_id: str):
    """Clear chat history for a session."""
    try:
        clear_chat_history(session_id)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sessions")
async def list_sessions(request: Request):
    """Get chat sessions for the current browser."""
    try:
        # Get browser_id from query parameter
        browser_id = request.query_params.get("browser_id")
        sessions = get_all_sessions(browser_id)
        return {"sessions": sessions}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sessions/new")
async def new_session(request: Request):
    """Create a new chat session."""
    try:
        data = await request.json()
        browser_id = data.get("browser_id")
        session_id = create_new_session(browser_id)
        return {"session_id": session_id}
    except Exception as e:
        return {"error": str(e)}


@app.put("/api/sessions/{session_id}/title")
async def update_title(session_id: str, request: Request):
    """Update session title."""
    try:
        data = await request.json()
        title = data.get("title", "")
        update_session_title(session_id, title)
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
        print("❌ OPENAI_API_KEY not set")
        exit(1)
    
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
