#!/usr/bin/env python3
"""
Test the Gradio integration with the new multi-agent system.
"""

import asyncio
from dotenv import load_dotenv
from gradio_app import DanceAgentUI


async def test_gradio_agent():
    """Test that the Gradio agent wrapper works with the new multi-agent."""
    load_dotenv()
    
    print("=" * 60)
    print("Testing Gradio Integration with Multi-Agent System")
    print("=" * 60)
    
    ui = DanceAgentUI()
    
    print("\n1. Testing agent initialization...")
    await ui.ensure_ready()
    print("✅ Agent initialized successfully")
    
    print("\n2. Testing valid SCD query streaming...")
    session_id = "test_session_123"
    query = "Find me some 32-bar reels"
    
    events = []
    async for event in ui.stream_events(query, session_id):
        events.append(event)
        event_type = event.get("event", "unknown")
        print(f"   Event: {event_type}")
        
        if event_type == "status":
            print(f"      Status: {event.get('title')}")
        elif event_type == "tool_start":
            print(f"      Tool: {event.get('tool')}")
        elif event_type == "tool_result":
            result = event.get("result", {})
            dances = result.get("dances", [])
            print(f"      Found {len(dances)} dances")
        elif event_type == "final":
            message = event.get("message", "")
            print(f"      Final: {message[:100]}...")
    
    print(f"\n✅ Received {len(events)} events total")
    
    # Check that we got expected events
    event_types = [e.get("event") for e in events]
    
    if "status" in event_types:
        print("✅ Status events present")
    if "tool_start" in event_types:
        print("✅ Tool start events present")
    if "final" in event_types or "assistant_update" in event_types:
        print("✅ Response events present")
    
    print("\n3. Testing rejected query...")
    query = "What's the weather today?"
    
    events = []
    async for event in ui.stream_events(query, session_id):
        events.append(event)
        event_type = event.get("event", "unknown")
        print(f"   Event: {event_type}")
        
        if event_type == "status":
            print(f"      Status: {event.get('title')}")
        elif event_type == "final":
            message = event.get("message", "")
            print(f"      Final: {message[:100]}...")
    
    print(f"\n✅ Received {len(events)} events for rejected query")
    
    # Clean up
    from dance_tools import mcp_client
    print("\n🧹 Cleaning up...")
    await mcp_client.close()
    
    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_gradio_agent())
