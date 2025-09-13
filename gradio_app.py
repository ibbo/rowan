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
from typing import List, Tuple

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
    
    async def process_query(self, message: str, history: List[Tuple[str, str]], session_id: str = None) -> str:
        """Process a user query through the dance agent with conversation memory."""
        start_time = time.time()
        logger.info(f"🔄 GRADIO: Processing query: '{message[:50]}{'...' if len(message) > 50 else ''}'")
        print(f"DEBUG GRADIO: Starting process_query at {start_time} for session {session_id}", file=sys.stderr)
        
        if not self.setup_complete:
            logger.info("🔧 GRADIO: Initializing agent...")
            init_start = time.time()
            print(f"DEBUG GRADIO: Starting agent initialization at {init_start}", file=sys.stderr)
            init_result = await self.initialize_agent()
            init_end = time.time()
            init_duration = init_end - init_start
            logger.info(f"⚡ GRADIO: Agent initialization took {init_duration:.2f}s")
            print(f"DEBUG GRADIO: Agent initialization completed in {init_duration:.2f}s", file=sys.stderr)
            if "❌" in init_result:
                return init_result
        
        try:
            # Create the system prompt and user message
            message_start = time.time()
            logger.info("📝 GRADIO: Creating messages for agent...")
            print(f"DEBUG GRADIO: Creating messages at {message_start}", file=sys.stderr)
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
            message_end = time.time()
            message_duration = message_end - message_start
            print(f"DEBUG GRADIO: Message creation took {message_duration:.3f}s", file=sys.stderr)
            
            # Process through the agent with timeout
            logger.info("🤖 GRADIO: Invoking dance agent...")
            agent_start = time.time()
            print(f"DEBUG GRADIO: Starting agent.ainvoke at {agent_start}", file=sys.stderr)
            
            # Create config for conversation memory
            if not session_id:
                session_id = f"gradio_session_{self.session_counter}"
                self.session_counter += 1
            
            config = {"configurable": {"thread_id": session_id}}
            print(f"DEBUG GRADIO: Using thread_id: {session_id}", file=sys.stderr)
            
            # Add timeout wrapper with conversation memory
            response = await asyncio.wait_for(
                self.agent.ainvoke({"messages": messages}, config),
                timeout=600.0  # 10 minute timeout
            )
            
            agent_end = time.time()
            agent_time = agent_end - agent_start
            logger.info(f"🎯 GRADIO: Agent processing took {agent_time:.2f}s")
            print(f"DEBUG GRADIO: Agent.ainvoke completed in {agent_time:.2f}s", file=sys.stderr)
            
            # Extract the final message
            extract_start = time.time()
            final_message = response["messages"][-1]
            extract_end = time.time()
            extract_time = extract_end - extract_start
            
            total_time = time.time() - start_time
            logger.info(f"✅ GRADIO: Query completed successfully in {total_time:.2f}s total")
            print(f"DEBUG GRADIO: Total query time {total_time:.2f}s (extract: {extract_time:.3f}s)", file=sys.stderr)
            
            # Ensure the response is safe for JSON serialization
            response_content = final_message.content
            if response_content is None:
                response_content = "No response generated."
            
            # Convert to string and clean up any problematic characters
            response_content = str(response_content)
            
            # Log response for debugging
            logger.info(f"📤 Response length: {len(response_content)} characters")
            logger.debug(f"📤 Response preview: {response_content[:200]}...")
            
            return response_content
            
        except asyncio.TimeoutError:
            total_time = time.time() - start_time
            error_msg = f"⏰ GRADIO: Query timed out after {total_time:.2f}s. The dance agent took too long to process your request. Please try a simpler query or try again later."
            logger.error(error_msg)
            print(f"DEBUG GRADIO: TIMEOUT after {total_time:.2f}s", file=sys.stderr)
            return error_msg
        except Exception as e:
            total_time = time.time() - start_time
            error_msg = f"❌ GRADIO: Error processing query after {total_time:.2f}s: {str(e)}"
            logger.error(error_msg, exc_info=True)
            print(f"DEBUG GRADIO: ERROR after {total_time:.2f}s - {str(e)}", file=sys.stderr)
            return error_msg


# Global UI instance
ui = DanceAgentUI()


