#!/usr/bin/env python3
"""Test the web server to verify the skip change fix."""

import requests
import json
import time

url = "http://localhost:7860/api/query"

data = {
    "message": "How do I teach the skip change?",
    "session_id": "test_session_" + str(int(time.time()))
}

print("Sending query:", data["message"])
print("="*80)

response = requests.post(url, json=data, stream=True, timeout=60)

print("\nStreaming response:")
print("-"*80)

final_message = None

for line in response.iter_lines():
    if line:
        line_str = line.decode('utf-8')
        if line_str.startswith('data: '):
            json_str = line_str[6:]  # Remove 'data: ' prefix
            try:
                event = json.loads(json_str)
                event_type = event.get('type')
                
                if event_type == 'status':
                    print(f"📍 Status: {event.get('message')}")
                elif event_type == 'tool_start':
                    print(f"🔧 Tool: {event.get('tool')} - Args: {event.get('args')}")
                elif event_type == 'final':
                    final_message = event.get('message')
                    print(f"\n✅ Final Response:")
                    print("-"*80)
                    print(final_message)
                    print("-"*80)
                elif event_type == 'complete':
                    print("\n✅ Complete")
                elif event_type == 'error':
                    print(f"\n❌ Error: {event.get('message')}")
            except json.JSONDecodeError:
                pass

print("\n" + "="*80)
if final_message:
    # Check if it's detailed or generic
    if "Points to observe" in final_message or "points to observe" in final_message:
        print("✅ SUCCESS: Got detailed teaching points from the manual!")
    elif "hop" in final_message.lower() and "extended" in final_message.lower():
        print("✅ SUCCESS: Got specific technical details!")
    else:
        print("⚠️  WARNING: Response looks generic, might not have detailed teaching points")
        if len(final_message) < 300:
            print(f"   Response is quite short ({len(final_message)} chars)")
else:
    print("❌ FAILED: No final message received")
