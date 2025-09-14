#!/usr/bin/env python3
"""
Gradio web interface for the Scottish Country Dance Agent.

This creates a web UI that can be hosted on a VPS for public access.
"""

import asyncio
import hashlib
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import List, Tuple, AsyncIterator, Dict, Any

import gradio as gr
from dotenv import load_dotenv

# Import our existing dance agent
from dance_agent import create_dance_agent, mcp_client
from langchain_core.messages import HumanMessage

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('dance_gradio.log')
    ]
)
logger = logging.getLogger(__name__)


class DanceAgentUI:
    """Gradio UI wrapper for the dance agent."""
    
    def __init__(self):
        self.agent = None
        self.setup_complete = False
        self.session_counter = 0
        self.active_threads = {}
    
    async def initialize_agent(self):
        """Initialize the dance agent asynchronously."""
        if self.setup_complete:
            return
        
        try:
            # Load environment variables
            load_dotenv()
            
            # Create and setup the agent
            self.agent = await create_dance_agent()
            await mcp_client.setup()
            
            self.setup_complete = True
            return "✅ Dance agent initialized successfully!"
        
        except Exception as e:
            return f"❌ Failed to initialize agent: {str(e)}"
    
    async def process_query_with_progress(self, message: str, history: List[Tuple[str, str]], session_id: str = None) -> AsyncIterator[Tuple[str, str]]:
        """Process a query with real-time progress updates."""
        print(f"DEBUG GRADIO: Starting process_query at {time.time()} for session {session_id}", file=sys.stderr)
        
        # Yield initial progress IMMEDIATELY
        yield ("🤔 **Analyzing Your Question**\n\n_Initializing the dance assistant and preparing your search..._", "progress")
        await asyncio.sleep(0.01)  # Force immediate UI update
        
        try:
            # Initialize agent if not done yet
            if self.agent is None:
                yield ("🔧 **Initializing Dance Agent**\n\n_Setting up the Scottish Country Dance database connection..._", "progress")
                await asyncio.sleep(0.01)  # Force UI update before initialization
                await self.initialize_agent()
                yield ("🔧 **Dance Agent Ready**\n\n_Agent initialized successfully, preparing database search..._", "progress")
                await asyncio.sleep(0.01)  # Force UI update after initialization
            
            # Prepare the conversation
            messages = [
                HumanMessage(content=(
                    "You are a Scottish Country Dance expert assistant with access to the Scottish Country Dance Database (SCDDB). "
                    "You can help users find dances, get detailed information about specific dances, and search through dance cribs. "
                    "When helping users:\n"
                    "1. Use find_dances to search for dances by type, formation, or other criteria\n"
                    "2. Use get_dance_detail to get full information about a specific dance\n"
                    "3. Use search_cribs to search for specific moves or terms in dance instructions\n"
                    "Always be helpful and provide clear, well-structured responses. "
                    "When presenting dance information, include relevant details like the dance name, type, formation, and key moves. "
                    "Format your responses nicely for web display.\n\n"
                    f"User question: {message}"
                ))
            ]
            
            # Process through the agent with streaming progress updates
            yield ("🤖 **AI Agent Thinking**\n\nAnalyzing your request and planning database searches...", "progress")
            
            # Create config for conversation memory
            if not session_id:
                session_id = f"gradio_session_{self.session_counter}"
                self.session_counter += 1
            
            config = {
                "configurable": {"thread_id": session_id},
                "recursion_limit": 50  # Increase from default 25 to handle complex queries
            }
            
            # Use the new streaming agent processing
            async for progress_update in self.stream_agent_with_progress(messages, config):
                yield progress_update
            
            total_time = time.time() - start_time
            logger.info(f"✅ GRADIO: Query completed successfully in {total_time:.2f}s total")
            
        except asyncio.TimeoutError:
            total_time = time.time() - start_time
            error_msg = f"⏰ **Query Timeout**\n\nThe dance agent took too long to process your request ({total_time:.1f}s). Please try a simpler query or try again later."
            logger.error(error_msg)
            yield (error_msg, "error")
        except Exception as e:
            total_time = time.time() - start_time
            error_msg = f"❌ **Processing Error**\n\nAn error occurred after {total_time:.1f}s: {str(e)}"
            logger.error(error_msg, exc_info=True)
            yield (error_msg, "error")
    
    async def stream_agent_with_progress(self, messages: List, config: Dict[str, Any]) -> AsyncIterator[Tuple[str, str]]:
        """Stream agent processing with progress updates by monitoring tool calls."""
        agent_start = time.time()
        
        try:
            # Start the agent processing
            response_stream = self.agent.astream({"messages": messages}, config)
            
            tool_call_count = 0
            current_tool = None
            thinking_steps = []
            
            async for chunk in response_stream:
                # Debug: Print comprehensive chunk structure
                print(f"DEBUG: Chunk keys: {list(chunk.keys()) if isinstance(chunk, dict) else type(chunk)}", file=sys.stderr)
                for key, value in chunk.items() if isinstance(chunk, dict) else []:
                    if key == "messages" and value:
                        print(f"DEBUG: {key} has {len(value)} messages", file=sys.stderr)
                    elif isinstance(value, dict) and "messages" in value:
                        print(f"DEBUG: {key}.messages has {len(value['messages'])} messages", file=sys.stderr)
                
                # Handle different chunk types for final responses
                final_response_detected = False
                
                # Only check for final responses in agent chunks, not tool chunks
                # Tool chunks contain JSON data, not final natural language responses
                
                # Check direct messages chunk
                if "messages" in chunk and chunk["messages"]:
                    latest_message = chunk["messages"][-1]
                    print(f"DEBUG: Message type: {type(latest_message)}, has tool_calls: {hasattr(latest_message, 'tool_calls')}", file=sys.stderr)
                    
                    # Check for tool calls in message
                    if hasattr(latest_message, 'tool_calls') and latest_message.tool_calls:
                        print(f"DEBUG: Found {len(latest_message.tool_calls)} tool calls", file=sys.stderr)
                        for tool_call in latest_message.tool_calls:
                            tool_name = tool_call['name']
                            tool_args = tool_call.get('args', {})
                            tool_call_count += 1
                            current_tool = tool_name
                            
                            print(f"DEBUG: Tool call {tool_call_count}: {tool_name} with args {tool_args}", file=sys.stderr)
                            
                            # Generate progress message based on tool being called
                            progress_msg = self.get_tool_progress_message(tool_name, tool_args, tool_call_count)
                            thinking_steps.append(progress_msg)
                            
                            # Show progress with thinking trace
                            trace_display = "\n".join([f"✓ {step}" for step in thinking_steps[:-1]])
                            if trace_display:
                                trace_display += "\n"
                            trace_display += f"⏳ {progress_msg}"
                            
                            full_progress = f"🔍 **Database Search in Progress** (Step {tool_call_count})\n\n{trace_display}\n\n_Please wait while I search the dance database..._"
                            print(f"DEBUG: Yielding progress update: {full_progress[:100]}...", file=sys.stderr)
                            yield (full_progress, "progress")
                            # Force UI update by yielding control
                            await asyncio.sleep(0.01)
                
                # Also check if chunk contains agent action directly
                elif "agent" in chunk and "messages" in chunk["agent"]:
                    agent_messages = chunk["agent"]["messages"]
                    if agent_messages:
                        latest_message = agent_messages[-1]
                        if hasattr(latest_message, 'tool_calls') and latest_message.tool_calls:
                            print(f"DEBUG: Found tool calls in agent chunk", file=sys.stderr)
                            # Same tool call processing logic
                            for tool_call in latest_message.tool_calls:
                                tool_name = tool_call['name']
                                tool_args = tool_call.get('args', {})
                                tool_call_count += 1
                                
                                progress_msg = self.get_tool_progress_message(tool_name, tool_args, tool_call_count)
                                thinking_steps.append(progress_msg)
                                
                                trace_display = "\n".join([f"✓ {step}" for step in thinking_steps[:-1]])
                                if trace_display:
                                    trace_display += "\n"
                                trace_display += f"⏳ {progress_msg}"
                                
                                full_progress = f"🔍 **Database Search in Progress** (Step {tool_call_count})\n\n{trace_display}\n\n_Please wait while I search the dance database..._"
                                yield (full_progress, "progress")
                                await asyncio.sleep(0.01)
                    
                    # Check for tool responses
                    elif hasattr(latest_message, 'content') and current_tool:
                        # Tool call completed
                        if current_tool and len(thinking_steps) > 0:
                            thinking_steps[-1] = thinking_steps[-1].replace("⏳", "✅")
                        
                        # Show completed steps
                        if thinking_steps:
                            trace_display = "\n".join([f"✓ {step.replace('⏳ ', '').replace('✅ ', '')}" for step in thinking_steps])
                            full_progress = f"🔍 **Database Search Progress** (Step {tool_call_count} completed)\n\n{trace_display}\n\n_Processing results..._"
                            yield (full_progress, "progress")
                            # Force UI update
                            await asyncio.sleep(0.01)
                    
                    # Check for final response (only from agent, not tools)
                    elif hasattr(latest_message, 'content') and latest_message.content:
                        content_str = str(latest_message.content)
                        print(f"DEBUG: Checking potential final response, length: {len(content_str)}, type: {type(latest_message).__name__}", file=sys.stderr)
                        print(f"DEBUG: Content preview: {content_str[:200]}", file=sys.stderr)
                        
                        # Only accept natural language responses from the agent, not JSON tool outputs  
                        is_json_array = content_str.strip().startswith('[{') and content_str.strip().endswith('}]')
                        is_json_object = content_str.strip().startswith('{') and content_str.strip().endswith('}')
                        is_tool_message = type(latest_message).__name__ == 'ToolMessage'
                        has_tool_calls = hasattr(latest_message, 'tool_calls') and latest_message.tool_calls
                        
                        if (len(content_str) > 50 and
                            not has_tool_calls and
                            not is_json_array and 
                            not is_json_object and 
                            not is_tool_message):
                            print(f"DEBUG: Detected final response in messages chunk!", file=sys.stderr)
                            final_response_detected = True
                            
                            if thinking_steps:
                                trace_display = "\n".join([f"✓ {step.replace('⏳ ', '').replace('✅ ', '')}" for step in thinking_steps])
                                yield (f"✅ **Search Complete!**\n\n{trace_display}\n\n_Preparing final response..._", "progress")
                            
                            yield (content_str, "final")
                            return
                
                # Check agent chunk for final response
                elif "agent" in chunk:
                    print(f"DEBUG: Processing agent chunk", file=sys.stderr)
                    
                    # Handle agent messages
                    if "messages" in chunk["agent"] and chunk["agent"]["messages"]:
                        agent_messages = chunk["agent"]["messages"]
                        latest_message = agent_messages[-1]
                        print(f"DEBUG: Agent message type: {type(latest_message).__name__}", file=sys.stderr)
                        
                        # Check for tool calls first
                        if hasattr(latest_message, 'tool_calls') and latest_message.tool_calls:
                            print(f"DEBUG: Found tool calls in agent chunk", file=sys.stderr)
                            # [Tool call processing - keeping existing logic]
                            for tool_call in latest_message.tool_calls:
                                tool_name = tool_call['name']
                                tool_args = tool_call.get('args', {})
                                tool_call_count += 1
                                current_tool = tool_name
                                
                                progress_msg = self.get_tool_progress_message(tool_name, tool_args, tool_call_count)
                                thinking_steps.append(progress_msg)
                                
                                trace_display = "\n".join([f"✓ {step}" for step in thinking_steps[:-1]])
                                if trace_display:
                                    trace_display += "\n"
                                trace_display += f"⏳ {progress_msg}"
                                
                                full_progress = f"🔍 **Database Search in Progress** (Step {tool_call_count})\n\n{trace_display}\n\n_Please wait while I search the dance database..._"
                                yield (full_progress, "progress")
                                await asyncio.sleep(0.01)
                        
                        # Check for final response in agent message (natural language, not JSON)
                        elif hasattr(latest_message, 'content') and latest_message.content:
                            content_str = str(latest_message.content)
                            print(f"DEBUG: Agent message content length: {len(content_str)}", file=sys.stderr)
                            print(f"DEBUG: Agent content preview: {content_str[:200]}", file=sys.stderr)
                            print(f"DEBUG: Message class: {type(latest_message).__name__}", file=sys.stderr)
                            
                            # Accept agent responses that are natural language (exclude raw JSON lists/objects from tools)
                            is_json_array = content_str.strip().startswith('[{') and content_str.strip().endswith('}]')
                            is_json_object = content_str.strip().startswith('{') and content_str.strip().endswith('}')
                            is_tool_message = type(latest_message).__name__ == 'ToolMessage'
                            
                            if (len(content_str) > 50 and 
                                not is_json_array and 
                                not is_json_object and 
                                not is_tool_message):
                                print(f"DEBUG: Detected final response in agent chunk!", file=sys.stderr)
                                final_response_detected = True
                                
                                if thinking_steps:
                                    trace_display = "\n".join([f"✓ {step.replace('⏳ ', '').replace('✅ ', '')}" for step in thinking_steps])
                                    yield (f"✅ **Search Complete!**\n\n{trace_display}\n\n_Preparing final response..._", "progress")
                                
                                yield (content_str, "final")
                                return
                
                # Handle tools chunks (tool responses)
                elif "tools" in chunk and "messages" in chunk["tools"]:
                    tools_messages = chunk["tools"]["messages"]
                    if tools_messages:
                        latest_message = tools_messages[-1]
                        print(f"DEBUG: Tools message type: {type(latest_message).__name__}", file=sys.stderr)
                        
                        # Tool call completed - update progress
                        if current_tool and len(thinking_steps) > 0:
                            thinking_steps[-1] = thinking_steps[-1].replace("⏳", "✅")
                        
                        # Show completed steps
                        if thinking_steps:
                            trace_display = "\n".join([f"✓ {step.replace('⏳ ', '').replace('✅ ', '')}" for step in thinking_steps])
                            full_progress = f"🔍 **Database Search Progress** (Step {tool_call_count} completed)\n\n{trace_display}\n\n_Processing results..._"
                            yield (full_progress, "progress")
                            await asyncio.sleep(0.01)
                        
                        current_tool = None  # Reset current tool
                
                # If no final response detected, continue to next chunk
                if final_response_detected:
                    return
            
            # Fallback - try to get the last response from the agent  
            print(f"DEBUG: Reached fallback - no final response detected through streaming", file=sys.stderr)
            
            # Try to get the final state directly from the agent
            try:
                print(f"DEBUG: Attempting to get final response from agent state", file=sys.stderr)
                # Get the final state after streaming completes
                final_state = await self.agent.aget_state(config)
                if final_state and "messages" in final_state.values:
                    messages = final_state.values["messages"]
                    if messages:
                        # Get the last AI message
                        for msg in reversed(messages):
                            if hasattr(msg, 'content') and msg.content and not (hasattr(msg, 'tool_calls') and msg.tool_calls):
                                content_str = str(msg.content)
                                if len(content_str) > 50:
                                    print(f"DEBUG: Found final message in state: {content_str[:100]}", file=sys.stderr)
                                    
                                    if thinking_steps:
                                        trace_display = "\n".join([f"✓ {step.replace('⏳ ', '').replace('✅ ', '')}" for step in thinking_steps])
                                        yield (f"✅ **Search Complete!**\n\n{trace_display}\n\n_Preparing final response..._", "progress")
                                    
                                    yield (content_str, "final")
                                    return
                        
                print(f"DEBUG: No suitable final message found in state", file=sys.stderr)
                yield ("I apologize, but I encountered an issue retrieving the final response. Please try your query again.", "error")
                
            except Exception as e:
                print(f"DEBUG: Error getting agent state: {e}", file=sys.stderr)
                yield (f"I encountered an error while processing your request: {str(e)}", "error")
                
        except Exception as e:
            print(f"DEBUG: Error in process_query_with_progress: {e}", file=sys.stderr)
            yield (f"I encountered an unexpected error: {str(e)}", "error")
                
    def get_tool_progress_message(self, tool_name: str, tool_args: Dict[str, Any], step_count: int) -> str:
        """Generate human-readable progress messages for different tool calls."""
        if tool_name == "find_dances":
            criteria = []
            if tool_args.get('name_contains'):
                criteria.append(f"name contains '{tool_args['name_contains']}'")
            if tool_args.get('kind'):
                criteria.append(f"type '{tool_args['kind']}'")
            if tool_args.get('metaform_contains'):
                criteria.append(f"formation '{tool_args['metaform_contains']}'")
            if tool_args.get('max_bars'):
                criteria.append(f"max {tool_args['max_bars']} bars")
            if tool_args.get('official_rscds_dances') is True:
                criteria.append("RSCDS official only")
            elif tool_args.get('official_rscds_dances') is False:
                criteria.append("community dances only")
            
            criteria_text = ", ".join(criteria) if criteria else "all dances"
            limit = tool_args.get('limit', 25)
            return f"Searching database for dances ({criteria_text}, limit {limit})"
            
        elif tool_name == "get_dance_detail":
            dance_id = tool_args.get('dance_id')
            return f"Getting detailed information for dance ID {dance_id}"
            
        elif tool_name == "search_cribs":
            query = tool_args.get('query', '')
            limit = tool_args.get('limit', 20)
            return f"Searching dance instructions for '{query}' (limit {limit})"
        
        else:
            return f"Calling tool {tool_name}"


