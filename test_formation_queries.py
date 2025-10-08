#!/usr/bin/env python3
"""
Test various formation query variations to ensure the agent handles them correctly.
"""
import asyncio
from dotenv import load_dotenv
from scd_agent import SCDAgent

async def test_queries():
    """Test multiple formation query variations."""
    load_dotenv()
    
    queries = [
        "Find dances with a reel of 3",
        "Find dances with reels of three",
        "Show me dances that have poussette",
        "Find me some Reels",  # This should use kind='Reel'
        "Find 32-bar Jigs",  # This should use kind='Jig', max_bars=32
    ]
    
    agent = SCDAgent()
    
    for query in queries:
        print(f"\n{'='*70}")
        print(f"📝 Testing: {query}")
        print('='*70)
        
        config = {"configurable": {"thread_id": f"test_{query[:20]}"}}
        result = await agent.ainvoke(query, config)
        
        # Show what tools were called
        print("\n🔧 Tools Used:")
        for msg in result["messages"]:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    print(f"  ✓ {tool_call['name']}({tool_call['args']})")
        
        # Show final response preview
        final_message = result["messages"][-1]
        response_preview = final_message.content[:200] + "..." if len(final_message.content) > 200 else final_message.content
        print(f"\n💬 Response Preview:\n{response_preview}")
    
    # Clean up
    from dance_tools import mcp_client
    await mcp_client.close()

if __name__ == "__main__":
    asyncio.run(test_queries())
