#!/usr/bin/env python3
"""
Lesson Planner Agent for Scottish Country Dance classes.

A dedicated LangGraph-based agent for creating comprehensive lesson plans
with full dance cribs, teaching points from the RSCDS manual, and export capabilities.
"""

import asyncio
import sys
from typing import Annotated, Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict
from dotenv import load_dotenv

load_dotenv()

# Import tools from both modules
from dance_tools import (
    find_dances,
    get_dance_detail,
    search_cribs,
    list_formations,
    search_manual,
    find_videos,
    find_recordings,
)
from lesson_tools import (
    get_full_crib,
    get_teaching_points_for_dance,
    export_lesson_plan,
    save_lesson_plan,
    load_lesson_plan,
    list_lesson_plans,
    delete_lesson_plan,
    format_lesson_plan_markdown,
)
from llm_providers import get_provider


class LessonPlannerState(TypedDict):
    """State that flows through the lesson planner graph."""
    messages: Annotated[list, add_messages]
    lesson_plan: Optional[Dict[str, Any]]
    plan_status: str  # 'gathering', 'selecting', 'enriching', 'reviewing', 'finalized'


# System prompt for the lesson planner agent
LESSON_PLANNER_SYSTEM_PROMPT = """You are an expert Scottish Country Dance teacher planning a lesson.

Your role is to create comprehensive, detailed lesson plans that include:
1. **Full dance cribs** - Not summaries, but complete instructions for each dance
2. **Teaching points** - Specific guidance from the RSCDS manual for formations in each dance
3. **Timing and structure** - How to organize the class time effectively

## Available Tools

**Dance Selection:**
- `find_dances`: Search for dances by type, bars, level, etc. ALWAYS use random_variety=True
- `search_cribs`: Find dances containing specific formations/figures
- `list_formations`: Discover available formations

**Detailed Information:**
- `get_full_crib`: Get the COMPLETE crib for a dance (use this for lesson plans!)
- `get_dance_detail`: Get dance metadata and formations
- `get_teaching_points_for_dance`: Get RSCDS manual teaching guidance for a dance's formations
- `search_manual`: Search the RSCDS manual directly for teaching advice

**Supporting Materials:**
- `find_videos`: Find demonstration videos for dances
- `find_recordings`: Find music recordings for dances

**Lesson Plan Management:**
- `save_lesson_plan`: Save the plan for later
- `load_lesson_plan`: Load a previously saved plan
- `list_lesson_plans`: List saved plans
- `export_lesson_plan`: Export plan as Markdown

## Lesson Planning Process

When asked to plan a lesson:

1. **Understand Requirements**: Ask clarifying questions if needed about:
   - Class duration (e.g., 45 minutes, 1.5 hours)
   - Dancer level (beginner, intermediate, advanced)
   - Focus areas (specific formations, dance types)
   - Number of dances desired

2. **Select Appropriate Dances**: 
   - Choose dances that match the level and time constraints
   - Vary the dance types (mix of reels, jigs, strathspeys)
   - Consider progressions - start easier, build complexity
   - Use find_dances with appropriate filters

3. **Get Complete Information**:
   - For EACH selected dance, call `get_full_crib` to get the complete crib
   - For EACH dance, call `get_teaching_points_for_dance` to get manual guidance
   - NEVER give abbreviated or summarized cribs in a lesson plan

4. **Structure the Plan**:
   - Include warm-up/technique time if appropriate
   - Order dances logically (easier to harder, or by theme)
   - Estimate time per dance including walkthrough and dancing

5. **Present the Complete Plan**:
   - Show all dances with their FULL cribs
   - Include teaching points for tricky formations
   - Provide timing breakdown
   - Offer to save or export the plan

## Critical Rules

⚠️ **ALWAYS get full cribs** - Use `get_full_crib` for each dance, never summarize
⚠️ **ALWAYS get teaching points** - Use `get_teaching_points_for_dance` for each dance
⚠️ **Include links** - Format dance names as links to Strathspey Server
⚠️ **Be thorough** - A lesson plan should be ready to print and use in class

Remember: Teachers need COMPLETE information to teach effectively. A good lesson plan
has everything they need without having to look anything up separately.
"""