# Global UI instance
ui = DanceAgentUI()


async def stream_process_query(message: str, history: List[Tuple[str, str]], session_id: str = None):
    """Streaming wrapper for the async query processing with progress updates."""
    logger.info(f"🌐 GRADIO: Starting streaming query for: '{message[:30]}{'...' if len(message) > 30 else ''}'")
    
    try:
        async for progress_update in ui.process_query_with_progress(message, history, session_id):
            yield progress_update
    except Exception as e:
        error_msg = f"❌ GRADIO: Streaming wrapper error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        yield (error_msg, "error")


def create_interface():
    """Create the Gradio interface."""
    
    # Custom CSS for ChatSCD theme - enhanced for readability
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    .gradio-container {
        background: linear-gradient(135deg, #f8faff 0%, #e8f2ff 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    
    /* Enhanced chat message styling */
    .chatbot .message {
        font-size: 15px !important;
        line-height: 1.6 !important;
        padding: 16px 20px !important;
        margin: 8px 0 !important;
        border-radius: 12px !important;
        max-width: none !important;
    }
    
    .chatbot .message.user {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3) !important;
    }
    
    .chatbot .message.bot {
        background: white !important;
        color: #2c3e50 !important;
        border: 1px solid #e1e8ed !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
    }
    
    /* Better text formatting in bot messages */
    .chatbot .message.bot p {
        margin: 8px 0 !important;
        line-height: 1.7 !important;
    }
    
    .chatbot .message.bot ul, .chatbot .message.bot ol {
        padding-left: 24px !important;
        margin: 12px 0 !important;
    }
    
    .chatbot .message.bot li {
        margin: 6px 0 !important;
        line-height: 1.6 !important;
    }
    
    .chatbot .message.bot h1, .chatbot .message.bot h2, .chatbot .message.bot h3 {
        color: #2c3e50 !important;
        margin: 16px 0 8px 0 !important;
        font-weight: 600 !important;
    }
    
    .chatbot .message.bot h1 { font-size: 20px !important; }
    .chatbot .message.bot h2 { font-size: 18px !important; }
    .chatbot .message.bot h3 { font-size: 16px !important; }
    
    .chatbot .message.bot strong {
        color: #1a365d !important;
        font-weight: 600 !important;
    }
    
    .chatbot .message.bot code {
        background: #f1f5f9 !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-family: 'Monaco', 'Menlo', monospace !important;
        font-size: 13px !important;
    }
    
    .chatbot .message.bot pre {
        background: #f8fafc !important;
        padding: 12px !important;
        border-radius: 8px !important;
        border-left: 4px solid #3b82f6 !important;
        margin: 12px 0 !important;
        overflow-x: auto !important;
    }
    
    /* Enhanced input styling */
    .gradio-textbox textarea {
        font-size: 15px !important;
        line-height: 1.5 !important;
        padding: 12px 16px !important;
        border: 2px solid #e2e8f0 !important;
        border-radius: 10px !important;
        font-family: 'Inter', sans-serif !important;
    }
    
    .gradio-textbox textarea:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
    }
    
    /* Enhanced button styling */
    .gradio-button {
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        border-radius: 8px !important;
        padding: 10px 20px !important;
        transition: all 0.2s ease !important;
    }
    
    .gradio-button.primary {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: none !important;
        color: white !important;
    }
    
    .gradio-button.primary:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
    }
    
    /* Sidebar styling */
    .sidebar-content {
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 24px !important;
        margin: 10px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06) !important;
    }
    
    .sidebar-title {
        color: #1a365d !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        margin: 0 0 12px 0 !important;
    }
    
    .example-list, .capability-list {
        padding-left: 0 !important;
        list-style: none !important;
        margin: 0 !important;
    }
    
    .example-item, .capability-item {
        background: #f8fafc !important;
        padding: 10px 14px !important;
        margin: 6px 0 !important;
        border-radius: 8px !important;
        border-left: 3px solid #667eea !important;
        color: #2c3e50 !important;
        font-size: 14px !important;
        line-height: 1.4 !important;
        transition: all 0.2s ease !important;
    }
    
    .example-item:hover, .capability-item:hover {
        background: #f1f5f9 !important;
        transform: translateX(2px) !important;
    }
    
    .highlight-text {
        color: #667eea !important;
        font-weight: 600 !important;
    }
    
    /* Header styling */
    .main-header {
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        margin: 0 10px 20px 10px !important;
        padding: 24px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06) !important;
    }
    
    .brand-title {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        font-size: 32px !important;
        font-weight: 700 !important;
        margin-bottom: 8px !important;
    }
    
    .brand-subtitle {
        color: #64748b !important;
        font-size: 18px !important;
        font-weight: 400 !important;
        margin: 0 !important;
    }
    """
    
    with gr.Blocks(
        css=css,
        title="ChatSCD - Scottish Country Dance Assistant",
        theme=gr.themes.Soft()
    ) as demo:
        
        # Header
        gr.HTML("""
        <div class="main-header" style="text-align: center;">
            <h1 class="brand-title">
                🏴󠁧󠁢󠁳󠁣󠁴󠁿 ChatSCD
            </h1>
            <p class="brand-subtitle">
                Your AI assistant for Scottish Country Dancing
            </p>
        </div>
        """)
        
        # Generate unique session ID per browser tab/window
        def get_browser_session_id():
            """Generate a unique session ID for each browser session."""
            return str(uuid.uuid4())
        
        # Session state to maintain conversation memory - unique per browser session
        session_state = gr.State(lambda: {"session_id": f"browser_{get_browser_session_id()}"})
        
        # Main chat interface
        with gr.Row():
            with gr.Column(scale=4):
                chatbot = gr.Chatbot(
                    height=600,
                    show_label=False,
                    container=True,
                    bubble_full_width=False,
                    avatar_images=("👤", "🏴󠁧󠁢󠁳󠁣󠁴󠁿"),
                    elem_classes=["chat-container"]
                )
                
                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="Ask me about Scottish Country Dances, lesson plans, or specific moves...",
                        show_label=False,
                        scale=4,
                        container=False,
                        lines=2,
                        max_lines=5
                    )
                    submit_btn = gr.Button("Send", variant="primary", scale=1)
                
                with gr.Row():
                    clear_btn = gr.Button("Clear Chat", variant="secondary")
            
            with gr.Column(scale=1):
                gr.HTML("""
                <div class="sidebar-content">
                    <h3 class="sidebar-title">💡 Try asking:</h3>
                    <ul class="example-list">
                        <li class="example-item">"Create a lesson plan for beginners"</li>
                        <li class="example-item">"Find me some 32-bar reels"</li>
                        <li class="example-item">"What dances have poussette moves?"</li>
                        <li class="example-item">"Show me longwise dances for 3 couples"</li>
                        <li class="example-item">"Plan a workshop on strathspeys"</li>
                        <li class="example-item">"Find RSCDS published jigs"</li>
                    </ul>
                    
                    <h3 class="sidebar-title">🎯 What I can do:</h3>
                    <ul class="capability-list">
                        <li class="capability-item"><span class="highlight-text">Lesson Planning:</span> Create structured dance lessons</li>
                        <li class="capability-item"><span class="highlight-text">Dance Search:</span> Find by type, formation, length</li>
                        <li class="capability-item"><span class="highlight-text">Move Analysis:</span> Search for specific techniques</li>
                        <li class="capability-item"><span class="highlight-text">RSCDS Filter:</span> Official vs community dances</li>
                    </ul>
                </div>
                """)
        
        # Event handlers with browser-scoped session management and streaming progress
        def respond(message, chat_history, session_state):
            if not message.strip():
                return "", chat_history, session_state
            
            # Ensure session_state is properly initialized for this browser session
            if session_state is None or not isinstance(session_state, dict) or "session_id" not in session_state:
                session_state = {"session_id": f"browser_{str(uuid.uuid4())}"}
                logger.info(f"🆕 GRADIO: Creating new browser session: {session_state['session_id']}")
            
            session_id = session_state["session_id"]
            logger.info(f"💬 GRADIO: Message from browser session {session_id[:8]}...: '{message[:50]}{'...' if len(message) > 50 else ''}'")
            
            # Add user message to history immediately
            chat_history.append([message, "🔧 **Starting...**\n\nInitializing your request..."])
            yield "", chat_history, session_state
            
            # Create async runner for streaming updates
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run the async streaming process
                async def run_streaming():
                    try:
                        async for progress_update in stream_process_query(message, chat_history, session_id):
                            content, update_type = progress_update
                            
                            # Update the bot response in real-time
                            if update_type in ["progress", "error"]:
                                chat_history[-1][1] = content
                                return "", chat_history, session_state
                            elif update_type == "final":
                                # Final response - clean and format
                                if content is None:
                                    content = "No response generated."
                                
                                # Ensure it's a string and clean up formatting
                                final_response = str(content)
                                
                                # Basic HTML cleanup while preserving markdown
                                import re
                                final_response = re.sub(r'<(?!/?(?:b|i|u|strong|em|code|pre|br|p|ul|ol|li|h[1-6])\b)[^>]*>', '', final_response)
                                
                                # Update with final response
                                chat_history[-1][1] = final_response
                                return "", chat_history, session_state
                        
                        # Fallback
                        if chat_history[-1][1] == "🔧 **Starting...**\n\nInitializing your request...":
                            chat_history[-1][1] = "❌ No response was generated. Please try again."
                        
                        return "", chat_history, session_state
                        
                    except Exception as e:
                        error_msg = f"❌ **Processing Error**\n\nAn unexpected error occurred: {str(e)}"
                        logger.error(f"Streaming error: {e}", exc_info=True)
                        chat_history[-1][1] = error_msg
                        return "", chat_history, session_state
                
                # Run and return result
                result = loop.run_until_complete(run_streaming())
                return result
                
            except Exception as e:
                error_msg = f"❌ **Processing Error**\n\nAn unexpected error occurred: {str(e)}"
                logger.error(f"Respond handler error: {e}", exc_info=True)
                chat_history[-1][1] = error_msg
                return "", chat_history, session_state
            finally:
                loop.close()
        
        # Simplified streaming function that forces immediate updates
        def respond_stream(message, chat_history, session_state):
            if not message.strip():
                yield "", chat_history, session_state
                return
            
            # Ensure session_state is properly initialized
            if session_state is None or not isinstance(session_state, dict) or "session_id" not in session_state:
                session_state = {"session_id": f"browser_{str(uuid.uuid4())}"}
                logger.info(f"🆕 GRADIO: Creating new browser session: {session_state['session_id']}")
            
            session_id = session_state["session_id"]
            
            # Add user message to history with IMMEDIATE initial progress
            chat_history.append([message, "🤔 **Analyzing Your Question**\n\nInitializing the dance assistant..."])
            yield "", chat_history, session_state
            
            # Immediate second update to confirm UI responsiveness
            import time
            time.sleep(0.1)  # Brief pause to ensure first update is rendered
            chat_history[-1][1] = "🔧 **Initializing Dance Agent**\n\nStarting database connection..."
            yield "", chat_history, session_state
            
            # Run the query with progress updates in a separate thread
            import threading
            import queue
            import time
            
            progress_queue = queue.Queue()
            result_ready = threading.Event()
            
            def run_query():
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def async_query():
                        # Put an immediate update to start the flow
                        progress_queue.put(("🔍 **Starting Search**\n\nConnecting to dance database...", "progress"))
                        
                        async for progress_update in stream_process_query(message, chat_history, session_id):
                            progress_queue.put(progress_update)
                            # Don't wait for final - put all updates immediately
                            if progress_update[1] == "final":
                                break
                        result_ready.set()
                    
                    loop.run_until_complete(async_query())
                    loop.close()
                    
                except Exception as e:
                    progress_queue.put((f"❌ **Error**: {str(e)}", "error"))
                    result_ready.set()
            
            # Start query in background
            query_thread = threading.Thread(target=run_query)
            query_thread.daemon = True
            query_thread.start()
            
            # Poll for updates and yield them immediately with aggressive responsiveness
            last_content = ""
            final_yielded = False
            update_count = 0
            
            while not result_ready.is_set() or not progress_queue.empty():
                try:
                    # Check for new progress with very short timeout for immediate response
                    content, update_type = progress_queue.get(timeout=0.05)
                    
                    if content != last_content:
                        chat_history[-1][1] = content
                        last_content = content
                        update_count += 1
                        
                        # Yield immediately
                        yield "", chat_history, session_state
                        
                        # Force a tiny delay to ensure UI rendering
                        time.sleep(0.01)
                        
                        if update_type == "final":
                            final_yielded = True
                            break
                            
                except queue.Empty:
                    # No new updates, continue polling
                    continue
            
            # Ensure we have a final response
            if not final_yielded and chat_history[-1][1].startswith("🔧"):
                chat_history[-1][1] = "❌ **Timeout** - No response received. Please try again."
                yield "", chat_history, session_state
        
        def clear_chat(session_state):
            # Keep the same browser session but start a new conversation thread
            if session_state and "session_id" in session_state:
                # Create a new conversation thread within the same browser session
                base_session = session_state["session_id"].split("_conv_")[0]
                new_conversation = f"{base_session}_conv_{int(time.time() * 1000)}"
                session_state["session_id"] = new_conversation
                logger.info(f"🧹 GRADIO: Chat cleared, new conversation thread: {new_conversation}")
            else:
                # Fallback: create entirely new session
                session_state = {"session_id": f"browser_{str(uuid.uuid4())}_conv_{int(time.time() * 1000)}"}
                logger.info(f"🧹 GRADIO: Chat cleared, new session: {session_state['session_id']}")
            return [], session_state
        
        # Wire up the events with session state - enable streaming for progress updates
        msg.submit(respond_stream, [msg, chatbot, session_state], [msg, chatbot, session_state], queue=True)
        submit_btn.click(respond_stream, [msg, chatbot, session_state], [msg, chatbot, session_state], queue=True)  
        clear_btn.click(clear_chat, [session_state], [chatbot, session_state], queue=False)
        
        # Footer
        gr.HTML("""
        <div style="text-align: center; padding: 20px; color: #2c3e50; background: white; border-radius: 12px; margin: 20px 10px 0 10px; border: 1px solid #e2e8f0;">
            <p style="margin: 8px 0; font-weight: 500; color: #1a365d;">Powered by the Scottish Country Dance Database (SCDDB)</p>
            <p style="font-size: 14px; margin: 4px 0; color: #4a5568;">
                ChatSCD helps you explore thousands of Scottish Country Dances with AI assistance
            </p>
        </div>
        """)
    
    return demo


def main():
    """Main entry point for the Gradio app."""
    
    # Check for required environment variables
    load_dotenv()
    
    # Set environment variables for extended timeouts
    os.environ['GRADIO_CLIENT_TIMEOUT'] = '650'  # 10+ minutes for client timeout
    os.environ['HTTPX_TIMEOUT'] = '650'  # Extended HTTP timeout
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable not set.")
        print("Please set your OpenAI API key in a .env file or as an environment variable.")
        sys.exit(1)
    
    # Check for database
    db_path = os.environ.get("SCDDB_SQLITE", "data/scddb/scddb.sqlite")
    if not Path(db_path).exists():
        print(f"❌ Error: Database not found at {db_path}")
        print("Please run refresh_scddb.py first to download the database.")
        sys.exit(1)
    
    print("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Starting ChatSCD - Scottish Country Dance Assistant Web UI...")
    
    # Create and launch the interface
    demo = create_interface()
    
    # Launch with settings appropriate for VPS hosting
    logger.info("🚀 Launching Gradio interface...")
    # Configure queue with extended timeout to match server timeout
    demo.queue(
        default_concurrency_limit=10,  # Allow 10 concurrent requests
        max_size=50,  # Queue up to 50 requests
        api_open=True  # Allow API access
    )
    demo.launch(
        server_name="0.0.0.0",  # Allow external connections
        server_port=7860,       # Default Gradio port
        share=False,            # Don't create a public gradio.app link
        show_error=True,        # Show detailed errors
        quiet=False,            # Show startup info
        max_threads=10,         # Allow more concurrent requests
        # Configure timeouts to match server settings
        favicon_path=None,
        ssl_verify=False
    )


if __name__ == "__main__":
    main()
