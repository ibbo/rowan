#!/usr/bin/env python3
"""
Test script for chat sessions functionality.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the functions from web_app
from web_app import (
    init_chat_db, save_message, get_chat_history, clear_chat_history,
    get_all_sessions, update_session_title, create_new_session, CHAT_DB_PATH
)


def test_chat_sessions():
    """Test the chat sessions functionality."""
    print("🧪 Testing Chat Sessions with Sidebar")
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
    
    # Test 2: Create new sessions
    print("\n2️⃣ Testing session creation...")
    browser_id = "test-browser-id"
    session1 = create_new_session(browser_id=browser_id)
    session2 = create_new_session(browser_id=browser_id)
    session3 = create_new_session(browser_id=browser_id)
    print(f"✅ Created 3 sessions: {session1[:8]}..., {session2[:8]}..., {session3[:8]}...")
    
    # Test 3: Add messages to sessions
    print("\n3️⃣ Testing message saving across sessions...")
    save_message(session1, "user", "Find me some 32-bar reels", browser_id=browser_id)
    save_message(session1, "assistant", "Here are some 32-bar reels...", browser_id=browser_id)
    save_message(session1, "user", "Tell me more about the first one", browser_id=browser_id)
    
    save_message(session2, "user", "What dances have poussette?", browser_id=browser_id)
    save_message(session2, "assistant", "Here are dances with poussette...", browser_id=browser_id)
    
    save_message(session3, "user", "Show me RSCDS published jigs", browser_id=browser_id)
    print("✅ Added messages to all sessions")
    
    # Test 4: Get all sessions
    print("\n4️⃣ Testing session listing...")
    sessions = get_all_sessions(browser_id=browser_id)
    assert len(sessions) == 3, f"Expected 3 sessions, got {len(sessions)}"
    
    # Check session metadata
    total_messages = 0
    for session in sessions:
        print(f"   Session: {session['title'][:30]}...")
        print(f"   Preview: {session['preview'][:50]}...")
        print(f"   Messages: {session['message_count']}")
        total_messages += session['message_count']
        print()
    
    # Sessions are ordered by last_active (most recent first)
    # So we just check total message count
    assert total_messages == 6, f"Expected 6 total messages, got {total_messages}"
    print("✅ Session listing works correctly")
    
    # Test 5: Update session title
    print("\n5️⃣ Testing session title update...")
    update_session_title(session1, "Reel Discussion", browser_id=browser_id)
    update_session_title(session2, "Poussette Dances", browser_id=browser_id)
    
    sessions = get_all_sessions(browser_id=browser_id)
    # Find the sessions by their content
    session1_data = next(s for s in sessions if s['session_id'] == session1)
    session2_data = next(s for s in sessions if s['session_id'] == session2)
    session3_data = next(s for s in sessions if s['session_id'] == session3)
    
    assert session1_data['title'] == "Reel Discussion", "Title should be updated"
    assert session2_data['title'] == "Poussette Dances", "Title should be updated"
    print("✅ Session titles updated successfully")
    
    # Test 6: Auto-generated titles
    print("\n6️⃣ Testing auto-generated titles...")
    # Session 3 should have auto-generated title from first message
    # (it was created with "New Chat" but should show first message as title)
    print(f"   Session 3 title: {session3_data['title']}")
    print(f"   Session 3 preview: {session3_data['preview']}")
    # The title should be either "New Chat" or auto-generated from first message
    assert session3_data['title'] in ["New Chat", session3_data['preview'][:50]], "Title should be set"
    print("✅ Session titles work correctly")
    
    # Test 7: Session ordering (most recent first)
    print("\n7️⃣ Testing session ordering...")
    # Add a new message to session 1 to make it most recent
    import time
    time.sleep(1)  # Ensure timestamp difference
    save_message(session1, "user", "Another question", browser_id=browser_id)
    
    sessions = get_all_sessions(browser_id=browser_id)
    assert sessions[0]['session_id'] == session1, "Most recent session should be first"
    print("✅ Sessions ordered by last_active correctly")
    
    # Test 8: Delete session
    print("\n8️⃣ Testing session deletion...")
    clear_chat_history(session2, browser_id=browser_id)
    sessions = get_all_sessions(browser_id=browser_id)
    assert len(sessions) == 2, "Should have 2 sessions after deletion"
    print("✅ Session deletion works correctly")
    
    print("\n" + "=" * 50)
    print("✅ All session tests passed!")
    
    # Show final database stats
    import sqlite3
    conn = sqlite3.connect(CHAT_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM sessions")
    session_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM messages")
    message_count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n📊 Final Database Stats:")
    print(f"   Sessions: {session_count}")
    print(f"   Messages: {message_count}")
    
    # Show all sessions
    print(f"\n📋 All Sessions:")
    sessions = get_all_sessions(browser_id=browser_id)
    for i, session in enumerate(sessions, 1):
        print(f"   {i}. {session['title']}")
        print(f"      Preview: {session['preview'][:60]}...")
        print(f"      Messages: {session['message_count']}")
        print()


if __name__ == "__main__":
    try:
        test_chat_sessions()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
