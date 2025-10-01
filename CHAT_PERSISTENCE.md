# Chat Persistence Implementation

## Overview

The ChatSCD web application now includes full chat persistence without requiring user login. Each user is automatically assigned a unique session ID that is stored in their browser's localStorage, allowing their chat history to persist across page refreshes and browser sessions.

## Architecture

### Backend (web_app.py)

**SQLite Database**: `data/chat_history.db`

**Tables**:
- `sessions`: Stores session metadata
  - `session_id` (TEXT, PRIMARY KEY)
  - `created_at` (TIMESTAMP)
  - `last_active` (TIMESTAMP)

- `messages`: Stores chat messages
  - `id` (INTEGER, PRIMARY KEY)
  - `session_id` (TEXT, FOREIGN KEY)
  - `role` (TEXT: 'user' or 'assistant')
  - `content` (TEXT)
  - `timestamp` (TIMESTAMP)

**Key Functions**:
- `init_chat_db()`: Initializes the database on startup
- `save_message(session_id, role, content)`: Saves a message to history
- `get_chat_history(session_id, limit=100)`: Retrieves chat history
- `clear_chat_history(session_id)`: Clears all messages for a session

**API Endpoints**:
- `GET /api/history/{session_id}`: Retrieve chat history
- `DELETE /api/history/{session_id}`: Clear chat history

### Frontend (templates/index.html)

**Session Management**:
- Session ID is generated using `crypto.randomUUID()` on first visit
- Stored in `localStorage` under key `chatSCD_sessionId`
- Persists across page refreshes and browser sessions
- Automatically loaded on page load

**Key Features**:
1. **Automatic History Loading**: On page load, fetches and displays previous conversations
2. **Persistent Sessions**: Same session ID used across visits until explicitly cleared
3. **Clear Chat Button**: Allows users to start fresh with a new session
4. **Real-time Saving**: Messages are saved to database as they're sent/received

## User Experience

### First Visit
1. User opens ChatSCD
2. New session ID generated and stored in localStorage
3. Welcome message displayed
4. User can start chatting

### Returning Visit
1. User opens ChatSCD
2. Existing session ID loaded from localStorage
3. Previous chat history fetched and displayed
4. User can continue previous conversation

### Clearing Chat
1. User clicks "🗑️ Clear Chat" button
2. Confirmation dialog appears
3. If confirmed:
   - Server-side history deleted
   - New session ID generated
   - localStorage updated
   - UI cleared and welcome message shown

## Privacy & Security

**No User Accounts**: 
- No login required
- No personal information collected
- Sessions identified only by random UUID

**Data Isolation**:
- Each session ID is unique and unguessable
- Users can only access their own chat history
- No cross-session data leakage

**Data Persistence**:
- Chat history stored locally on server
- Survives server restarts
- Can be manually cleared by user at any time

## Future Enhancements

Potential additions for the future:

1. **User Accounts** (Optional):
   - Allow users to create accounts
   - Link multiple sessions to one account
   - Access history from any device

2. **Session Management**:
   - View/manage multiple chat sessions
   - Archive old conversations
   - Export chat history

3. **Data Retention**:
   - Automatic cleanup of old sessions
   - Configurable retention policies
   - GDPR compliance features

4. **Enhanced Privacy**:
   - End-to-end encryption option
   - Self-destructing messages
   - Anonymous mode

## Technical Details

**Database Location**: `data/chat_history.db`

**Storage Format**: SQLite3 database file

**Message Limit**: 100 messages per session (configurable via `limit` parameter)

**Session ID Format**: UUID v4 (e.g., `550e8400-e29b-41d4-a716-446655440000`)

**Browser Compatibility**: Works in all modern browsers supporting localStorage and crypto.randomUUID()

## Testing

To test the persistence:

1. Start the web app:
   ```bash
   uv run python web_app.py
   ```

2. Open http://localhost:8000

3. Send some messages

4. Refresh the page - messages should persist

5. Close and reopen browser - messages should still be there

6. Click "Clear Chat" - history should be cleared and new session created

## Maintenance

**Database Backup**:
```bash
cp data/chat_history.db data/chat_history.db.backup
```

**View Database Contents**:
```bash
sqlite3 data/chat_history.db
.tables
SELECT * FROM sessions;
SELECT * FROM messages;
```

**Clear All Data**:
```bash
rm data/chat_history.db
# Database will be recreated on next startup
```
