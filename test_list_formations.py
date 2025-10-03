#!/usr/bin/env python3
"""
Test script for the list_formations MCP tool.
Tests various filtering and sorting options.
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_list_formations():
    """Test the list_formations tool with various parameters."""
    
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_scddb_server.py"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("=" * 80)
            print("TEST 1: List top 10 most popular formations")
            print("=" * 80)
            result = await session.call_tool(
                "list_formations",
                arguments={
                    "sort_by": "popularity",
                    "limit": 10
                }
            )
            formations = json.loads(result.content[0].text)
            print(f"Found {len(formations)} formations:")
            for f in formations:
                print(f"  - {f['name']:<40} (token: {f['formation_token']:<20} used in {f['usage_count']} dances)")
            
            print("\n" + "=" * 80)
            print("TEST 2: List formations alphabetically (first 15)")
            print("=" * 80)
            result = await session.call_tool(
                "list_formations",
                arguments={
                    "sort_by": "alphabetical",
                    "limit": 15
                }
            )
            formations = json.loads(result.content[0].text)
            print(f"Found {len(formations)} formations:")
            for f in formations:
                print(f"  - {f['name']:<40} (token: {f['formation_token']:<20} used in {f['usage_count']} dances)")
            
            print("\n" + "=" * 80)
            print("TEST 3: Search for formations containing 'reel'")
            print("=" * 80)
            result = await session.call_tool(
                "list_formations",
                arguments={
                    "name_contains": "reel",
                    "sort_by": "popularity",
                    "limit": 20
                }
            )
            formations = json.loads(result.content[0].text)
            print(f"Found {len(formations)} formations with 'reel' in name:")
            for f in formations:
                print(f"  - {f['name']:<40} (token: {f['formation_token']:<20} used in {f['usage_count']} dances)")
            
            print("\n" + "=" * 80)
            print("TEST 4: Search for formations containing 'allemande'")
            print("=" * 80)
            result = await session.call_tool(
                "list_formations",
                arguments={
                    "name_contains": "allemande",
                    "sort_by": "popularity",
                    "limit": 10
                }
            )
            formations = json.loads(result.content[0].text)
            print(f"Found {len(formations)} formations with 'allemande' in name:")
            for f in formations:
                print(f"  - {f['name']:<40} (token: {f['formation_token']:<20} used in {f['usage_count']} dances)")
            
            print("\n" + "=" * 80)
            print("TEST 5: Search for formations containing 'poussette'")
            print("=" * 80)
            result = await session.call_tool(
                "list_formations",
                arguments={
                    "name_contains": "poussette",
                    "sort_by": "popularity",
                    "limit": 10
                }
            )
            formations = json.loads(result.content[0].text)
            print(f"Found {len(formations)} formations with 'poussette' in name:")
            for f in formations:
                print(f"  - {f['name']:<40} (token: {f['formation_token']:<20} used in {f['usage_count']} dances)")
            
            print("\n" + "=" * 80)
            print("TEST 6: Get formation tokens for use in find_dances")
            print("=" * 80)
            result = await session.call_tool(
                "list_formations",
                arguments={
                    "name_contains": "hands across",
                    "sort_by": "popularity",
                    "limit": 5
                }
            )
            formations = json.loads(result.content[0].text)
            print(f"Found {len(formations)} 'hands across' formations:")
            print("\nFormation tokens that can be used with find_dances:")
            for f in formations:
                print(f"  - '{f['formation_token']}' for {f['name']} (used in {f['usage_count']} dances)")
            
            print("\n" + "=" * 80)
            print("All tests completed successfully!")
            print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_list_formations())
