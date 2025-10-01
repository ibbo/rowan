#!/usr/bin/env python3
"""
Test script for chat persistence functionality.
"""

import os
import sys
import uuid
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the functions from web_app
from web_app import init_chat_db, save_message, get_chat_history, clear_chat_history, CHAT_DB_PATH


def test_chat_persistence():
    """Test the chat persistence functions."""
    print("🧪 Testing Chat Persistence")
    print("=" * 50)
    
    # Clean up any existing test database
    if os.path.exists(CHAT_DB_PATH):
        os.remove(CHAT_DB_PATH)
        print(f"🧹 Cleaned up existing database at {CHAT_DB_PATH}")
    
    # Test 1: Initialize database
    print("\n1️⃣ Testing database initialization...")
    init_chat_db()
    assert os.path.exists(CHAT_DB_PATH), "Database file should exist"
    print("✅ Database initialized successfully")
    
    # Test 2: Save messages
    print("\n2️⃣ Testing message saving...")
    test_session_id = str(uuid.uuid4())
    save_message(test_session_id, "user", "Find me some 32-bar reels")
    save_message(test_session_id, "assistant", "Here are some 32-bar reels: The Reel of the 51st Division...")
    save_message(test_session_id, "user", "Tell me more about the first one")
    print(f"✅ Saved 3 messages for session {test_session_id[:8]}...")
    
    # Test 3: Retrieve messages
    print("\n3️⃣ Testing message retrieval...")
    history = get_chat_history(test_session_id)
    assert len(history) == 3, f"Expected 3 messages, got {len(history)}"
    assert history[0]["role"] == "user", "First message should be from user"
    assert history[1]["role"] == "assistant", "Second message should be from assistant"
    assert "32-bar reels" in history[0]["content"], "Message content should match"
    print(f"✅ Retrieved {len(history)} messages successfully")
    
    # Test 4: Multiple sessions
    print("\n4️⃣ Testing multiple sessions...")
    session2_id = str(uuid.uuid4())
    save_message(session2_id, "user", "What dances have poussette?")
    save_message(session2_id, "assistant", "Here are dances with poussette...")
    
    history1 = get_chat_history(test_session_id)
    history2 = get_chat_history(session2_id)
    assert len(history1) == 3, "Session 1 should have 3 messages"
    assert len(history2) == 2, "Session 2 should have 2 messages"
    print("✅ Multiple sessions work correctly")
    
    # Test 5: Clear chat history
    print("\n5️⃣ Testing chat clearing...")
    clear_chat_history(test_session_id)
    history_after_clear = get_chat_history(test_session_id)
    assert len(history_after_clear) == 0, "History should be empty after clearing"
    
    # Session 2 should still have messages
    history2_after = get_chat_history(session2_id)
    assert len(history2_after) == 2, "Session 2 should still have messages"
    print("✅ Chat clearing works correctly")
    
    # Test 6: Message limit
    print("\n6️⃣ Testing message limit...")
    session3_id = str(uuid.uuid4())
    for i in range(10):
        save_message(session3_id, "user", f"Message {i}")
    
    history_limited = get_chat_history(session3_id, limit=5)
    assert len(history_limited) == 5, "Should respect limit parameter"
    print("✅ Message limit works correctly")
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    print(f"📁 Database location: {CHAT_DB_PATH}")
    
    # Show database stats
    import sqlite3
    conn = sqlite3.connect(CHAT_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM sessions")
    session_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM messages")
    message_count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n📊 Database Stats:")
    print(f"   Sessions: {session_count}")
    print(f"   Messages: {message_count}")


if __name__ == "__main__":
    try:
        test_chat_persistence()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
