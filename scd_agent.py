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

from dance_tools import (
    find_dances, get_dance_detail, search_cribs, list_formations, search_manual,
    find_videos, find_recordings, find_devisors, find_publications, 
    get_publication_dances, search_dance_lists, get_dance_list_detail
)
from concept_resolver import (
    CanonicalConceptResolver,
    build_grounding_decision,
    manual_kb_available,
)


# Define the state that flows through the graph
class State(TypedDict):
    """State that flows through the agent graph."""
    messages: Annotated[list, add_messages]
    is_scd_query: bool  # Whether the query is about Scottish Country Dancing
    route: str  # Routing decision from prompt checker
    grounding_route: str
    grounding_context: str
    grounding_response: str


class SCDAgent:
    """Scottish Country Dance Agent with multi-stage processing."""
    
    def __init__(
        self, 
        provider: str = "openai", 
        model: str = "gpt-5.4-mini",
        temperature: float = 0,
        api_key: str | None = None
    ):
        """Initialize the agent with LLMs and tools.
        
        Args:
            provider: LLM provider name ('openai', 'google')
            model: Model identifier
            temperature: Sampling temperature (0 = deterministic)
        """
        from llm_providers import get_provider
        
        # Get the provider instance
        llm_provider = get_provider(provider)
        
        # Check for API key
        import os
        env_var = llm_provider.get_env_var_name()
        if not api_key and not os.getenv(env_var):
            raise RuntimeError(
                f"API key not found. Please set {env_var} environment variable.\\n"
                f"Example: export {env_var}='your-key-here'"
            )
        
        # Initialize LLMs for different agents
        self.prompt_checker_llm = llm_provider.create_chat_llm(model, temperature, api_key)
        self.dance_planner_llm = llm_provider.create_chat_llm(model, temperature, api_key)
        
        # Store config for reference
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        
        # Tools for the dance planner
        self.tools = [
            list_formations, find_dances, get_dance_detail, search_cribs, search_manual,
            find_videos, find_recordings, find_devisors, find_publications,
            get_publication_dances, search_dance_lists, get_dance_list_detail
        ]
        self.concept_resolver = CanonicalConceptResolver()
        
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
        graph_builder.add_node("concept_grounder", self._concept_grounder_node)
        graph_builder.add_node("dance_planner", self._dance_planner_node)
        graph_builder.add_node("tool_executor", self._tool_executor_node)
        graph_builder.add_node("grounding_handler", self._grounding_handler_node)
        graph_builder.add_node("rejection_handler", self._rejection_handler_node)
        
        # Add edges
        graph_builder.add_edge(START, "prompt_checker")
        
        # Conditional routing from prompt checker
        graph_builder.add_conditional_edges(
            "prompt_checker",
            self._route_after_prompt_check,
            {
                "concept_grounder": "concept_grounder",
                "reject": "rejection_handler"
            }
        )

        graph_builder.add_conditional_edges(
            "concept_grounder",
            self._route_after_grounding,
            {
                "dance_planner": "dance_planner",
                "grounding_handler": "grounding_handler",
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
    
    def _route_after_prompt_check(self, state: State) -> Literal["concept_grounder", "reject"]:
        """Route based on prompt checker decision."""
        return "concept_grounder" if state["route"] == "dance_planner" else "reject"

    async def _concept_grounder_node(self, state: State) -> dict:
        """Resolve canonical SCD concepts before planning."""
        print("\n🧭 Concept Grounder: Resolving canonical concepts...", file=sys.stderr)

        last_message = state["messages"][-1]
        user_query = last_message.content if isinstance(last_message.content, str) else str(last_message.content)

        resolution = await self.concept_resolver.resolve(user_query)
        decision = build_grounding_decision(
            resolution=resolution,
            manual_available=manual_kb_available(),
        )

        if decision.grounding_context:
            print("🧭 Concept Grounder: Added canonical grounding context", file=sys.stderr)
        if decision.route == "grounding_handler":
            print("🧭 Concept Grounder: Blocking ungrounded technical answer", file=sys.stderr)

        return {
            "grounding_route": decision.route,
            "grounding_context": decision.grounding_context,
            "grounding_response": decision.response,
        }

    def _route_after_grounding(self, state: State) -> Literal["dance_planner", "grounding_handler"]:
        """Route based on grounding outcome."""
        return state.get("grounding_route", "dance_planner")
    
    def _rejection_handler_node(self, state: State) -> dict:
        """Handle rejected queries with a polite message."""
        print("❌ Rejection Handler: Query not about SCD", file=sys.stderr)
        
        rejection_message = AIMessage(content=(
            "Thanks for reaching out! I'm dedicated to Scottish Country Dancing, "
            "including sharing information and helping plan classes or dance programmes. "
            "Could you rephrase your question to focus on Scottish Country Dancing?"
        ))
        
        return {"messages": [rejection_message]}

    def _grounding_handler_node(self, state: State) -> dict:
        """Return deterministic clarification / unsupported-grounding responses."""
        print("🧱 Grounding Handler: Responding without planner", file=sys.stderr)
        return {"messages": [AIMessage(content=state["grounding_response"])]}

    def _dance_planner_node(self, state: State) -> dict:
        """Plan and execute dance queries using tools."""
        print("\n🎯 Dance Planner: Processing query...", file=sys.stderr)
        
        # Add system message for the dance planner if this is the first planning step
        messages = state["messages"]

        system_messages = [SystemMessage(content="""
You are a Scottish Country Dance expert assistant with access to the Scottish Country Dance Database (SCDDB).

You have access to these tools:
1. find_dances: Search for dances by name, type (Reel/Jig/Strathspey), formation, bars, RSCDS status
2. get_dance_detail: Get detailed information about a specific dance including crib
3. search_cribs: Search dance instructions for specific moves or terms
4. list_formations: List all available dance formations with usage statistics
5. search_manual: Search the official RSCDS manual for teaching points, technique guidance, and formation descriptions

CRITICAL DISTINCTION - Dance Types vs. Dance Formations:
⚠️ "Reel", "Jig", "Strathspey" are DANCE TYPES (music/tempo) - use the 'kind' parameter
⚠️ "Reel of three", "poussette", "allemande" are DANCE FORMATIONS (figures/movements)

When users ask for "dances with a reel of 3" or "dances with reels of three":
- They are asking for dances containing the FORMATION "reel of three" (a figure where 3 people dance in a figure-8 pattern)
- DO NOT use kind='Reel' - that's the dance type!
- CORRECT APPROACH: Use search_cribs with query "reel of three" to find dances containing this formation
- ALTERNATIVE: Use list_formations to find "reel of three" formations, get the token (e.g., "REEL;R3;"), then use find_dances with formation_token

Examples of how to handle different queries:
- "Find Reels" → kind='Reel' (dance type)
- "Find dances with a reel of 3" → search_cribs("reel of three") (formation/figure)
- "Find dances with poussette" → search_cribs("poussette") (formation)
- "Find 32-bar Jigs" → kind='Jig', max_bars=32 (dance type + bars)

CRITICAL: When using find_dances, ALWAYS set random_variety=True to provide varied and diverse dance suggestions.
Only use random_variety=False if the user specifically asks for alphabetical order or searches for a specific dance by name.

When helping users:
- Use find_dances to search for dances matching criteria (ALWAYS with random_variety=True for variety)
- Use get_dance_detail to get full information about specific dances
- Use search_cribs to find dances with specific moves/formations (e.g., "reel of three", "poussette")
- Use list_formations to discover available formations
- Use search_manual when users ask for teaching points, technique guidance, or explanations of formations
- Provide clear, well-structured responses with relevant details
- Include dance names, types, formations, and key information
- When explaining formations, consult the RSCDS manual for authoritative teaching guidance

⚠️ CRITICAL - NEVER MIX UP FORMATION INSTRUCTIONS:
When explaining how to teach a specific formation (e.g., "skip change of step"), you MUST:
1. Quote ONLY the instructions from the search_manual result for that EXACT formation
2. DO NOT paraphrase or "improve" the instructions
3. DO NOT blend instructions from similar-sounding formations (e.g., pas de basque ≠ skip change of step)
4. If unsure, quote the manual verbatim - accuracy is more important than style
5. Verify the section number matches the requested formation before using any content

⚠️ CRITICAL - QUERY CONSTRUCTION FOR search_manual:
When users ask "how to teach [formation]", construct your search_manual query carefully:
- GOOD: "skip change of step points to observe" → Gets specific teaching content
- GOOD: "skip change of step" → Gets the right formation
- BAD: "teaching skip change" → Gets generic Chapter 8 teaching advice ❌
- BAD: "how to teach" → Gets generic teaching content ❌

Extract the FULL formation name (e.g., "skip change of step" not just "skip change") and optionally add "points to observe" or "teaching points" to get the specific teaching guidance for that formation.

IMPORTANT: When presenting dances, ALWAYS include a link to the Strathspey Server for each dance.
Format links as: https://my.strathspey.org/dd/dance/{dance_id}/
where {dance_id} is the 'id' field from the dance data.
Example: For a dance with id=1786, link to https://my.strathspey.org/dd/dance/1786/
Make the dance name clickable by formatting as: [Dance Name](https://my.strathspey.org/dd/dance/{id}/)
""")]

        grounding_context = state.get("grounding_context", "").strip()
        if grounding_context:
            system_messages.append(SystemMessage(content=grounding_context))

        messages = system_messages + messages
        
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
            "route": "",
            "grounding_route": "dance_planner",
            "grounding_context": "",
            "grounding_response": "",
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
            # Clean up database connections properly
            from database import DatabasePool
            print("\n🧹 Cleaning up...", file=sys.stderr)
            pool = await DatabasePool.get_instance()
            await pool.close_all()
    
    except Exception as e:
        print(f"Failed to start agent: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
