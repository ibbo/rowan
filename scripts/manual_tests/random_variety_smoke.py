#!/usr/bin/env python3
"""
Test script to verify that the agent now uses random_variety=True by default.
This will make two queries and check if we get different results.
"""

import asyncio
import sys
from dotenv import load_dotenv
from scd_agent import SCDAgent
from dance_tools import mcp_client

async def test_random_variety():
    """Test that the agent uses random_variety by default."""
    load_dotenv()
    
    print("🧪 Testing Random Variety Default Behavior")
    print("=" * 60)
    
    # Initialize agent
    agent = SCDAgent()
    await mcp_client.setup()
    
    # Test query
    test_query = "Find me some 32-bar reels"
    
    print(f"\n📝 Test Query: '{test_query}'")
    print("\n🔄 Running query twice to check for variety...\n")
    
    # First query
    print("Query 1:")
    print("-" * 40)
    config1 = {"configurable": {"thread_id": "test_session_1"}}
    response1 = await agent.graph.ainvoke(
        {"messages": [{"role": "user", "content": test_query}]},
        config1
    )
    
    # Extract dance names from first response
    final_msg1 = response1["messages"][-1].content
    print(final_msg1[:500])  # Print first 500 chars
    
    # Second query (new session to avoid memory)
    print("\n\nQuery 2:")
    print("-" * 40)
    config2 = {"configurable": {"thread_id": "test_session_2"}}
    response2 = await agent.graph.ainvoke(
        {"messages": [{"role": "user", "content": test_query}]},
        config2
    )
    
    # Extract dance names from second response
    final_msg2 = response2["messages"][-1].content
    print(final_msg2[:500])  # Print first 500 chars
    
    print("\n\n" + "=" * 60)
    print("✅ Test Complete!")
    print("\nIf the two responses show different dances, random_variety is working!")
    print("If they show the same dances (alphabetically), random_variety is NOT being used.")
    
    # Cleanup
    await mcp_client.close()

if __name__ == "__main__":
    asyncio.run(test_random_variety())
