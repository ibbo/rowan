#!/usr/bin/env python3
"""
Debug the agent with skip change of step query.
Shows exactly what the search_manual tool returns and what the agent does with it.
"""

import asyncio
import sys
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

async def test_agent_with_debug():
    load_dotenv()
    
    from scd_agent import SCDAgent
    from dance_tools import mcp_client
    
    print("="*80)
    print("DEBUG TEST: Skip Change of Step Query")
    print("="*80)
    
    # Initialize
    print("\n1. Initializing agent...")
    agent = SCDAgent()
    await mcp_client.setup()
    print("   ✅ Agent initialized")
    
    # Create a test query
    query = "how to teach skip change of step"
    print(f"\n2. Query: '{query}'")
    print("   Processing...")
    
    # Run the agent with streaming to see each step
    config = {"configurable": {"thread_id": "debug_test"}}
    
    print("\n3. Agent execution steps:")
    print("-"*80)
    
    step_num = 0
    async for chunk in agent.graph.astream(
        {
            "messages": [HumanMessage(content=query)],
            "is_scd_query": False,
            "route": ""
        },
        config
    ):
        step_num += 1
        print(f"\n--- STEP {step_num} ---")
        
        for node_name, node_data in chunk.items():
            print(f"\nNode: {node_name}")
            
            # Show messages
            if "messages" in node_data:
                for msg in node_data["messages"]:
                    msg_type = type(msg).__name__
                    print(f"  Message type: {msg_type}")
                    
                    # Show tool calls
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for call in msg.tool_calls:
                            print(f"  🔧 Tool call: {call.get('name')}")
                            print(f"     Args: {call.get('args')}")
                    
                    # Show tool results (this is what we really care about!)
                    if hasattr(msg, "content") and msg.content:
                        content = msg.content
                        if msg_type == "ToolMessage":
                            print(f"  📥 Tool result (first 500 chars):")
                            print(f"     {str(content)[:500]}")
                            if len(str(content)) > 500:
                                print(f"     ... [truncated, total length: {len(str(content))} chars]")
                            
                            # Check if this is search_manual result
                            if "skip change" in str(content).lower():
                                print("\n  ⚠️  ANALYSIS: This tool result mentions 'skip change'")
                            if "pas de basque" in str(content).lower():
                                print("  ⚠️  ANALYSIS: This tool result mentions 'pas de basque'")
                            if "5.4.1" in str(content):
                                print("  ✅ ANALYSIS: Contains section 5.4.1 (skip change)")
                            if "5.4.2" in str(content):
                                print("  ❌ ANALYSIS: Contains section 5.4.2 (pas de basque) - WRONG!")
                        
                        elif msg_type == "AIMessage" and not hasattr(msg, "tool_calls"):
                            print(f"  💬 AI response (first 500 chars):")
                            print(f"     {str(content)[:500]}")
                            if len(str(content)) > 500:
                                print(f"     ... [truncated, total length: {len(str(content))} chars]")
    
    # Get final response
    print("\n" + "="*80)
    print("4. FINAL RESPONSE:")
    print("="*80)
    
    final_state = await agent.graph.aget_state(config)
    if final_state and hasattr(final_state, "values"):
        messages = final_state.values.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                continue
            content = getattr(msg, "content", "")
            if isinstance(content, str) and content and not content.startswith("You are"):
                print(content)
                
                # Analysis
                print("\n" + "="*80)
                print("5. RESPONSE ANALYSIS:")
                print("="*80)
                
                if "spring onto the right foot" in content.lower() and "bring the left foot in front" in content.lower():
                    print("❌ ERROR: Response contains PAS DE BASQUE instructions!")
                    print("   (spring onto right, left to third, etc.)")
                elif "hop on the left foot" in content.lower() or "hop on the leĞ foot" in content.lower():
                    print("✅ CORRECT: Response contains SKIP CHANGE instructions!")
                    print("   (hop on left foot, extend right leg)")
                else:
                    print("⚠️  UNCLEAR: Can't determine which formation is being described")
                
                if "5.4.1" in content:
                    print("✅ References section 5.4.1 (skip change)")
                if "5.4.2" in content:
                    print("❌ References section 5.4.2 (pas de basque)")
                
                break
    
    # Cleanup
    await mcp_client.close()

if __name__ == "__main__":
    asyncio.run(test_agent_with_debug())
