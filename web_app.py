#!/usr/bin/env python3
"""
FastAPI + HTMX web interface for the Scottish Country Dance agent.
Uses Server-Sent Events (SSE) for real-time streaming updates.
"""

import asyncio
import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import uvicorn

from scd_agent import SCDAgent
from dance_tools import mcp_client
from langchain_core.messages import HumanMessage

# Load environment
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="ChatSCD - Scottish Country Dance Assistant")

# Templates
templates = Jinja2Templates(directory="templates")

# Global agent instance
agent: Optional[SCDAgent] = None
agent_ready = False

# Chat history database path
CHAT_DB_PATH = "data/chat_history.db"


def init_chat_db():
    """Initialize the chat history database."""
    os.makedirs(os.path.dirname(CHAT_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(CHAT_DB_PATH)
    cursor = conn.cursor()
    
    # Create sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
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


def save_message(session_id: str, role: str, content: str):
    """Save a message to the chat history."""
    conn = sqlite3.connect(CHAT_DB_PATH)
    cursor = conn.cursor()
    
    # Ensure session exists
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


def get_all_sessions() -> List[Dict]:
    """Get all chat sessions with metadata."""
    conn = sqlite3.connect(CHAT_DB_PATH)
    cursor = conn.cursor()
    
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


def create_new_session() -> str:
    """Create a new chat session and return its ID."""
    session_id = str(uuid.uuid4())
    conn = sqlite3.connect(CHAT_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO sessions (session_id, title) VALUES (?, ?)
    """, (session_id, "New Chat"))
    
    conn.commit()
    conn.close()
    return session_id


@app.on_event("startup")
async def startup_event():
    """Initialize the agent on startup."""
    global agent, agent_ready
    print("🔧 Initializing SCD Agent...")
    init_chat_db()
    agent = SCDAgent()
    await mcp_client.setup()
    agent_ready = True
    print("✅ Agent ready!")


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
        "session_id": "optional-session-id"
    }
    """
    data = await request.json()
    message = data.get("message", "").strip()
    session_id = data.get("session_id") or str(uuid.uuid4())
    
    if not message:
        return {"error": "Message is required"}
    
    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events from the agent."""
        try:
            # Save user message to history
            save_message(session_id, "user", message)
            
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
                        else:
                            # Assistant message
                            content = getattr(msg, "content", "")
                            if isinstance(content, str) and content and not content.startswith("You are a Scottish"):
                                yield f"data: {json.dumps({'type': 'assistant', 'message': content, 'timestamp': datetime.now().isoformat()})}\n\n"
                
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
            
            # Get final state
            final_state = await agent.graph.aget_state(config)
            final_response = ""
            if final_state and hasattr(final_state, "values"):
                messages = final_state.values.get("messages", [])
                for msg in reversed(messages):
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        continue
                    content = getattr(msg, "content", "")
                    if isinstance(content, str) and content:
                        final_response = content
                        yield f"data: {json.dumps({'type': 'final', 'message': content, 'timestamp': datetime.now().isoformat()})}\n\n"
                        break
            
            # Save assistant response to history
            if final_response:
                save_message(session_id, "assistant", final_response)
            
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
async def list_sessions():
    """Get all chat sessions."""
    try:
        sessions = get_all_sessions()
        return {"sessions": sessions}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sessions/new")
async def new_session():
    """Create a new chat session."""
    try:
        session_id = create_new_session()
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
    return {
        "status": "healthy",
        "agent_ready": agent_ready,
    }


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
