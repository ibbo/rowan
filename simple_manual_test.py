#!/usr/bin/env python3
"""Simple test of search_manual tool."""

import asyncio
from dotenv import load_dotenv

async def test():
    load_dotenv()
    
    from dance_tools import search_manual
    
    print("="*80)
    print("QUERY: 'how to teach skip change of step'")
    print("="*80)
    
    result = await search_manual.ainvoke({
        "query": "how to teach skip change of step",
        "num_results": 3
    })
    
    print(result)
    
    # Check what's in the result
    if "pas de basque" in result.lower():
        print("\n⚠️  WARNING: Result contains 'pas de basque'")
        # Check if it's just mentioned in context vs being the main content
        if "5.4.2" in result:  # Pas de basque section number
            print("   - Contains pas de basque section (5.4.2)")
        if "5.4.1" in result:  # Skip change section number
            print("   - ✅ Also contains skip change section (5.4.1)")
    
    if "skip change" in result.lower():
        print("\n✅ Result contains 'skip change'")
        if "points to observe" in result.lower():
            print("   - ✅ Contains 'Points to observe' section")

if __name__ == "__main__":
    asyncio.run(test())
