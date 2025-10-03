#!/bin/bash
# Test intensity filtering via curl

echo "Testing: Find easy reels"
curl -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Find easy reels for beginners",
    "session_id": "test_intensity_'$(date +%s)'"
  }' \
  2>&1 | jq -r '.response' | head -50

echo ""
echo "Check the server logs for MCP tool calls and recursion patterns"
