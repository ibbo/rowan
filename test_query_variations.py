#!/usr/bin/env python3
"""Test different query phrasings to see what results we get."""

import asyncio
from dotenv import load_dotenv

async def test_variations():
    load_dotenv()
    
    from dance_tools import search_manual
    
    queries = [
        "skip change of step",
        "how to teach skip change of step",
        "teaching skip change",
        "skip change teaching points",
        "points to observe skip change of step",
    ]
    
    for query in queries:
        print("\n" + "="*80)
        print(f"QUERY: '{query}'")
        print("="*80)
        
        result = await search_manual.ainvoke({
            "query": query,
            "num_results": 3
        })
        
        # Show first 800 chars to see what sections we get
        print(result[:800])
        print("\n[...truncated...]")

if __name__ == "__main__":
    asyncio.run(test_variations())
