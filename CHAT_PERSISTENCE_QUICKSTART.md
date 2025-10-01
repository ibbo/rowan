# Chat Persistence Quick Start Guide

## What Was Added

Your ChatSCD web app now has **full chat persistence** without requiring user login!

## Key Features

✅ **Automatic Session Management**: Each user gets a unique session ID stored in their browser  
✅ **Persistent Chat History**: Conversations survive page refreshes and browser restarts  
✅ **SQLite Storage**: All chats saved to `data/chat_history.db`  
✅ **Clear Chat Button**: Users can start fresh anytime  
✅ **Privacy-Focused**: No login required, sessions identified by random UUID only  

## How It Works

### For Users

1. **First Visit**: 
   - Open the web app → automatically assigned a session ID
   - Start chatting immediately

2. **Return Visits**:
   - Open the web app → previous conversations automatically loaded
   - Continue where you left off

3. **Clear Chat**:
   - Click "🗑️ Clear Chat" button
   - Confirm → history cleared, new session started

### Technical Flow

```
User Opens Page
    ↓
Check localStorage for session_id
    ↓
If exists → Load chat history from database
If not → Generate new UUID, show welcome
    ↓
User sends message
    ↓
Save to database (session_id, role, content)
    ↓
Agent responds
    ↓
Save response to database
```

## Files Modified

### Backend: `web_app.py`
- Added SQLite database initialization
- Added `save_message()`, `get_chat_history()`, `clear_chat_history()` functions
- Added API endpoints: `GET /api/history/{session_id}` and `DELETE /api/history/{session_id}`
- Messages automatically saved during query processing

### Frontend: `templates/index.html`
- Session ID stored in `localStorage` (key: `chatSCD_sessionId`)
- Chat history loaded on page load via `loadChatHistory()`
- Clear chat button added with confirmation dialog
- Welcome message shown only for new sessions

## Testing

Run the test suite:
```bash
uv run python test_chat_persistence.py
```

Or test manually:
```bash
# Start the web app
uv run python web_app.py

# Open http://localhost:8000
# Send some messages
# Refresh page → messages persist
# Close browser, reopen → messages still there
# Click "Clear Chat" → new session started
```

## Database Schema

**Location**: `data/chat_history.db`

**Tables**:
```sql
sessions (
    session_id TEXT PRIMARY KEY,
    created_at TIMESTAMP,
    last_active TIMESTAMP
)

messages (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    role TEXT,  -- 'user' or 'assistant'
    content TEXT,
    timestamp TIMESTAMP
)
```

## API Endpoints

### Get Chat History
```http
GET /api/history/{session_id}
```
Returns:
```json
{
  "history": [
    {
      "role": "user",
      "content": "Find me some 32-bar reels",
      "timestamp": "2025-09-30 21:15:00"
    },
    {
      "role": "assistant",
      "content": "Here are some 32-bar reels...",
      "timestamp": "2025-09-30 21:15:05"
    }
  ]
}
```

### Clear Chat History
```http
DELETE /api/history/{session_id}
```
Returns:
```json
{
  "success": true
}
```

## Browser Storage

Session ID stored in localStorage:
```javascript
localStorage.getItem('chatSCD_sessionId')
// Returns: "550e8400-e29b-41d4-a716-446655440000"
```

## Privacy & Security

- ✅ No user accounts or personal information required
- ✅ Sessions identified by random UUID only
- ✅ Each user can only access their own history
- ✅ Users can clear their history anytime
- ✅ Data stored locally on your server

## Maintenance

### View Database
```bash
sqlite3 data/chat_history.db
SELECT COUNT(*) FROM sessions;
SELECT COUNT(*) FROM messages;
```

### Backup Database
```bash
cp data/chat_history.db data/chat_history.db.backup
```

### Clear All Data
```bash
rm data/chat_history.db
# Will be recreated on next startup
```

## Future Enhancements

Consider adding:
- User accounts (optional login)
- Multiple chat sessions per user
- Export chat history
- Search within history
- Auto-cleanup of old sessions
- Analytics dashboard

## Integration with LangGraph

The session ID is passed to LangGraph's checkpointer:
```python
config = {"configurable": {"thread_id": session_id}}
```

This means:
- LangGraph maintains conversation context per session
- Agent can reference previous messages in the conversation
- Each browser session has isolated conversation memory

## Summary

Your web app now provides a seamless chat experience with full persistence, no login required. Users can return anytime and pick up where they left off, with the option to start fresh whenever they want.