def sync_process_query(message: str, history: List[Tuple[str, str]], session_id: str = None) -> str:
    """Synchronous wrapper for the async query processing."""
    sync_start = time.time()
    logger.info(f"🌐 GRADIO: Starting sync wrapper for query: '{message[:30]}{'...' if len(message) > 30 else ''}'")
    print(f"DEBUG GRADIO: sync_process_query started at {sync_start} for session {session_id}", file=sys.stderr)
    
    loop_start = time.time()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop_setup_time = time.time() - loop_start
    print(f"DEBUG GRADIO: Event loop setup took {loop_setup_time:.3f}s", file=sys.stderr)
    
    try:
        async_start = time.time()
        result = loop.run_until_complete(ui.process_query(message, history, session_id))
        async_end = time.time()
        async_time = async_end - async_start
        total_sync_time = async_end - sync_start
        
        print(f"DEBUG GRADIO: Async execution took {async_time:.2f}s, total sync wrapper {total_sync_time:.2f}s", file=sys.stderr)
        return result
    except Exception as e:
        error_time = time.time() - sync_start
        error_msg = f"❌ GRADIO: Sync wrapper error after {error_time:.2f}s: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"DEBUG GRADIO: Sync wrapper failed after {error_time:.2f}s", file=sys.stderr)
        return error_msg
    finally:
        loop.close()
        close_time = time.time() - sync_start
        print(f"DEBUG GRADIO: Loop closed, total sync_process_query time: {close_time:.2f}s", file=sys.stderr)


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
        
        # Event handlers with browser-scoped session management
        def respond(message, chat_history, session_state):
            respond_start = time.time()
            if not message.strip():
                return "", chat_history, session_state
            
            # Ensure session_state is properly initialized for this browser session
            if session_state is None or not isinstance(session_state, dict) or "session_id" not in session_state:
                session_state = {"session_id": f"browser_{str(uuid.uuid4())}"}
                logger.info(f"🆕 GRADIO: Creating new browser session: {session_state['session_id']}")
            
            session_id = session_state["session_id"]
            logger.info(f"💬 GRADIO: Message from browser session {session_id[:8]}...: '{message[:50]}{'...' if len(message) > 50 else ''}'")
            print(f"DEBUG GRADIO: respond() called at {respond_start} for browser session {session_id}", file=sys.stderr)
            
            # Add user message to history
            history_start = time.time()
            chat_history.append([message, None])
            history_time = time.time() - history_start
            print(f"DEBUG GRADIO: Chat history update took {history_time:.3f}s", file=sys.stderr)
            
            # Get bot response
            try:
                query_start = time.time()
                bot_response = sync_process_query(message, chat_history, session_id)
                query_end = time.time()
                query_time = query_end - query_start
                print(f"DEBUG GRADIO: sync_process_query returned after {query_time:.2f}s", file=sys.stderr)
                
                # Validate and sanitize response for JSON serialization
                if bot_response is None:
                    bot_response = "No response received."
                
                # Ensure it's a string
                bot_response = str(bot_response)
                
                # Remove any HTML tags that might cause JSON parsing issues
                import re
                # Basic HTML tag removal (but preserve markdown formatting)
                bot_response = re.sub(r'<(?!/?(?:b|i|u|strong|em|code|pre|br|p|ul|ol|li|h[1-6])\b)[^>]*>', '', bot_response)
                
                # Ensure response doesn't start with HTML
                if bot_response.strip().startswith('<'):
                    logger.warning("⚠️ Response starts with HTML, wrapping in text")
                    bot_response = f"Response: {bot_response}"
                
                logger.debug(f"✅ Sanitized response length: {len(bot_response)}")
                
            except Exception as e:
                bot_response = f"❌ Unexpected error in response handler: {str(e)}"
                logger.error(f"Response handler error: {e}", exc_info=True)
            
            # Final validation before returning
            try:
                # Test JSON serialization
                import json
                json.dumps(bot_response)
            except (TypeError, ValueError) as e:
                logger.error(f"JSON serialization failed: {e}")
                bot_response = "❌ Response formatting error. Please try again."
            
            # Update the last message with bot response
            update_start = time.time()
            chat_history[-1][1] = bot_response
            update_time = time.time() - update_start
            total_respond_time = time.time() - respond_start
            
            print(f"DEBUG GRADIO: Chat history update took {update_time:.3f}s, total respond() time: {total_respond_time:.2f}s", file=sys.stderr)
            
            return "", chat_history, session_state
        
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
        
        # Wire up the events with session state - enable queue for long-running requests
        msg.submit(respond, [msg, chatbot, session_state], [msg, chatbot, session_state], queue=True)
        submit_btn.click(respond, [msg, chatbot, session_state], [msg, chatbot, session_state], queue=True)
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
