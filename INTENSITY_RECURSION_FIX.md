# Intensity Filter Recursion Issue - Fix Documentation

## Problem
When adding intensity/difficulty filtering to the `find_dances` tool, the LLM agent hit recursion limits when queries like "Find easy reels for beginners" were made.

## Root Causes Identified

### 1. Invalid JSON Schema - `null` in enum
**Issue:** Line 103 had `"enum":["asc","desc",null]` which is invalid JSON schema syntax.
```json
"sort_by_intensity":{"type":["string","null"], "enum":["asc","desc",null], ...}
```

**Impact:** This could cause the MCP client/agent to fail parsing the tool schema or behave unexpectedly.

**Fix:** Removed `null` from enum, made it optional by omission:
```json
"sort_by_intensity":{"type":["string","null"], "enum":["asc","desc"], ...}
```

### 2. Unrated Dances with intensity=-1
**Issue:** Database uses `-1` to indicate unrated dances (not NULL). When filtering by `max_intensity=40`, queries matched 12,774 unrated dances.

**Impact:** 
- Massive result sets (13,123 dances instead of ~342)
- LLM might see `-1` values and get confused
- Potential performance issues

**Fix:** Added `AND d.intensity > 0` to both min/max intensity filters:
```python
if min_intensity is not None:
    sql += " AND d.intensity >= ? AND d.intensity > 0"
if max_intensity is not None:
    sql += " AND d.intensity <= ? AND d.intensity > 0"
```

### 3. Always Including Intensity Field
**Issue:** The `intensity` field was always included in SELECT, even when not filtering by it. This meant all queries returned `-1` for unrated dances.

**Impact:**
- Added noise to results
- LLM might try to interpret/filter `-1` values
- Potential confusion in agent reasoning

**Fix:** Only include intensity field when actually needed:
```python
include_intensity = (min_intensity is not None or max_intensity is not None or sort_by_intensity is not None)

if include_intensity:
    sql = "SELECT ... d.intensity FROM ... INNER JOIN dance d ..."
else:
    sql = "SELECT ... FROM ... (no dance join)"
```

## Testing

### Before Fix
```bash
# Query: "Find easy reels"
# Result: 13,123 matches (including 12,774 unrated)
# Agent: Recursion limit error
```

### After Fix
```bash
# Query: "Find easy reels" (max_intensity=40)
# Result: 153 matches (only rated dances)
# Agent: Should complete successfully
```

### SQL Test
```sql
-- Easy reels (intensity <= 40, excluding unrated)
SELECT COUNT(DISTINCT m.id) 
FROM v_metaform m 
INNER JOIN dance d ON m.id = d.id 
WHERE m.kind = 'Reel' 
  AND d.intensity <= 40 
  AND d.intensity > 0;
-- Result: 153 dances
```

## Files Modified
- `/home/ubuntu/dance-teacher-dev/mcp_scddb_server.py`
  - Fixed JSON schema enum (line 103)
  - Added conditional intensity field inclusion (lines 174-189)
  - Added `d.intensity > 0` filters (lines 225, 227)
  - Added debug logging (lines 251-253)

## Verification Steps

1. **Test the MCP tool directly:**
   ```bash
   uv run python test_mcp_intensity.py
   ```

2. **Test via web interface:**
   - Start dev server: `uv run uvicorn web_app:app --host 127.0.0.1 --port 8000 --reload`
   - Query: "Find easy reels for beginners"
   - Expected: Returns ~10-25 easy reels, no recursion error

3. **Check logs:**
   - Look for `find_dances called with:` entries
   - Verify `min_intensity` and `max_intensity` parameters are passed
   - Check `Sample results:` shows only positive intensity values

## Statistics
- **Total dances:** 22,633
- **Rated dances:** 9,852 (43.5%)
- **Unrated dances:** 12,774 (56.5%, intensity=-1)
- **Easy (1-40):** 342 dances
- **Medium (41-69):** 6,407 dances
- **Hard (70+):** 3,103 dances

## Next Steps
- Monitor for any remaining recursion issues
- Consider adding explicit recursion limit to agent configuration
- Add user-facing documentation about intensity scale
- Consider UI hints for "easy" (≤40), "medium" (41-69), "hard" (≥70)
