# List Formations Feature

## Overview

Added a new `list_formations` tool to the Scottish Country Dance MCP server to help LLMs discover and search for dance formations more effectively.

## Problem Solved

Previously, LLMs had to guess formation names or tokens when searching for dances with specific formations. This often led to:
- Incorrect formation token guesses
- Missing dances due to wrong search terms
- Inability to discover what formations exist in the database
- Poor user experience when asking about specific moves

## Solution

The `list_formations` tool provides:
1. **Discovery**: List all 354 formations in the database
2. **Search**: Filter formations by name substring
3. **Statistics**: Show usage counts (how many dances use each formation)
4. **Sorting**: Sort by popularity or alphabetically
5. **Tokens**: Get exact formation tokens for use with `find_dances`

## Implementation Details

### MCP Server Changes (`mcp_scddb_server.py`)

Added new tool with the following parameters:
- `name_contains` (optional): Filter formations by name substring (case-insensitive)
- `sort_by` (optional): Sort by "popularity" (default) or "alphabetical"
- `limit` (optional): Maximum results to return (default: 50, max: 500)

Returns JSON array with:
```json
[
  {
    "id": 1,
    "name": "Reel of three - on side",
    "formation_token": "REEL;R3;SIDES;",
    "napiername": "R3S",
    "usage_count": 2166
  },
  ...
]
```

### Database Query

The tool queries the `formation` table joined with `dancesformationsmap` to calculate usage statistics:

```sql
SELECT 
    f.id,
    f.name,
    f.searchid as formation_token,
    f.napiername,
    COUNT(dfm.dance_id) as usage_count
FROM formation f
LEFT JOIN dancesformationsmap dfm ON f.id = dfm.formation_id
GROUP BY f.id, f.name, f.searchid, f.napiername
ORDER BY usage_count DESC, f.name
```

### Agent Integration (`dance_agent.py`)

Updated the system prompt to inform the LLM about the new tool:
- Added `list_formations` as the first tool in the workflow
- Explained when to use it (discovering formations, exploring moves)
- Showed how to use formation tokens with `find_dances`

## Usage Examples

### Example 1: Discover Popular Formations
```python
# List top 10 most popular formations
result = await session.call_tool(
    "list_formations",
    arguments={
        "sort_by": "popularity",
        "limit": 10
    }
)
```

Results:
1. Reel of three - on side (2166 dances)
2. Chase (2135 dances)
3. Figure of Eight - half (2035 dances)
4. Hands across - 4 (1949 dances)
5. Hands round - 6 - and back (1704 dances)
...

### Example 2: Search for Specific Formations
```python
# Find all allemande variations
result = await session.call_tool(
    "list_formations",
    arguments={
        "name_contains": "allemande",
        "sort_by": "popularity",
        "limit": 10
    }
)
```

Results:
- Allemande for 2 couples (510 dances) - token: `ALLMND;2C;`
- Allemande for 3 couples (457 dances) - token: `ALLMND;3C;`
- Allemande Turn (47 dances) - token: `ALL_RL`
...

### Example 3: Workflow - Find Dances with Specific Formation
```python
# Step 1: Find the formation token
formations = await session.call_tool(
    "list_formations",
    arguments={"name_contains": "poussette"}
)
# Get token: "POUSS;PV;" for "Poussette - standard"

# Step 2: Use token to find dances
dances = await session.call_tool(
    "find_dances",
    arguments={
        "formation_token": "POUSS;PV;",
        "limit": 10
    }
)
```

## Database Statistics

- **Total formations**: 354
- **Most popular formation**: Reel of three - on side (2166 dances)
- **Formation categories**: Reels, Allemandes, Poussettes, Hands Across, Rights and Lefts, Figure of Eight, etc.

## Benefits for LLMs

1. **No More Guessing**: LLMs can discover exact formation names and tokens
2. **Better Recommendations**: Sort by popularity to suggest common formations
3. **Exploration**: Users can ask "what formations exist?" and get real answers
4. **Precise Searches**: Use exact tokens for accurate dance searches
5. **Educational**: Show users what moves are most common in SCD

## Testing

Created comprehensive test scripts:
- `test_list_formations.py`: Direct MCP tool testing
- `test_formations_integration.py`: Workflow demonstrations
- `test_formations_agent.py`: Full agent integration tests

All tests pass successfully with performance metrics:
- Typical query time: 10-30ms
- Large queries (50+ results): 100-150ms
- Filtered searches: 5-20ms

## Performance

The tool uses efficient SQL with:
- Indexed joins on `dancesformationsmap`
- GROUP BY for aggregation
- LIMIT for result pagination
- Case-insensitive LIKE with COLLATE NOCASE

Performance is excellent even for large result sets.

## Files Modified

1. `/mcp_scddb_server.py`: Added `list_formations` tool definition and implementation
2. `/dance_agent.py`: Updated system prompt and docstring
3. `/test_list_formations.py`: Direct tool testing
4. `/test_formations_integration.py`: Workflow demonstrations
5. `/test_formations_agent.py`: Agent integration tests
6. `/LIST_FORMATIONS_FEATURE.md`: This documentation

## Future Enhancements

Potential improvements:
- Add formation categories/tags (e.g., "beginner", "advanced")
- Include formation descriptions/instructions
- Add related formations suggestions
- Support for formation difficulty ratings
- Filter by formation type (traveling, setting, etc.)
