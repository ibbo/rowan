#!/usr/bin/env python3
"""
Gradio web interface for the Scottish Country Dance Agent.

This creates a web UI that can be hosted on a VPS for public access.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Tuple

import gradio as gr
from dotenv import load_dotenv

# Import our existing dance agent
from dance_agent import create_dance_agent, mcp_client
from langchain_core.messages import HumanMessage


class DanceAgentUI:
    """Gradio UI wrapper for the dance agent."""
    
    def __init__(self):
        self.agent = None
        self.setup_complete = False
    
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
    
    async def process_query(self, message: str, history: List[Tuple[str, str]]) -> str:
        """Process a user query through the dance agent."""
        if not self.setup_complete:
            init_result = await self.initialize_agent()
            if "❌" in init_result:
                return init_result
        
        try:
            # Create the system prompt and user message
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
            
            # Process through the agent
            response = await self.agent.ainvoke({"messages": messages})
            
            # Extract the final message
            final_message = response["messages"][-1]
            return final_message.content
            
        except Exception as e:
            return f"❌ Error processing query: {str(e)}"


# Global UI instance
ui = DanceAgentUI()


def sync_process_query(message: str, history: List[Tuple[str, str]]) -> str:
    """Synchronous wrapper for the async query processing."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(ui.process_query(message, history))
    finally:
        loop.close()


def create_interface():
    """Create the Gradio interface."""
    
    # Custom CSS for Scottish theme
    css = """
    .gradio-container {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    .chat-message {
        border-radius: 10px !important;
    }
    .bot-message {
        background-color: #e8f4fd !important;
        border-left: 4px solid #1976d2 !important;
    }
    .user-message {
        background-color: #f3e5f5 !important;
        border-left: 4px solid #7b1fa2 !important;
    }
    /* Fix sidebar readability with specific classes */
    .sidebar-content {
        color: #333 !important;
    }
    .sidebar-title {
        color: #1976d2 !important;
        font-weight: bold !important;
        margin-top: 0 !important;
    }
    .example-list {
        padding-left: 20px !important;
        line-height: 1.8 !important;
        color: #444 !important;
    }
    .example-item {
        color: #555 !important;
        margin-bottom: 6px !important;
    }
    .capability-list {
        padding-left: 20px !important;
        line-height: 1.8 !important;
        color: #444 !important;
    }
    .capability-item {
        color: #555 !important;
        margin-bottom: 6px !important;
    }
    .highlight-text {
        color: #1976d2 !important;
        font-weight: bold !important;
    }
    """
    
    with gr.Blocks(
        css=css,
        title="Scottish Country Dance Assistant",
        theme=gr.themes.Soft()
    ) as demo:
        
        # Header
        gr.HTML("""
        <div style="text-align: center; padding: 20px;">
            <h1 style="color: #1976d2; margin-bottom: 10px;">
                🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scottish Country Dance Assistant
            </h1>
            <p style="color: #666; font-size: 18px;">
                Your AI guide to the Scottish Country Dance Database
            </p>
        </div>
        """)
        
        # Main chat interface
        with gr.Row():
            with gr.Column(scale=4):
                chatbot = gr.Chatbot(
                    height=500,
                    show_label=False,
                    container=True,
                    bubble_full_width=False,
                    avatar_images=(None, "🏴󠁧󠁢󠁳󠁣󠁴󠁿")
                )
                
                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="Ask me about Scottish Country Dances...",
                        show_label=False,
                        scale=4,
                        container=False
                    )
                    submit_btn = gr.Button("Send", variant="primary", scale=1)
                
                with gr.Row():
                    clear_btn = gr.Button("Clear Chat", variant="secondary")
            
            with gr.Column(scale=1):
                gr.HTML("""
                <div class="sidebar-content" style="padding: 20px; background: white; border-radius: 10px; margin: 10px;">
                    <h3 class="sidebar-title">💡 Try asking:</h3>
                    <ul class="example-list">
                        <li class="example-item">"Find me some 32-bar reels"</li>
                        <li class="example-item">"What dances have poussette moves?"</li>
                        <li class="example-item">"Show me longwise dances for 3 couples"</li>
                        <li class="example-item">"Tell me about dance ID 100"</li>
                        <li class="example-item">"Find jigs with less than 40 bars"</li>
                        <li class="example-item">"Search for dances with allemande"</li>
                    </ul>
                    
                    <h3 class="sidebar-title">📚 What I can do:</h3>
                    <ul class="capability-list">
                        <li class="capability-item"><span class="highlight-text">Find Dances:</span> Search by type, formation, length</li>
                        <li class="capability-item"><span class="highlight-text">Dance Details:</span> Get complete information about any dance</li>
                        <li class="capability-item"><span class="highlight-text">Crib Search:</span> Find dances containing specific moves</li>
                    </ul>
                </div>
                """)
        
        # Event handlers
        def respond(message, chat_history):
            if not message.strip():
                return "", chat_history
            
            # Add user message to history
            chat_history.append([message, None])
            
            # Get bot response
            bot_response = sync_process_query(message, chat_history)
            
            # Update the last message with bot response
            chat_history[-1][1] = bot_response
            
            return "", chat_history
        
        def clear_chat():
            return []
        
        # Wire up the events
        msg.submit(respond, [msg, chatbot], [msg, chatbot], queue=False)
        submit_btn.click(respond, [msg, chatbot], [msg, chatbot], queue=False)
        clear_btn.click(clear_chat, None, chatbot, queue=False)
        
        # Footer
        gr.HTML("""
        <div style="text-align: center; padding: 20px; color: #666;">
            <p>Powered by the Scottish Country Dance Database (SCDDB)</p>
            <p style="font-size: 12px;">
                This assistant can help you explore thousands of Scottish Country Dances
            </p>
        </div>
        """)
    
    return demo


def main():
    """Main entry point for the Gradio app."""
    
    # Check for required environment variables
    load_dotenv()
    
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
    
    print("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Starting Scottish Country Dance Assistant Web UI...")
    
    # Create and launch the interface
    demo = create_interface()
    
    # Launch with settings appropriate for VPS hosting
    demo.launch(
        server_name="0.0.0.0",  # Allow external connections
        server_port=7860,       # Default Gradio port
        share=False,            # Don't create a public gradio.app link
        show_error=True,        # Show detailed errors
        quiet=False             # Show startup info
    )


if __name__ == "__main__":
    main()
