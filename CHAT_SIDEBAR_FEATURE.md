# Chat Sidebar Feature

## Overview

The ChatSCD web app now includes a **sidebar with chat session management**, allowing users to:
- View all their previous chat sessions
- Create new chats while keeping old ones
- Switch between different conversations
- See chat previews and timestamps

## Features

### 🗂️ Session List Sidebar
- **Left-hand sidebar** displaying all chat sessions
- Sessions ordered by most recent activity
- Each session shows:
  - Title (auto-generated from first message or custom)
  - Preview of first message
  - Time since last activity (e.g., "5m ago", "2h ago", "3d ago")
  - Message count

### ➕ New Chat Button
- Create new chat sessions with one click
- Old chats remain accessible in the sidebar
- Each session maintains its own conversation history

### 🔄 Session Switching
- Click any session in the sidebar to switch to it
- Active session highlighted with purple border
- Chat history loads instantly when switching
- LangGraph conversation context maintained per session

### 🗑️ Delete Chat
- "Clear Chat" button now deletes the current session
- Automatically creates a new session after deletion
- Sidebar updates to reflect changes

## User Interface

### Layout
```
┌─────────────────────────────────────────────────────────┐
│  💬 Chat History    │    🏴󠁧󠁢󠁳󠁣󠁴󠁿 ChatSCD                    │
│  [+ New Chat]       │    Your Scottish Country Dance    │
│                     │    Planning Partner               │
│  ┌───────────────┐  │                                   │
│  │ Reel Disc...  │  │  ┌─────────────────────────────┐ │
│  │ Find me some  │  │  │                             │ │
│  │ 32-bar reels  │  │  │   Chat Messages Here        │ │
│  │ 5m ago        │  │  │                             │ │
│  └───────────────┘  │  └─────────────────────────────┘ │
│                     │                                   │
│  ┌───────────────┐  │  [Example Buttons]               │
│  │ Poussette...  │  │  [Input Field]        [Send]     │
│  │ What dances   │  │                                   │
│  │ have pouss... │  │                                   │
│  │ 2h ago        │  │                                   │
│  └───────────────┘  │                                   │
└─────────────────────────────────────────────────────────┘
```

### Responsive Design
- **Desktop**: Sidebar on left, chat on right
- **Mobile**: Sidebar collapses to top, chat below
- Smooth transitions and hover effects

## Technical Implementation

### Backend Changes (`web_app.py`)

**Database Schema Updates**:
```sql
-- Added title column to sessions table
ALTER TABLE sessions ADD COLUMN title TEXT;
```

**New Functions**:
- `get_all_sessions()`: Returns all sessions with metadata
- `create_new_session()`: Creates a new session with UUID
- `update_session_title(session_id, title)`: Updates session title

**New API Endpoints**:
- `GET /api/sessions`: List all chat sessions
- `POST /api/sessions/new`: Create a new session
- `PUT /api/sessions/{session_id}/title`: Update session title

### Frontend Changes (`templates/index.html`)

**New UI Components**:
- `.sidebar`: Left sidebar container
- `.sidebar-header`: Header with "New Chat" button
- `.sessions-list`: Scrollable list of sessions
- `.session-item`: Individual session card
- `.main-content`: Wrapper for chat area

**New JavaScript Functions**:
- `loadSessions()`: Fetches and displays all sessions
- `switchToSession(sessionId)`: Switches to a different chat
- `createNewChat()`: Creates and switches to new session
- `formatTimeAgo(timestamp)`: Formats relative time display

**Session Management**:
```javascript
// Load sessions on page load
await loadSessions();

// Create new chat
const response = await fetch('/api/sessions/new', {method: 'POST'});
const {session_id} = await response.json();

// Switch to existing session
sessionId = newSessionId;
localStorage.setItem('chatSCD_sessionId', sessionId);
await loadChatHistory();
```

## Database Schema

### Sessions Table (Updated)
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    title TEXT,                    -- NEW: Session title
    created_at TIMESTAMP,
    last_active TIMESTAMP
)
```

### Session Metadata Query
```sql
SELECT 
    s.session_id,
    s.title,
    s.created_at,
    s.last_active,
    COUNT(m.id) as message_count,
    (SELECT content FROM messages 
     WHERE session_id = s.session_id AND role = 'user'
     ORDER BY timestamp ASC LIMIT 1) as first_message
