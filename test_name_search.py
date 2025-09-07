#!/usr/bin/env python3
"""
Test script to verify both name and ID searches work in the enhanced MCP server.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_search_functionality():
    """Test both name search and ID search functionality with debug output."""
    
    # Setup server parameters with debug logging
    db_path = os.environ.get("SCDDB_SQLITE", "data/scddb/scddb.sqlite")
    db_path = str(Path(db_path).resolve())
    
    server_script = str((Path(__file__).parent / "mcp_scddb_server.py").resolve())
    
    params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env={
            "SCDDB_SQLITE": db_path,
            "SCDDB_LOG_LEVEL": "DEBUG",  # Enable debug logging
        },
    )
    
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            print("🧪 Testing Enhanced Dance Search Functionality")
            print("=" * 60)
            
            # Test 1: Name search (this should now work!)
            print("\n🔍 Test 1: Search by name containing 'Mairi'")
            try:
                result = await session.call_tool(
                    name="find_dances", 
                    arguments={"name_contains": "Mairi", "limit": 3}
                )
                
                content = []
                for block in result.content:
                    if hasattr(block, 'text'):
                        parsed = json.loads(block.text)
                        content.extend(parsed if isinstance(parsed, list) else [parsed])
                
                if content:
                    print(f"✅ Found {len(content)} dances:")
                    for dance in content[:3]:  # Show first 3
                        print(f"   - ID {dance['id']}: {dance['name']} ({dance['kind']})")
                else:
                    print("❌ No dances found")
                    
            except Exception as e:
                print(f"❌ Error in name search: {e}")
            
            # Test 2: ID search (existing functionality)
            print("\n🔍 Test 2: Search by ID (existing functionality)")
            try:
                # Use ID from first result if available, otherwise use a known ID
                test_id = content[0]['id'] if content else 18396
                result = await session.call_tool(
                    name="dance_detail", 
                    arguments={"dance_id": test_id}
                )
                
                detail_content = []
                for block in result.content:
                    if hasattr(block, 'text'):
                        parsed = json.loads(block.text)
                        detail_content.append(parsed)
                
                if detail_content and 'dance' in detail_content[0]:
                    dance = detail_content[0]['dance']
                    print(f"✅ Found dance by ID {test_id}:")
                    print(f"   - Name: {dance['name']}")
                    print(f"   - Kind: {dance['kind']}")
                    print(f"   - Formation: {dance['metaform']}")
                    print(f"   - Bars: {dance['bars']}")
                else:
                    print("❌ No dance found by ID")
                    
            except Exception as e:
                print(f"❌ Error in ID search: {e}")
            
            # Test 3: Combined search (name + kind)
            print("\n🔍 Test 3: Combined search (name contains 'Highland' + kind 'Reel')")
            try:
                result = await session.call_tool(
                    name="find_dances", 
                    arguments={"name_contains": "Highland", "kind": "Reel", "limit": 2}
                )
                
                combined_content = []
                for block in result.content:
                    if hasattr(block, 'text'):
                        parsed = json.loads(block.text)
                        combined_content.extend(parsed if isinstance(parsed, list) else [parsed])
                
                if combined_content:
                    print(f"✅ Found {len(combined_content)} Highland Reels:")
                    for dance in combined_content:
                        print(f"   - ID {dance['id']}: {dance['name']} ({dance['kind']})")
                else:
                    print("❌ No Highland Reels found")
                    
            except Exception as e:
                print(f"❌ Error in combined search: {e}")
            
            print("\n🎉 Testing complete!")

if __name__ == "__main__":
    asyncio.run(test_search_functionality())
