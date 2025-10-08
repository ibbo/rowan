#!/usr/bin/env python3
"""
Test to reproduce the "reel of 3" confusion issue.
The agent confuses "Reel" (dance type) with "reel of three" (formation).
"""
import asyncio
from dotenv import load_dotenv
from scd_agent import SCDAgent
from langchain_core.messages import HumanMessage

async def test_reel_of_3():
    """Test the agent's handling of 'reel of 3' queries."""
    load_dotenv()
    
    print("🧪 Testing: 'Find dances with a reel of 3' query")
    print("=" * 60)
    
    agent = SCDAgent()
    
    # Test query
    query = "Find dances with a reel of 3"
    
    print(f"\n📝 Query: {query}")
    print("-" * 60)
    
    config = {"configurable": {"thread_id": "test_session"}}
    result = await agent.ainvoke(query, config)
    
    # Display messages
    print("\n📋 Agent Response:")
    print("-" * 60)
    for msg in result["messages"]:
        if hasattr(msg, 'content'):
            print(f"\n{msg.__class__.__name__}: {msg.content[:500]}...")
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            print(f"\nTool Calls: {msg.tool_calls}")
    
    # Clean up
    from dance_tools import mcp_client
    await mcp_client.close()

if __name__ == "__main__":
    asyncio.run(test_reel_of_3())
