#!/usr/bin/env python3
"""Direct test of MCP server with intensity parameters."""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_intensity_filter():
    """Test the intensity filtering directly via MCP."""
    
    # Setup server parameters
    db_path = str(Path("data/scddb/scddb.sqlite").resolve())
    server_script = str(Path("mcp_scddb_server.py").resolve())
    
    params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env={
            "SCDDB_SQLITE": db_path,
            "SCDDB_LOG_LEVEL": "INFO",
        },
    )
    
    print("=" * 80)
    print("Testing MCP Server Intensity Filtering")
    print("=" * 80)
    
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List tools to verify intensity parameters are exposed
            print("\n1. Listing available tools...")
            tools_result = await session.list_tools()
            
            find_dances_tool = None
            for tool in tools_result.tools:
                if tool.name == "find_dances":
                    find_dances_tool = tool
                    break
            
            if find_dances_tool:
                print(f"\n✓ Found 'find_dances' tool")
                print(f"  Description: {find_dances_tool.description[:100]}...")
                print(f"\n  Parameters:")
                for param_name, param_info in find_dances_tool.inputSchema.get("properties", {}).items():
                    print(f"    - {param_name}: {param_info.get('description', 'N/A')[:80]}")
            else:
                print("✗ 'find_dances' tool not found!")
                return
            
            # Test 1: Easy reels (max_intensity=40)
            print("\n" + "=" * 80)
            print("TEST 1: Easy Reels (kind=Reel, max_intensity=40)")
            print("=" * 80)
            
            try:
                result = await session.call_tool(
                    "find_dances",
                    arguments={
                        "kind": "Reel",
                        "max_intensity": 40,
                        "limit": 10
                    }
                )
                
                dances = json.loads(result.content[0].text)
                print(f"\n✓ Query successful! Found {len(dances)} dances")
                
                for i, dance in enumerate(dances[:5], 1):
                    intensity = dance.get('intensity', 'N/A')
                    print(f"  {i}. {dance['name']} - Intensity: {intensity}, Bars: {dance['bars']}")
                    
            except Exception as e:
                print(f"\n✗ Query failed: {e}")
                import traceback
                traceback.print_exc()
            
            # Test 2: Hard dances sorted by difficulty
            print("\n" + "=" * 80)
            print("TEST 2: Hard Dances (min_intensity=70, sort_by_intensity=desc)")
            print("=" * 80)
            
            try:
                result = await session.call_tool(
                    "find_dances",
                    arguments={
                        "min_intensity": 70,
                        "sort_by_intensity": "desc",
                        "limit": 10
                    }
                )
                
                dances = json.loads(result.content[0].text)
                print(f"\n✓ Query successful! Found {len(dances)} dances")
                
                for i, dance in enumerate(dances[:5], 1):
                    intensity = dance.get('intensity', 'N/A')
                    print(f"  {i}. {dance['name']} - Intensity: {intensity}, Type: {dance['kind']}")
                    
            except Exception as e:
                print(f"\n✗ Query failed: {e}")
                import traceback
                traceback.print_exc()
            
            # Test 3: Medium difficulty with sorting
            print("\n" + "=" * 80)
            print("TEST 3: Medium Difficulty (min=40, max=70, sort_by_intensity=asc)")
            print("=" * 80)
            
            try:
                result = await session.call_tool(
                    "find_dances",
                    arguments={
                        "min_intensity": 40,
                        "max_intensity": 70,
                        "sort_by_intensity": "asc",
                        "limit": 10
                    }
                )
                
                dances = json.loads(result.content[0].text)
                print(f"\n✓ Query successful! Found {len(dances)} dances")
                
                for i, dance in enumerate(dances[:5], 1):
                    intensity = dance.get('intensity', 'N/A')
                    print(f"  {i}. {dance['name']} - Intensity: {intensity}, Type: {dance['kind']}")
                    
            except Exception as e:
                print(f"\n✗ Query failed: {e}")
                import traceback
                traceback.print_exc()
            
            print("\n" + "=" * 80)
            print("✅ All MCP tests completed!")
            print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_intensity_filter())
