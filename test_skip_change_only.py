#!/usr/bin/env python3
"""Test 'skip change' vs 'skip change of step'."""

import asyncio
from dotenv import load_dotenv

async def test():
    load_dotenv()
    
    from dance_tools import search_manual
    
    print("="*80)
    print("TEST: 'skip change' (without 'of step')")
    print("="*80)
    
    result = await search_manual.ainvoke({
        "query": "skip change",
        "num_results": 5
    })
    
    print(result[:1500])

if __name__ == "__main__":
    asyncio.run(test())
