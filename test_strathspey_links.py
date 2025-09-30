#!/usr/bin/env python3
"""
Test script to verify that the agent includes Strathspey Server links in responses.
"""

import asyncio
import re
from dotenv import load_dotenv
from scd_agent import SCDAgent
from dance_tools import mcp_client

async def test_strathspey_links():
    """Test that the agent includes Strathspey Server links."""
    load_dotenv()
    
    print("🧪 Testing Strathspey Server Links")
    print("=" * 60)
    
    # Initialize agent
    agent = SCDAgent()
    await mcp_client.setup()
    
    # Test query
    test_query = "Find me 3 jigs"
    
    print(f"\n📝 Test Query: '{test_query}'")
    print("\n🔄 Running query...\n")
    
    config = {"configurable": {"thread_id": "test_strathspey_links"}}
    response = await agent.graph.ainvoke(
        {"messages": [{"role": "user", "content": test_query}]},
        config
    )
    
    # Extract final response
    final_msg = response["messages"][-1].content
    print("Response:")
    print("-" * 60)
    print(final_msg)
    print("-" * 60)
    
    # Check for Strathspey links
    strathspey_pattern = r'https://my\.strathspey\.org/dd/dance/\d+/'
    markdown_link_pattern = r'\[.+?\]\(https://my\.strathspey\.org/dd/dance/\d+/\)'
    
    strathspey_links = re.findall(strathspey_pattern, final_msg)
    markdown_links = re.findall(markdown_link_pattern, final_msg)
    
    print("\n\n" + "=" * 60)
    print("✅ Test Results:")
    print(f"   Found {len(strathspey_links)} Strathspey Server links")
    print(f"   Found {len(markdown_links)} Markdown-formatted links")
    
    if strathspey_links:
        print("\n   Example links found:")
        for link in strathspey_links[:3]:
            print(f"   - {link}")
    
    if len(strathspey_links) >= 3:
        print("\n✅ SUCCESS: Agent is including Strathspey Server links!")
    else:
        print("\n⚠️  WARNING: Expected at least 3 links, but found fewer.")
        print("   The LLM may need a few queries to learn the pattern.")
    
    # Cleanup
    await mcp_client.close()

if __name__ == "__main__":
    asyncio.run(test_strathspey_links())
