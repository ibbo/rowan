# MCP Client Cleanup Fix

## Problem

When exiting the agent with "bye", "quit", or "exit", an async context manager error occurred:

```
RuntimeError: Attempted to exit cancel scope in a different task than it was entered in
```

This happened because the `atexit` handler tried to clean up async resources using `asyncio.run()`, which creates a new event loop and causes context manager issues.

## Root Cause

The original code used an `atexit` handler to clean up MCP sessions:

```python
import atexit
def cleanup_sessions():
    if mcp_client._connection_pool:
        try:
            asyncio.run(mcp_client.close())  # ❌ Creates new event loop
        except:
            pass
atexit.register(cleanup_sessions)
```

**Problem**: `asyncio.run()` creates a new event loop, but the MCP client's async context managers were entered in a different event loop/task, causing the RuntimeError.

## Solution

Remove the `atexit` handler and use explicit cleanup in the async context with a `try/finally` block:

### Changes Made

#### 1. `dance_tools.py`
- **Removed**: `atexit` handler with `asyncio.run()`
- **Added**: Comment explaining why explicit cleanup is needed

```python
# Global MCP client instance
mcp_client = MCPSCDDBClient()

# Note: Cleanup should be done explicitly in async context
# Using atexit with asyncio.run() causes context manager issues
```

#### 2. `scd_agent.py`
- **Added**: `try/finally` block in `main()` function
- **Added**: Explicit `await mcp_client.close()` in finally block

```python
try:
    while True:
        # ... main loop ...
finally:
    # Clean up MCP client connections properly
    from dance_tools import mcp_client
    print("\n🧹 Cleaning up...", file=sys.stderr)
    await mcp_client.close()
```

#### 3. `dance_agent.py`
- **Same fix**: Added `try/finally` with explicit cleanup

#### 4. `test_scd_agent.py`
- **Added**: Cleanup in test function's finally block

## Why This Works

1. **Same Event Loop**: Cleanup happens in the same async context where resources were created
2. **Proper Async Context**: Uses `await` instead of `asyncio.run()`
3. **Guaranteed Cleanup**: `finally` block ensures cleanup even on errors
4. **No Context Manager Issues**: All async context managers are entered and exited in the same task

## Testing

Test the fix:

```bash
# Should exit cleanly without errors
uv run python scd_agent.py
# Type: bye

# Expected output:
# 👋 Goodbye!
# 🧹 Cleaning up...
# DEBUG: All MCP sessions closed
```

## Best Practices

### ✅ Do This
```python
async def main():
    try:
        # ... async work ...
    finally:
        await cleanup_async_resources()

asyncio.run(main())
```

### ❌ Don't Do This
```python
import atexit

def cleanup():
    asyncio.run(cleanup_async_resources())  # Creates new event loop!

atexit.register(cleanup)
```

## Impact

- **User Experience**: Clean exit without error messages
- **Resource Management**: Proper cleanup of MCP connections
- **Code Quality**: Follows async/await best practices
- **Reliability**: No context manager errors

## Files Modified

1. `dance_tools.py` - Removed atexit handler
2. `scd_agent.py` - Added try/finally cleanup
3. `dance_agent.py` - Added try/finally cleanup
4. `test_scd_agent.py` - Added cleanup in tests

All agents now exit cleanly without async context manager errors.
