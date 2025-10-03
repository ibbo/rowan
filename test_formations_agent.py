#!/usr/bin/env python3
"""
Test script to demonstrate the list_formations tool with the dance agent.
Shows how LLMs can now discover formations before searching for dances.
"""

import asyncio
import sys
from dance_agent import run_agent_query

async def test_formations_queries():
    """Test various queries that would benefit from the list_formations tool."""
    
    test_queries = [
        "What are the most popular formations in Scottish Country Dancing?",
        "Show me all formations that involve reels",
        "What allemande variations are available?",
        "List formations containing 'poussette'",
        "What are some common formations I should know as a beginner?",
    ]
    
    print("=" * 80)
    print("Testing list_formations tool with Dance Agent")
    print("=" * 80)
    print()
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'=' * 80}")
        print(f"TEST {i}: {query}")
        print(f"{'=' * 80}\n")
        
        try:
            # Run the query through the agent
            await run_agent_query(query)
            print()
        except Exception as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            continue
    
    print("\n" + "=" * 80)
    print("All formation tests completed!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_formations_queries())