FROM sessions s
LEFT JOIN messages m ON s.session_id = m.session_id
GROUP BY s.session_id
ORDER BY s.last_active DESC
```

## User Workflows

### Creating a New Chat
1. User clicks "+ New Chat" button
2. Backend creates new session with UUID
3. Frontend switches to new session
4. Empty chat with welcome message displayed
5. Sidebar updates with new session

### Switching Between Chats
1. User clicks session in sidebar
2. Session ID updated in localStorage
3. Chat history loaded for selected session
4. Active session highlighted in sidebar
5. LangGraph uses session ID as thread_id for context

### Deleting a Chat
1. User clicks "🗑️ Clear Chat"
2. Confirmation dialog appears
3. If confirmed:
   - Current session deleted from database
   - New session automatically created
   - Sidebar refreshed
   - User starts fresh

## Session Titles

### Auto-Generated Titles
- If no custom title set, uses first 50 characters of first user message
- Example: "Find me some 32-bar reels" → "Find me some 32-bar reels"
- Fallback: "New Chat" if no messages yet

### Custom Titles (Future Enhancement)
- API endpoint ready: `PUT /api/sessions/{session_id}/title`
- Can add inline editing in sidebar
- Users can rename chats for better organization

## Integration with LangGraph

Each session maintains its own conversation context:

```python
# Session ID passed as thread_id to LangGraph
config = {"configurable": {"thread_id": session_id}}
await agent.graph.astream({...}, config)
```

This ensures:
- Each chat has isolated conversation memory
- Agent can reference previous messages within the session
- No cross-contamination between different chats
- Context-aware responses based on conversation history

## Testing

Run the test suite:
```bash
uv run python test_chat_sessions.py
```

Tests cover:
- Session creation and listing
- Message saving across sessions
- Session title updates
- Auto-generated titles
- Session ordering by last_active
- Session deletion
- Message count accuracy

## Mobile Responsiveness

**Breakpoint**: 768px

**Desktop (>768px)**:
- Sidebar: 280px fixed width
- Chat: Flexible width
- Side-by-side layout

**Mobile (≤768px)**:
- Sidebar: Full width, max 200px height
- Chat: Full width, 60vh height
- Stacked layout

## Performance Considerations

- **Lazy Loading**: Sessions loaded once on page load
- **Efficient Queries**: Indexed by session_id and timestamp
- **Minimal Reloads**: Sidebar only refreshes after new messages
- **Local Storage**: Session ID cached in browser

## Future Enhancements

### Potential Features
1. **Inline Title Editing**: Click to rename sessions
2. **Search Sessions**: Filter by title or content
3. **Archive/Pin**: Mark important chats
4. **Export Chat**: Download conversation history
5. **Session Folders**: Organize chats by topic
6. **Bulk Delete**: Clear multiple old sessions
7. **Session Sharing**: Share chat via link (with permissions)
8. **Auto-Cleanup**: Delete sessions older than X days

### UI Improvements
1. **Drag to Reorder**: Manual session ordering
2. **Collapse Sidebar**: Toggle button for more chat space
3. **Session Icons**: Visual indicators for chat type
4. **Unread Indicators**: Show which chats have updates
5. **Session Stats**: Total messages, tokens used, etc.

## Styling

**Color Scheme**:
- Primary: Purple gradient (#667eea → #764ba2)
- Active session: Light purple (#ede9fe)
- Hover: Light gray (#f3f4f6)
- Text: Dark gray (#1f2937)

**Typography**:
- Session title: 0.9rem, bold
- Preview: 0.8rem, gray
- Time: 0.75rem, light gray

**Animations**:
- Smooth hover transitions (0.2s)
- Slide-in for new sessions
- Fade for deleted sessions

## Browser Compatibility

- ✅ Chrome/Edge (90+)
- ✅ Firefox (88+)
- ✅ Safari (14+)
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)

Requires:
- `localStorage` support
- `crypto.randomUUID()` support
- Flexbox layout support
- CSS Grid support

## Summary

The sidebar feature transforms ChatSCD from a single-conversation app into a **multi-session chat manager**, allowing users to:
- Maintain multiple ongoing conversations
- Easily switch between different topics
- Keep organized chat history
- Never lose context when exploring different dance queries

All while maintaining the same beautiful UI and seamless user experience! 🎉