class LessonPlannerAgent:
    """Scottish Country Dance Lesson Planner Agent with comprehensive planning capabilities."""

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        temperature: float = 0,
        api_key: str | None = None
    ):
        """
        Initialize the lesson planner agent.
        
        Args:
            provider: LLM provider name ('openai', 'google')
            model: Model identifier
            temperature: Sampling temperature (0 = deterministic)
        """
        print(f"🎓 Initializing Lesson Planner Agent with {provider}/{model}", file=sys.stderr)
        
        # Get the provider instance (matching scd_agent.py pattern)
        llm_provider = get_provider(provider)
        
        # Check for API key
        import os
        env_var = llm_provider.get_env_var_name()
        if not api_key and not os.getenv(env_var):
            raise RuntimeError(
                f"API key not found. Please set {env_var} environment variable.\n"
                f"Example: export {env_var}='your-key-here'"
            )
        
        # Initialize LLM
        self.llm = llm_provider.create_chat_llm(model, temperature, api_key)
        self.provider = provider
        self.model = model
        self.api_key = api_key
        
        # Combine all tools for lesson planning
        self.tools = [
            # Dance selection
            find_dances,
            search_cribs,
            list_formations,
            # Detailed info
            get_full_crib,
            get_dance_detail,
            get_teaching_points_for_dance,
            search_manual,
            # Supporting materials
            find_videos,
            find_recordings,
            # Plan management
            save_lesson_plan,
            load_lesson_plan,
            list_lesson_plans,
            export_lesson_plan,
            delete_lesson_plan,
        ]
        
        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Build the agent graph
        self.graph = self._build_graph()
        
        print(f"✅ Lesson Planner Agent ready with {len(self.tools)} tools", file=sys.stderr)

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow for lesson planning."""
        
        # Create the graph
        graph = StateGraph(LessonPlannerState)
        
        # Add nodes
        graph.add_node("planner", self._planner_node)
        graph.add_node("tools", ToolNode(self.tools))
        
        # Set entry point
        graph.set_entry_point("planner")
        
        # Add conditional edges
        graph.add_conditional_edges(
            "planner",
            self._route_after_planner,
            {
                "tools": "tools",
                "end": END
            }
        )
        
        # Tools always return to planner
        graph.add_edge("tools", "planner")
        
        return graph.compile()

    def _planner_node(self, state: LessonPlannerState) -> dict:
        """Main planning node that processes requests and calls tools."""
        print("\n🎓 Lesson Planner: Processing...", file=sys.stderr)
        
        messages = state["messages"]
        
        # Add system message if not present
        has_system_message = any(isinstance(msg, SystemMessage) for msg in messages)
        
        if not has_system_message:
            system_msg = SystemMessage(content=LESSON_PLANNER_SYSTEM_PROMPT)
            messages = [system_msg] + messages
        
        # Invoke LLM with tools
        response = self.llm_with_tools.invoke(messages)
        
        tool_call_count = len(response.tool_calls) if hasattr(response, 'tool_calls') else 0
        print(f"🎓 Lesson Planner: {'Using ' + str(tool_call_count) + ' tools' if tool_call_count else 'Responding'}", file=sys.stderr)
        
        return {"messages": [response]}

    def _route_after_planner(self, state: LessonPlannerState) -> str:
        """Route based on whether tools need to be called."""
        last_message = state["messages"][-1]
        
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "end"

    async def ainvoke(self, user_input: str, config: dict = None) -> dict:
        """
        Async invoke the lesson planner with a user request.
        
        Args:
            user_input: The lesson planning request
            config: Optional config dict (for thread_id, etc.)
        
        Returns:
            The final state with messages
        """
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "lesson_plan": None,
            "plan_status": "gathering"
        }
        
        config = config or {}
        
        result = await self.graph.ainvoke(initial_state, config)
        return result

    def invoke(self, user_input: str, config: dict = None) -> dict:
        """
        Synchronous invoke (runs async in event loop).
        
        Args:
            user_input: The lesson planning request
            config: Optional config dict
        
        Returns:
            The final state with messages
        """
        return asyncio.run(self.ainvoke(user_input, config))

    async def astream(self, user_input: str, config: dict = None):
        """
        Stream the lesson planner responses.
        
        Yields state updates as the agent processes the request.
        """
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "lesson_plan": None,
            "plan_status": "gathering"
        }
        
        config = config or {}
        
        async for event in self.graph.astream(initial_state, config):
            yield event


async def main():
    """Interactive lesson planning session."""
    print("\n🎓 Scottish Country Dance Lesson Planner 🎓")
    print("=" * 50)
    print("Plan comprehensive lessons with full cribs and teaching points.")
    print("Type 'quit' to exit.\n")
    
    # Initialize agent
    agent = LessonPlannerAgent()
    
    while True:
        try:
            user_input = input("\n📝 Describe your lesson: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Happy teaching!")
                break
            
            print("\n🎓 Planning your lesson...\n")
            
            result = await agent.ainvoke(user_input)
            
            # Print the final response
            for msg in result["messages"]:
                if isinstance(msg, AIMessage) and msg.content:
                    print(msg.content)
                    
        except KeyboardInterrupt:
            print("\n\n👋 Happy teaching!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            continue
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
