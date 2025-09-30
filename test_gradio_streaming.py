#!/usr/bin/env python3
"""
Test Gradio streaming to verify UI updates are working.
"""

import asyncio
from dotenv import load_dotenv
from gradio_app import DanceAgentUI


async def test_streaming():
    """Test that streaming events are generated properly."""
    load_dotenv()
    
    print("=" * 60)
    print("Testing Gradio Streaming Updates")
    print("=" * 60)
    
    ui = DanceAgentUI()
    
    print("\n1. Initializing agent...")
    await ui.ensure_ready()
    print("✅ Agent ready\n")
    
    print("2. Testing streaming with a valid query...")
    print("   Query: 'Find me some 32-bar reels'\n")
    
    session_id = "test_stream_123"
    query = "Find me some 32-bar reels"
    
    event_count = 0
    last_event_time = asyncio.get_event_loop().time()
    
    async for event in ui.stream_events(query, session_id):
        current_time = asyncio.get_event_loop().time()
        time_since_last = (current_time - last_event_time) * 1000
        
        event_count += 1
        event_type = event.get("event", "unknown")
        
        print(f"   [{event_count:2d}] {event_type:20s} (+{time_since_last:6.1f}ms)", end="")
        
        if event_type == "status":
            print(f" - {event.get('title')}")
        elif event_type == "tool_start":
            tool = event.get('tool', 'unknown')
            args = event.get('args', {})
            print(f" - {tool} with {len(args)} args")
        elif event_type == "tool_result":
            result = event.get('result', {})
            dances = result.get('dances', [])
            print(f" - {len(dances)} dances")
        elif event_type == "assistant_update":
            message = event.get('message', '')
            print(f" - {len(message)} chars")
        elif event_type == "final":
            message = event.get('message', '')
            print(f" - {len(message)} chars")
        else:
            print()
        
        last_event_time = current_time
    
    print(f"\n✅ Received {event_count} events")
    print(f"   Average time between events: {(asyncio.get_event_loop().time() - last_event_time) / max(event_count, 1) * 1000:.1f}ms")
    
    # Check event distribution
    print("\n3. Event distribution:")
    print(f"   - Status events should appear first")
    print(f"   - Tool events should appear in the middle")
    print(f"   - Final event should appear last")
    print(f"   - Total events: {event_count}")
    
    if event_count < 3:
        print("\n⚠️  WARNING: Very few events received!")
        print("   This might indicate streaming issues.")
    else:
        print("\n✅ Good event count - streaming appears to be working")
    
    # Clean up
    from dance_tools import mcp_client
    print("\n🧹 Cleaning up...")
    await mcp_client.close()
    
    print("\n" + "=" * 60)
    print("Streaming test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_streaming())
