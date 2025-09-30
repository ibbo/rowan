#!/usr/bin/env python3
"""
FastAPI + HTMX web interface for the Scottish Country Dance agent.
Uses Server-Sent Events (SSE) for real-time streaming updates.
"""

import asyncio
import json
import os
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

# Session storage (in production, use Redis or similar)
sessions: Dict[str, Dict] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize the agent on startup."""
    global agent, agent_ready
    print("🔧 Initializing SCD Agent...")
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
            if final_state and hasattr(final_state, "values"):
                messages = final_state.values.get("messages", [])
                for msg in reversed(messages):
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        continue
                    content = getattr(msg, "content", "")
                    if isinstance(content, str) and content:
                        yield f"data: {json.dumps({'type': 'final', 'message': content, 'timestamp': datetime.now().isoformat()})}\n\n"
                        break
            
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
