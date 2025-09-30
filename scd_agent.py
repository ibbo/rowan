#!/usr/bin/env python3
"""
LangGraph-based Scottish Country Dance Agent with prompt checking and dance planning.

Architecture:
1. Prompt Checker: Validates that queries are about Scottish Country Dancing
2. Dance Planner: Uses tools to answer dance-related queries

Usage:
    export OPENAI_API_KEY="your-key-here"
    uv run scd_agent.py
"""

import asyncio
import os
import sys
from typing import Annotated, Literal
from typing_extensions import TypedDict

from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from dance_tools import find_dances, get_dance_detail, search_cribs


# Define the state that flows through the graph
class State(TypedDict):
    """State that flows through the agent graph."""
    messages: Annotated[list, add_messages]
    is_scd_query: bool  # Whether the query is about Scottish Country Dancing
    route: str  # Routing decision from prompt checker


class SCDAgent:
    """Scottish Country Dance Agent with multi-stage processing."""
    
    def __init__(self):
        """Initialize the agent with LLMs and tools."""
        # Check for OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OpenAI API key not found. Please set OPENAI_API_KEY environment variable.\n"
                "Example: export OPENAI_API_KEY='your-key-here'"
            )
        
        # Initialize LLMs for different agents
        self.prompt_checker_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.dance_planner_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
        # Tools for the dance planner
        self.tools = [find_dances, get_dance_detail, search_cribs]
        
        # Bind tools to the dance planner LLM
        self.dance_planner_with_tools = self.dance_planner_llm.bind_tools(self.tools)
        
        # Checkpointer for conversation memory
        self.checkpointer = MemorySaver()
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """Build the LangGraph workflow."""
        graph_builder = StateGraph(State)
        
        # Add nodes
        graph_builder.add_node("prompt_checker", self._prompt_checker_node)
        graph_builder.add_node("dance_planner", self._dance_planner_node)
        graph_builder.add_node("tool_executor", self._tool_executor_node)
        graph_builder.add_node("rejection_handler", self._rejection_handler_node)
        
        # Add edges
        graph_builder.add_edge(START, "prompt_checker")
        
        # Conditional routing from prompt checker
        graph_builder.add_conditional_edges(
            "prompt_checker",
            self._route_after_prompt_check,
            {
                "dance_planner": "dance_planner",
                "reject": "rejection_handler"
            }
        )
        
        # Conditional routing from dance planner
        graph_builder.add_conditional_edges(
            "dance_planner",
            self._route_after_planner,
            {
                "tools": "tool_executor",
                "end": END
            }
        )
        
        # Tool executor loops back to dance planner
        graph_builder.add_edge("tool_executor", "dance_planner")
        
        # Rejection handler goes to END
        graph_builder.add_edge("rejection_handler", END)
        
        # Compile with checkpointer for memory
        return graph_builder.compile(checkpointer=self.checkpointer)
    
    def _prompt_checker_node(self, state: State) -> dict:
        """Check if the prompt is about Scottish Country Dancing."""
        print("\n🔍 Prompt Checker: Analyzing query...", file=sys.stderr)
        
        # Get the last user message
        last_message = state["messages"][-1]
        user_query = last_message.content if isinstance(last_message.content, str) else str(last_message.content)
        
        # System prompt for the checker
        checker_prompt = SystemMessage(content="""
You are a prompt validator for a Scottish Country Dance assistant. Your job is to determine if a user's query is related to Scottish Country Dancing.

Scottish Country Dancing topics include:
- Dance names, types (reels, jigs, strathspeys, etc.)
- Dance formations and moves (poussette, allemande, etc.)
- RSCDS (Royal Scottish Country Dance Society) publications
- Planning dance classes or programmes
- Dance cribs and instructions
- Scottish dance music and timing

Respond with ONLY one word:
- "ACCEPT" if the query is about Scottish Country Dancing
- "REJECT" if the query is about something else

Examples:
- "Find me some 32-bar reels" -> ACCEPT
- "What's the weather today?" -> REJECT
- "Tell me about The Reel of the 51st Division" -> ACCEPT
- "How do I cook haggis?" -> REJECT
""")
        
        user_message = HumanMessage(content=f"User query: {user_query}")
        
        # Get decision from checker
        response = self.prompt_checker_llm.invoke([checker_prompt, user_message])
        decision = response.content.strip().upper()
        
        is_accepted = "ACCEPT" in decision
        
        print(f"🔍 Prompt Checker: {'✅ ACCEPTED' if is_accepted else '❌ REJECTED'}", file=sys.stderr)
        
        return {
            "is_scd_query": is_accepted,
            "route": "dance_planner" if is_accepted else "reject"
        }
    
    def _route_after_prompt_check(self, state: State) -> Literal["dance_planner", "reject"]:
        """Route based on prompt checker decision."""
        return state["route"]
    
    def _rejection_handler_node(self, state: State) -> dict:
        """Handle rejected queries with a polite message."""
        print("❌ Rejection Handler: Query not about SCD", file=sys.stderr)
        
        rejection_message = AIMessage(content=(
            "Thanks for reaching out! I'm dedicated to Scottish Country Dancing, "
            "including sharing information and helping plan classes or dance programmes. "
            "Could you rephrase your question to focus on Scottish Country Dancing?"
        ))
        
        return {"messages": [rejection_message]}
    
    def _dance_planner_node(self, state: State) -> dict:
        """Plan and execute dance queries using tools."""
        print("\n🎯 Dance Planner: Processing query...", file=sys.stderr)
        
        # Add system message for the dance planner if this is the first planning step
        messages = state["messages"]
        
        # Check if we need to add system context
        has_system_message = any(isinstance(msg, SystemMessage) for msg in messages)
        
        if not has_system_message:
            system_msg = SystemMessage(content="""
You are a Scottish Country Dance expert assistant with access to the Scottish Country Dance Database (SCDDB).

You have access to these tools:
1. find_dances: Search for dances by name, type (Reel/Jig/Strathspey), formation, bars, RSCDS status
2. get_dance_detail: Get detailed information about a specific dance including crib
3. search_cribs: Search dance instructions for specific moves or terms

When helping users:
- Use find_dances to search for dances matching criteria
- Use get_dance_detail to get full information about specific dances
- Use search_cribs to find dances with specific moves
- Provide clear, well-structured responses with relevant details
- Include dance names, types, formations, and key information
""")
            messages = [system_msg] + messages
        
        # Invoke the LLM with tools
        response = self.dance_planner_with_tools.invoke(messages)
        
        print(f"🎯 Dance Planner: {'Using tools' if response.tool_calls else 'Responding'}", file=sys.stderr)
        
        return {"messages": [response]}
    
    def _route_after_planner(self, state: State) -> Literal["tools", "end"]:
        """Route based on whether the planner wants to use tools."""
        last_message = state["messages"][-1]
        
        # Check if there are tool calls
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        return "end"
    
    async def _tool_executor_node(self, state: State) -> dict:
        """Execute tool calls from the dance planner."""
        print("\n🔧 Tool Executor: Running tools...", file=sys.stderr)
        
        last_message = state["messages"][-1]
        tool_calls = last_message.tool_calls
        
        from langchain_core.messages import ToolMessage
        
        tool_messages = []
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            print(f"🔧 Executing: {tool_name}({tool_args})", file=sys.stderr)
            
            # Find and execute the tool
            tool_func = None
            for tool in self.tools:
                if tool.name == tool_name:
                    tool_func = tool
                    break
            
            if tool_func:
                try:
                    result = await tool_func.ainvoke(tool_args)
                    tool_messages.append(
                        ToolMessage(
                            content=str(result),
                            tool_call_id=tool_id,
                            name=tool_name
                        )
                    )
                    print(f"✅ Tool {tool_name} completed", file=sys.stderr)
                except Exception as e:
                    tool_messages.append(
                        ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_id,
                            name=tool_name
                        )
                    )
                    print(f"❌ Tool {tool_name} failed: {e}", file=sys.stderr)
            else:
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: Tool {tool_name} not found",
                        tool_call_id=tool_id,
                        name=tool_name
                    )
                )
        
        return {"messages": tool_messages}
    
    async def ainvoke(self, user_input: str, config: dict = None):
        """Async invoke the agent with a user query."""
        if config is None:
            config = {"configurable": {"thread_id": "default"}}
        
        # Create initial state
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "is_scd_query": False,
            "route": ""
        }
        
        # Run the graph
        result = await self.graph.ainvoke(initial_state, config)
        return result
    
    def invoke(self, user_input: str, config: dict = None):
        """Synchronous invoke (runs async in event loop)."""
        return asyncio.run(self.ainvoke(user_input, config))


