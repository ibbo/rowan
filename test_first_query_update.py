#!/usr/bin/env python3
"""
Test that the first query shows updates immediately.
"""

import asyncio
from dotenv import load_dotenv
from gradio_app import ui


async def test_first_query():
    """Test that the first query yields updates immediately."""
    load_dotenv()
    
    print("=" * 60)
    print("Testing First Query Updates")
    print("=" * 60)
    
    # Simulate the Gradio flow
    from gradio_app import build_interface
    
    # Get the agent UI
    agent_ui = ui
    
    print("\n1. Ensuring agent is ready...")
    await agent_ui.ensure_ready()
    print("✅ Agent ready\n")
    
    print("2. Simulating first query with execute_agent_flow...")
    
    # Simulate the inputs
    chat_history = []
    activity_history = []
    dance_history = []
    session_info = {}
    
    query = "Find me some 32-bar reels"
    
    # Import the execute_agent_flow function
    # We'll manually create it here to test
    from gradio_app import timestamp, format_activity_timeline, render_dance_cards
    import uuid
    
    # Simulate execute_agent_flow
    if "session_id" not in session_info:
        session_info["session_id"] = f"browser_{uuid.uuid4()}"
    
    session_id = session_info["session_id"]
    
    chat_history.append({"role": "user", "content": query})
    chat_history.append({"role": "assistant", "content": "Starting the search..."})
    activity_history.append({"time": timestamp(), "text": "User request received."})
    
    yield_count = 0
    
    print(f"   Initial state prepared")
    print(f"   - Chat history: {len(chat_history)} messages")
    print(f"   - Activity history: {len(activity_history)} items")
    
    # First yield
    yield_count += 1
    print(f"\n   [Yield {yield_count}] Initial state")
    print(f"      Assistant message: '{chat_history[-1]['content']}'")
    
    await asyncio.sleep(0.05)
    
    # Second yield - initialization
    chat_history[-1]["content"] = "🔧 Initializing agent..."
    activity_history.append({"time": timestamp(), "text": "Starting agent initialization"})
    yield_count += 1
    print(f"\n   [Yield {yield_count}] Initialization")
    print(f"      Assistant message: '{chat_history[-1]['content']}'")
    
    # Now stream events
    event_count = 0
    async for event in agent_ui.stream_events(query, session_id):
        event_count += 1
        event_type = event.get("event", "unknown")
        
        if event_type == "status":
            yield_count += 1
            print(f"\n   [Yield {yield_count}] Status event")
            print(f"      Title: {event.get('title')}")
            print(f"      Body: {event.get('body')}")
        elif event_type == "tool_start":
            yield_count += 1
            print(f"\n   [Yield {yield_count}] Tool start")
            print(f"      Tool: {event.get('tool')}")
        elif event_type == "tool_result":
            yield_count += 1
            print(f"\n   [Yield {yield_count}] Tool result")
        elif event_type == "assistant_update":
            yield_count += 1
            print(f"\n   [Yield {yield_count}] Assistant update")
        elif event_type == "final":
            yield_count += 1
            print(f"\n   [Yield {yield_count}] Final response")
            break
    
    print(f"\n✅ Total yields: {yield_count}")
    print(f"   Total events: {event_count}")
    
    if yield_count < 3:
        print("\n⚠️  WARNING: Very few yields!")
        print("   First query might not show updates.")
    else:
        print("\n✅ Good yield count - first query should show updates")
    
    # Clean up
    from dance_tools import mcp_client
    print("\n🧹 Cleaning up...")
    await mcp_client.close()
    
    print("\n" + "=" * 60)
    print("First query test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_first_query())
