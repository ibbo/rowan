#!/usr/bin/env python3
"""Test script for the new MCP SCDDB tools."""
import asyncio
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_scddb_server import call_tool

async def test_find_videos():
    """Test find_videos tool."""
    print("\n" + "="*60)
    print("Testing find_videos")
    print("="*60)
    
    # Test with dance name
    result = await call_tool("find_videos", {"dance_name": "Dashing White Sergeant", "limit": 3})
    data = json.loads(result[0].text)
    print(f"\nVideos for 'Dashing White Sergeant': {len(data)} found")
    if data:
        for v in data[:2]:
            print(f"  - {v.get('dance_name')}: {v.get('youtube_url')}")
    
    # Test editors picks
    result = await call_tool("find_videos", {"editors_pick": True, "limit": 5})
    data = json.loads(result[0].text)
    print(f"\nEditor's picks: {len(data)} found")
    if data:
        for v in data[:3]:
            print(f"  - {v.get('dance_name')}: {v.get('youtube_url')}")

async def test_find_recordings():
    """Test find_recordings tool."""
    print("\n" + "="*60)
    print("Testing find_recordings")
    print("="*60)
    
    # Test with dance name
    result = await call_tool("find_recordings", {"dance_name": "Mairi's Wedding", "limit": 5})
    data = json.loads(result[0].text)
    print(f"\nRecordings for 'Mairi's Wedding': {len(data)} found")
    if data:
        for r in data[:3]:
            print(f"  - {r.get('recording_name')} by {r.get('artist')} ({r.get('album')})")
    
    # Test with artist name
    result = await call_tool("find_recordings", {"artist_name": "Jim Lindsay", "limit": 5})
    data = json.loads(result[0].text)
    print(f"\nRecordings by 'Jim Lindsay': {len(data)} found")
    if data:
        for r in data[:3]:
            print(f"  - {r.get('recording_name')} ({r.get('album')})")

async def test_find_devisors():
    """Test find_devisors tool."""
    print("\n" + "="*60)
    print("Testing find_devisors")
    print("="*60)
    
    # Test top devisors
    result = await call_tool("find_devisors", {"min_dances": 100, "limit": 10})
    data = json.loads(result[0].text)
    print(f"\nTop devisors (100+ dances): {len(data)} found")
    for d in data[:5]:
        print(f"  - {d.get('name')}: {d.get('dance_count')} dances")
    
    # Test search by name
    result = await call_tool("find_devisors", {"name_contains": "Drewry", "limit": 5})
    data = json.loads(result[0].text)
    print(f"\nDevisors matching 'Drewry': {len(data)} found")
    for d in data:
        print(f"  - {d.get('name')}: {d.get('dance_count')} dances")

async def test_find_publications():
    """Test find_publications tool."""
    print("\n" + "="*60)
    print("Testing find_publications")
    print("="*60)
    
    # Test RSCDS publications
    result = await call_tool("find_publications", {"rscds_only": True, "sort_by": "name", "limit": 10})
    data = json.loads(result[0].text)
    print(f"\nRSCDS publications: {len(data)} found")
    for p in data[:5]:
        print(f"  - {p.get('name')} ({p.get('year')}): {p.get('dance_count')} dances")
    
    # Test search by name
    result = await call_tool("find_publications", {"name_contains": "Book", "rscds_only": True, "limit": 10})
    data = json.loads(result[0].text)
    print(f"\nRSCDS publications with 'Book': {len(data)} found")
    for p in data[:5]:
        print(f"  - {p.get('name')}: {p.get('dance_count')} dances")

async def test_get_publication_dances():
    """Test get_publication_dances tool."""
    print("\n" + "="*60)
    print("Testing get_publication_dances")
    print("="*60)
    
    # Get dances from RSCDS Book 1 (publication_id=1)
    result = await call_tool("get_publication_dances", {"publication_id": 1, "limit": 20})
    data = json.loads(result[0].text)
    pub = data.get("publication", {})
    dances = data.get("dances", [])
    print(f"\nPublication: {pub.get('name')}")
    print(f"Dances: {len(dances)} found")
    for d in dances[:5]:
        print(f"  #{d.get('position_in_book')}: {d.get('dance_name')} ({d.get('kind')} {d.get('bars')} bars)")

async def test_search_dance_lists():
    """Test search_dance_lists tool (live API)."""
    print("\n" + "="*60)
    print("Testing search_dance_lists (LIVE API)")
    print("="*60)
    
    # Search for recent class lists
    result = await call_tool("search_dance_lists", {
        "list_type": "class",
        "order_by": "-date",
        "limit": 5
    })
    data = json.loads(result[0].text)
    
    if isinstance(data, dict) and "error" in data:
        print(f"\nAPI Error: {data.get('error')}")
    else:
        print(f"\nRecent class lists: {len(data)} found")
        for lst in data[:5]:
            print(f"  - {lst.get('name')} by {lst.get('owner')} ({lst.get('date')}): {lst.get('item_count')} items")

async def test_get_dance_list_detail():
    """Test get_dance_list_detail tool (live API)."""
    print("\n" + "="*60)
    print("Testing get_dance_list_detail (LIVE API)")
    print("="*60)
    
    # First get a list ID
    result = await call_tool("search_dance_lists", {"limit": 1})
    lists = json.loads(result[0].text)
    
    if isinstance(lists, dict) and "error" in lists:
        print(f"\nAPI Error: {lists.get('error')}")
        return
    
    if not lists:
        print("\nNo lists found to test")
        return
    
    list_id = lists[0].get("id")
    print(f"\nFetching details for list ID {list_id}...")
    
    result = await call_tool("get_dance_list_detail", {"list_id": list_id})
    data = json.loads(result[0].text)
    
    if isinstance(data, dict) and "error" in data:
        print(f"API Error: {data.get('error')}")
    else:
        print(f"List: {data.get('name')} ({data.get('type')})")
        print(f"Owner: {data.get('owner')}")
        print(f"Date: {data.get('date')}")
        items = data.get("items", [])
        print(f"Items: {len(items)}")
        for item in items[:5]:
            dance = item.get("dance", {})
            if dance:
                print(f"  - {dance.get('displayname')} ({dance.get('type')})")
            else:
                print(f"  - {item.get('description')} ({item.get('type')})")

async def main():
    print("="*60)
    print("Testing New MCP SCDDB Tools")
    print("="*60)
    
    # Local database tools
    await test_find_videos()
    await test_find_recordings()
    await test_find_devisors()
    await test_find_publications()
    await test_get_publication_dances()
    
    # Live API tools
    await test_search_dance_lists()
    await test_get_dance_list_detail()
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
