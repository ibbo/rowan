#!/usr/bin/env python3
"""
Quick integration test for list_formations tool.
Tests the tool directly and shows how it helps LLMs search more effectively.
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_formation_workflow():
    """
    Demonstrate a typical workflow:
    1. User asks for dances with a specific formation
    2. Agent uses list_formations to find the correct formation token
    3. Agent uses find_dances with the formation_token for precise results
    """
    
    server_params = StdioServerParameters(
        command="python3",
        args=["mcp_scddb_server.py"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("=" * 80)
            print("WORKFLOW: Finding dances with 'Allemande for 3 couples'")
            print("=" * 80)
            
            # Step 1: List formations to find the right token
            print("\nStep 1: Search for allemande formations...")
            result = await session.call_tool(
                "list_formations",
                arguments={
                    "name_contains": "allemande",
                    "sort_by": "popularity",
                    "limit": 10
                }
            )
            formations = json.loads(result.content[0].text)
            
            print(f"Found {len(formations)} allemande formations:")
            for f in formations[:5]:
                print(f"  - {f['name']:<45} token: {f['formation_token']:<25} ({f['usage_count']} dances)")
            
            # Find the specific formation we want
            target_formation = next((f for f in formations if "3 couples" in f['name'] and "circulating" not in f['name']), None)
            
            if target_formation:
                print(f"\n✓ Found target formation: '{target_formation['name']}'")
                print(f"  Token: {target_formation['formation_token']}")
                print(f"  Used in {target_formation['usage_count']} dances")
                
                # Step 2: Use the formation token to find dances
                print(f"\nStep 2: Finding dances with this formation...")
                result = await session.call_tool(
                    "find_dances",
                    arguments={
                        "formation_token": target_formation['formation_token'],
                        "limit": 5
                    }
                )
                dances = json.loads(result.content[0].text)
                
                print(f"\nFound {len(dances)} dances with '{target_formation['name']}':")
                for dance in dances:
                    print(f"  - {dance['name']:<40} ({dance['kind']}, {dance['bars']} bars)")
            
            print("\n" + "=" * 80)
            print("WORKFLOW: Finding most popular formations for beginners")
            print("=" * 80)
            
            print("\nListing top 15 most popular formations (good for beginners)...")
            result = await session.call_tool(
                "list_formations",
                arguments={
                    "sort_by": "popularity",
                    "limit": 15
                }
            )
            formations = json.loads(result.content[0].text)
            
            print(f"\nTop {len(formations)} most common formations in SCD:")
            for i, f in enumerate(formations, 1):
                print(f"  {i:2d}. {f['name']:<45} ({f['usage_count']:4d} dances)")
            
            print("\n" + "=" * 80)
            print("WORKFLOW: Exploring specific formation types")
            print("=" * 80)
            
            # Test different formation searches
            searches = [
                ("reel", 8),
                ("hands across", 5),
                ("figure of eight", 5),
                ("rights and lefts", 5),
            ]
            
            for search_term, limit in searches:
                print(f"\nSearching for '{search_term}' formations...")
                result = await session.call_tool(
                    "list_formations",
                    arguments={
                        "name_contains": search_term,
                        "sort_by": "popularity",
                        "limit": limit
                    }
                )
                formations = json.loads(result.content[0].text)
                
                print(f"Found {len(formations)} variations:")
                for f in formations:
                    print(f"  - {f['name']:<50} ({f['usage_count']:4d} dances)")
            
            print("\n" + "=" * 80)
            print("Integration test completed successfully!")
            print("=" * 80)
            print("\nKey Benefits for LLMs:")
            print("  ✓ Discover available formations without guessing")
            print("  ✓ Get exact formation tokens for precise searches")
            print("  ✓ Understand formation popularity and usage")
            print("  ✓ Explore variations of specific moves")
            print("  ✓ Provide better recommendations to users")

if __name__ == "__main__":
    asyncio.run(test_formation_workflow())
