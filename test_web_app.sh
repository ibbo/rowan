#!/bin/bash
# Quick test script for the web app

echo "🧪 Testing ChatSCD Web App"
echo "=========================="
echo ""

# Check if server is running
echo "1. Checking if server is accessible..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✅ Server is running"
    
    # Get health status
    HEALTH=$(curl -s http://localhost:8000/health)
    echo "   Health: $HEALTH"
else
    echo "   ❌ Server not running"
    echo "   Start with: uv run python web_app.py"
    exit 1
fi

echo ""
echo "2. Testing SSE streaming..."
echo "   Sending query: 'Find me some 32-bar reels'"
echo ""

# Test streaming (show first 10 events)
curl -N -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"message": "Find me some 32-bar reels"}' \
  2>/dev/null | head -n 20

echo ""
echo ""
echo "✅ Test complete!"
echo ""
echo "📍 Open browser to: http://localhost:8000"
echo ""
