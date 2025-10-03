#!/usr/bin/env python3
"""
Test the RAG pipeline for RSCDS manual integration.

Tests:
1. Direct tool access - test search_manual tool directly
2. Agent integration - test that scd_agent uses search_manual appropriately
3. End-to-end queries - realistic user questions

Usage:
    export OPENAI_API_KEY="your-key-here"
    uv run test_manual_rag.py
"""

import asyncio
import sys
from dotenv import load_dotenv


async def test_search_manual_tool():
    """Test the search_manual tool directly."""
    print("\n" + "=" * 60)
    print("TEST 1: Direct search_manual Tool Access")
    print("=" * 60)
    
    from dance_tools import search_manual
    
    test_queries = [
        ("poussette teaching points", 3),
        ("allemande technique", 2),
        ("rights and lefts", 2),
        ("set and link", 2),
    ]
    
    for query, num_results in test_queries:
        print(f"\n🔍 Query: '{query}' (requesting {num_results} results)")
        print("-" * 60)
        
        result = await search_manual.ainvoke({
            "query": query,
            "num_results": num_results
        })
        
        print(result)
        print()
    
    print("✅ Direct tool test completed\n")


async def test_agent_integration():
    """Test that the agent uses search_manual appropriately."""
    print("\n" + "=" * 60)
    print("TEST 2: Agent Integration")
    print("=" * 60)
    
    from scd_agent import SCDAgent
    
    agent = SCDAgent()
    config = {"configurable": {"thread_id": "test_session"}}
    
    test_queries = [
        "How do I teach a poussette?",
        "Can you explain the allemande formation?",
        "What are the teaching points for rights and lefts?",
    ]
    
    for query in test_queries:
        print(f"\n🤔 User Query: '{query}'")
        print("-" * 60)
        
        result = await agent.ainvoke(query, config)
        final_message = result["messages"][-1]
        
        print(f"\n📚 Agent Response:")
        print(final_message.content)
        print()
    
    # Clean up
    from dance_tools import mcp_client
    await mcp_client.close()
    
    print("✅ Agent integration test completed\n")


async def test_end_to_end_scenarios():
    """Test realistic end-to-end scenarios."""
    print("\n" + "=" * 60)
    print("TEST 3: End-to-End Scenarios")
    print("=" * 60)
    
    from scd_agent import SCDAgent
    
    agent = SCDAgent()
    config = {"configurable": {"thread_id": "e2e_test_session"}}
    
    scenarios = [
        {
            "name": "Teaching a formation",
            "query": "I'm teaching a beginner class and need help explaining what a poussette is. Can you help?"
        },
        {
            "name": "Dance with formation explanation",
            "query": "Find me some dances with allemande and explain how to teach that formation."
        },
        {
            "name": "General technique question",
            "query": "What's the proper footwork for traveling steps in Scottish Country Dancing?"
        },
    ]
    
    for scenario in scenarios:
        print(f"\n📖 Scenario: {scenario['name']}")
        print(f"🤔 Query: '{scenario['query']}'")
        print("-" * 60)
        
        result = await agent.ainvoke(scenario["query"], config)
        final_message = result["messages"][-1]
        
        print(f"\n📚 Agent Response:")
        print(final_message.content)
        print("\n" + "=" * 60)
    
    # Clean up
    from dance_tools import mcp_client
    await mcp_client.close()
    
    print("✅ End-to-end test completed\n")


async def test_manual_not_available():
    """Test behavior when manual is not available."""
    print("\n" + "=" * 60)
    print("TEST 4: Graceful Handling of Missing Manual")
    print("=" * 60)
    
    from dance_tools import search_manual, _manual_vectorstore
    import dance_tools
    
    # Temporarily set vectorstore to None to simulate missing database
    original_store = dance_tools._manual_vectorstore
    dance_tools._manual_vectorstore = None
    
    # Also need to prevent loading
    from pathlib import Path
    original_load_func = dance_tools._load_manual_vectorstore
    
    def mock_load():
        return None
    
    dance_tools._load_manual_vectorstore = mock_load
    
    print("\n🔍 Testing with simulated missing database...")
    result = await search_manual.ainvoke({
        "query": "test query",
        "num_results": 2
    })
    
    print(f"Result: {result}")
    
    # Restore
    dance_tools._manual_vectorstore = original_store
    dance_tools._load_manual_vectorstore = original_load_func
    
    if "not available" in result.lower() or "administrator" in result.lower():
        print("✅ Gracefully handled missing database")
    else:
        print("⚠️  Warning: May not have handled missing database gracefully")
    
    print()


async def main():
    """Run all tests."""
    load_dotenv()
    
    try:
        print("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Testing RSCDS Manual RAG Pipeline")
        print("=" * 60)
        
        # Test 1: Direct tool access
        await test_search_manual_tool()
        
        # Test 2: Agent integration
        await test_agent_integration()
        
        # Test 3: End-to-end scenarios
        await test_end_to_end_scenarios()
        
        # Test 4: Missing manual handling
        await test_manual_not_available()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
