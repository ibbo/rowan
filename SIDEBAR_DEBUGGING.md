# Sidebar Debugging Guide

## Issue: Sidebar Disappearing

If the sidebar disappears after sending messages, here are the fixes and debugging steps:

## Fixes Applied

### 1. **CSS Improvements**
- Added `min-width: 280px` to prevent sidebar from shrinking
- Added `flex-shrink: 0` to prevent flex layout from collapsing sidebar
- Added `min-height: 0` to sessions-list for proper scrolling
- Added `overflow-x: hidden` to prevent horizontal scroll issues

### 2. **JavaScript Error Handling**
- Fixed `event.currentTarget` bug in `switchToSession()` function
- Added proper error handling in `loadSessions()` to prevent clearing on failure
- Added HTML escaping to prevent XSS and rendering issues
- Added debouncing with `setTimeout()` to prevent race conditions

### 3. **Visibility Monitoring**
- Added `ensureSidebarVisible()` function that runs every 5 seconds
- Automatically detects if sidebar is hidden or removed
- Forces visibility if sidebar gets hidden
- Reloads page if sidebar is completely removed from DOM

## Debugging Steps

### Step 1: Check Browser Console
Open Developer Tools (F12) and check for JavaScript errors:

```javascript
// Common errors to look for:
- "event is not defined" (FIXED)
- "Cannot read property 'innerHTML' of null" (FIXED)
- "Failed to fetch" (API error)
```

### Step 2: Check Sidebar Element
In the console, run:

```javascript
// Check if sidebar exists
document.querySelector('.sidebar')

// Check if it's visible
window.getComputedStyle(document.querySelector('.sidebar')).display

// Check if sessions list exists
document.getElementById('sessions-list')

// Check sessions list content
document.getElementById('sessions-list').innerHTML
```

### Step 3: Check API Responses
In Network tab, check `/api/sessions` response:

```json
// Should return:
{
  "sessions": [
    {
      "session_id": "...",
      "title": "...",
      "preview": "...",
      "last_active": "...",
      "message_count": 3
    }
  ]
}

// If error:
{
  "error": "..."
}
```

### Step 4: Check CSS
In Elements tab, inspect `.sidebar` element:

```css
/* Should have these styles: */
.sidebar {
    width: 280px;
    min-width: 280px;
    flex-shrink: 0;
    display: flex;
    /* NOT display: none */
}
```

### Step 5: Force Reload Sessions
In console, manually trigger:

```javascript
loadSessions()
```

## Common Issues & Solutions

### Issue 1: Sidebar Shrinks to Zero Width
**Cause**: Flex layout collapsing sidebar when content is too wide

**Solution**: 
- Added `min-width: 280px`
- Added `flex-shrink: 0`

### Issue 2: Sessions List Empty
**Cause**: API error or race condition clearing the list

**Solution**:
- Improved error handling in `loadSessions()`
- Don't clear list if API fails
- Added validation before clearing

### Issue 3: "event is not defined" Error
**Cause**: Using `event.currentTarget` without event parameter

**Solution**:
- Changed `switchToSession()` to find active item by session ID
- Removed dependency on event object

### Issue 4: Sidebar Hidden by CSS
**Cause**: Unknown CSS override or JavaScript manipulation

**Solution**:
- Added `ensureSidebarVisible()` monitoring function
- Runs every 5 seconds to check visibility
- Forces display if hidden

### Issue 5: Race Condition on Message Send
**Cause**: `loadSessions()` called immediately after message, before DB update

**Solution**:
- Changed to `setTimeout(() => loadSessions(), 100)`
- Gives DB time to update before reloading

## Manual Recovery

If sidebar disappears, try these in console:

### Option 1: Force Visibility
```javascript
const sidebar = document.querySelector('.sidebar');
sidebar.style.display = 'flex';
sidebar.style.visibility = 'visible';
sidebar.style.minWidth = '280px';
```

### Option 2: Reload Sessions
```javascript
loadSessions();
```

### Option 3: Reload Page
```javascript
location.reload();
```

## Monitoring

The app now includes automatic monitoring:

```javascript
// Runs every 5 seconds
setInterval(ensureSidebarVisible, 5000);
```

This will:
1. Check if sidebar exists in DOM
2. Check if sidebar is visible
3. Force visibility if hidden
4. Reload page if completely missing

## Testing

To test the fixes:

1. **Start the app**:
   ```bash
   uv run python web_app.py
   ```

2. **Open browser** to http://localhost:8000

3. **Open Developer Tools** (F12)

4. **Send several messages** in a row

5. **Check console** for any errors

6. **Verify sidebar** remains visible

7. **Switch sessions** and verify it works

8. **Create new chat** and verify sidebar updates

## Prevention

The fixes prevent sidebar disappearing by:

1. ✅ **Robust CSS**: Sidebar can't shrink or collapse
2. ✅ **Error Handling**: API failures don't clear the list
3. ✅ **No Event Dependency**: Session switching doesn't rely on event object
4. ✅ **Debouncing**: Prevents race conditions
5. ✅ **Active Monitoring**: Detects and fixes visibility issues
6. ✅ **HTML Escaping**: Prevents rendering issues from special characters

## If Issue Persists

If sidebar still disappears after these fixes:

1. **Check browser compatibility**:
   - Ensure browser supports flexbox
   - Ensure browser supports localStorage
   - Try different browser

2. **Check for browser extensions**:
   - Ad blockers might interfere
   - Privacy extensions might block localStorage
   - Try incognito mode

3. **Check server logs**:
   ```bash
   # Look for API errors
   tail -f logs/web_app.log
   ```

4. **Clear browser data**:
   - Clear localStorage
   - Clear cookies
   - Hard refresh (Ctrl+Shift+R)

5. **Report the issue**:
   - Browser version
   - Console errors
   - Network tab errors
   - Steps to reproduce

## Summary

The sidebar disappearing issue has been fixed with:
- Improved CSS to prevent collapse
- Better error handling
- Fixed JavaScript bugs
- Active visibility monitoring
- Debounced session reloading

The sidebar should now remain visible and functional at all times!
