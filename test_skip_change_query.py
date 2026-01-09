#!/usr/bin/env python3
"""Test the skip change teaching query to debug the issue."""

import asyncio
import sys
from dotenv import load_dotenv
from scd_agent import SCDAgent

async def test_query():
    """Test the skip change query."""
    load_dotenv()
    
    print("Initializing agent...")
    agent = SCDAgent()
    
    query = "How do I teach the skip change?"
    print(f"\nQuery: {query}")
    print("="*80)
    
    config = {"configurable": {"thread_id": "test_skip_change"}}
    
    # Stream the response to see what tools are called
    async for chunk in agent.graph.astream(
        {
            "messages": [{"role": "user", "content": query}],
            "is_scd_query": False,
            "route": ""
        },
        config
    ):
        print(f"\nChunk: {chunk}")
    
    # Get final state
    final_state = await agent.graph.aget_state(config)
    print("\n" + "="*80)
    print("FINAL STATE:")
    if final_state and hasattr(final_state, "values"):
        messages = final_state.values.get("messages", [])
        for i, msg in enumerate(messages):
            print(f"\nMessage {i}: {type(msg).__name__}")
            if hasattr(msg, "content"):
                print(f"Content: {msg.content[:500]}")
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                print(f"Tool calls: {msg.tool_calls}")
    
    # Cleanup
    from dance_tools import mcp_client
    await mcp_client.close()

if __name__ == "__main__":
    asyncio.run(test_query())