async def main():
    """Main interactive loop."""
    load_dotenv()
    
    try:
        print("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scottish Country Dance Assistant")
        print("=" * 50)
        print("Setting up multi-agent system...")
        
        agent = SCDAgent()
        
        print("✅ Agent ready! Ask me about Scottish Country Dances.")
        print("\nExamples:")
        print("- 'Find me some 32-bar reels'")
        print("- 'What dances have poussette moves?'")
        print("- 'Tell me about The Reel of the 51st Division'")
        print("- 'Find longwise dances for 3 couples'")
        print("\nType 'quit' to exit.\n")
        
        # Use a consistent thread for conversation memory
        config = {"configurable": {"thread_id": "interactive_session"}}
        
        try:
            while True:
                try:
                    user_input = input("🤔 Your question: ").strip()
                    
                    if user_input.lower() in ['quit', 'exit', 'bye']:
                        print("👋 Goodbye!")
                        break
                    
                    if not user_input:
                        continue
                    
                    print("\n🤖 Processing...")
                    
                    # Process the query
                    result = await agent.ainvoke(user_input, config)
                    
                    # Extract and display the final message
                    final_message = result["messages"][-1]
                    print(f"\n📚 {final_message.content}\n")
                    print("-" * 50)
                    
                except KeyboardInterrupt:
                    print("\n\n👋 Goodbye!")
                    break
                except Exception as e:
                    print(f"\n❌ Error: {e}\n")
                    import traceback
                    traceback.print_exc()
        finally:
            # Clean up MCP client connections properly
            from dance_tools import mcp_client
            print("\n🧹 Cleaning up...", file=sys.stderr)
            await mcp_client.close()
    
    except Exception as e:
        print(f"Failed to start agent: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
