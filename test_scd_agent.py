#!/usr/bin/env python3
"""
Test script for the new SCD Agent with prompt checking and dance planning.
"""

import asyncio
from dotenv import load_dotenv
from scd_agent import SCDAgent


async def test_agent():
    """Test the agent with various queries."""
    load_dotenv()
    
    print("=" * 60)
    print("Testing SCD Agent with Prompt Checker and Dance Planner")
    print("=" * 60)
    
    agent = SCDAgent()
    config = {"configurable": {"thread_id": "test_session"}}
    
    try:
        # Test cases
        test_queries = [
            # Valid SCD queries
            ("Find me some 32-bar reels", True),
            ("What dances have poussette moves?", True),
            ("Tell me about The Reel of the 51st Division", True),
            
            # Invalid queries (should be rejected)
            ("What's the weather today?", False),
            ("How do I cook haggis?", False),
        ]
        
        for query, should_accept in test_queries:
            print(f"\n{'='*60}")
            print(f"Query: {query}")
            print(f"Expected: {'ACCEPT' if should_accept else 'REJECT'}")
            print(f"{'='*60}")
            
            result = await agent.ainvoke(query, config)
            
            # Check the result
            final_message = result["messages"][-1]
            is_accepted = result.get("is_scd_query", False)
            
            print(f"\nActual: {'ACCEPT' if is_accepted else 'REJECT'}")
            print(f"Response: {final_message.content[:200]}...")
            
            # Verify
            if is_accepted == should_accept:
                print("✅ TEST PASSED")
            else:
                print("❌ TEST FAILED")
        
        print(f"\n{'='*60}")
        print("All tests completed!")
        print(f"{'='*60}")
    finally:
        # Clean up MCP client connections
        from dance_tools import mcp_client
        print("\n🧹 Cleaning up test resources...")
        await mcp_client.close()


if __name__ == "__main__":
    asyncio.run(test_agent())
