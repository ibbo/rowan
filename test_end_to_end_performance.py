#!/usr/bin/env python3
"""
End-to-end performance test for the Scottish Country Dance system.
Tests the complete flow from user query to response to identify bottlenecks.
"""

import asyncio
import time
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Import the components to test
from dance_agent import create_dance_agent, mcp_client
from langchain_core.messages import HumanMessage

async def test_component_performance():
    """Test individual components to isolate bottlenecks."""
    print("=" * 60)
    print("COMPONENT PERFORMANCE ANALYSIS")
    print("=" * 60)
    
    # Test 1: MCP Client Setup
    print("\n1. Testing MCP Client Setup...")
    setup_start = time.perf_counter()
    await mcp_client.setup()
    setup_end = time.perf_counter()
    setup_time = (setup_end - setup_start) * 1000
    print(f"   MCP Setup: {setup_time:.2f}ms")
    
    # Test 2: Direct MCP Tool Calls
    print("\n2. Testing Direct MCP Tool Calls...")
    
    # Simple find_dances call
    tool_start = time.perf_counter()
    result = await mcp_client.call_tool("find_dances", {"limit": 5})
    tool_end = time.perf_counter()
    tool_time = (tool_end - tool_start) * 1000
    print(f"   Direct MCP find_dances: {tool_time:.2f}ms ({len(result)} results)")
    
    # Test 3: Agent Creation
    print("\n3. Testing Agent Creation...")
    agent_create_start = time.perf_counter()
    agent = await create_dance_agent()
    agent_create_end = time.perf_counter()
    agent_create_time = (agent_create_end - agent_create_start) * 1000
    print(f"   Agent Creation: {agent_create_time:.2f}ms")
    
    return agent

async def test_simple_agent_query(agent):
    """Test a simple agent query to isolate LLM vs tool overhead."""
    print("\n4. Testing Simple Agent Query (no tools needed)...")
    
    simple_query = "What is Scottish Country Dancing?"
    messages = [HumanMessage(content=simple_query)]
    
    simple_start = time.perf_counter()
    response = await agent.ainvoke({"messages": messages})
    simple_end = time.perf_counter()
    simple_time = (simple_end - simple_start) * 1000
    
    print(f"   Simple Query (no tools): {simple_time:.2f}ms")
    print(f"   Response length: {len(response['messages'][-1].content)} chars")
    
    return simple_time

async def test_tool_using_query(agent):
    """Test a query that requires tool usage."""
    print("\n5. Testing Tool-Using Query...")
    
    tool_query = "Find me 3 reels"
    messages = [HumanMessage(content=(
        "You are a Scottish Country Dance expert assistant with access to the Scottish Country Dance Database (SCDDB). "
        "Use the find_dances tool to help users find dances.\n\n"
        f"User question: {tool_query}"
    ))]
    
    tool_start = time.perf_counter()
    response = await agent.ainvoke({"messages": messages})
    tool_end = time.perf_counter()
    tool_time = (tool_end - tool_start) * 1000
    
    print(f"   Tool-Using Query: {tool_time:.2f}ms")
    print(f"   Response length: {len(response['messages'][-1].content)} chars")
    
    # Count how many messages (indicates tool calls)
    message_count = len(response['messages'])
    print(f"   Total messages in response: {message_count}")
    
    return tool_time

async def test_complex_multi_tool_query(agent):
    """Test a complex query that requires multiple tool calls."""
    print("\n6. Testing Complex Multi-Tool Query...")
    
    complex_query = "Find me a 32-bar reel, then show me the details of the first one you find"
    messages = [HumanMessage(content=(
        "You are a Scottish Country Dance expert assistant with access to the Scottish Country Dance Database (SCDDB). "
        "Use find_dances to search and get_dance_detail for detailed information.\n\n"
        f"User question: {complex_query}"
    ))]
    
    complex_start = time.perf_counter()
    response = await agent.ainvoke({"messages": messages})
    complex_end = time.perf_counter()
    complex_time = (complex_end - complex_start) * 1000
    
    print(f"   Complex Multi-Tool Query: {complex_time:.2f}ms")
    print(f"   Response length: {len(response['messages'][-1].content)} chars")
    print(f"   Total messages in response: {len(response['messages'])}")
    
    return complex_time

async def test_openai_api_latency():
    """Test OpenAI API latency directly."""
    print("\n7. Testing OpenAI API Latency...")
    
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # Simple test message
    test_messages = [HumanMessage(content="Hello, what is 2+2?")]
    
    api_start = time.perf_counter()
    response = await llm.ainvoke(test_messages)
    api_end = time.perf_counter()
    api_time = (api_end - api_start) * 1000
    
    print(f"   Direct OpenAI API call: {api_time:.2f}ms")
    print(f"   Response: {response.content[:100]}...")
    
    return api_time

async def test_gradio_simulation():
    """Simulate the Gradio flow without actually running Gradio."""
    print("\n8. Testing Gradio Flow Simulation...")
    
    # Simulate what happens in the Gradio interface
    from gradio_app import DanceAgentUI
    
    ui = DanceAgentUI()
    
    test_message = "Find me some jigs"
    history = []
    
    gradio_start = time.perf_counter()
    response = await ui.process_query(test_message, history)
    gradio_end = time.perf_counter()
    gradio_time = (gradio_end - gradio_start) * 1000
    
    print(f"   Gradio Flow Simulation: {gradio_time:.2f}ms")
    print(f"   Response length: {len(response)} chars")
    
    return gradio_time

def analyze_system_resources():
    """Check system resources that might impact performance."""
    print("\n9. System Resource Analysis...")
    
    try:
        import psutil
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        print(f"   CPU Usage: {cpu_percent}%")
        
        # Memory usage
        memory = psutil.virtual_memory()
        print(f"   Memory Usage: {memory.percent}% ({memory.used // (1024**3)}GB / {memory.total // (1024**3)}GB)")
        
        # Disk usage
        disk = psutil.disk_usage('/')
        print(f"   Disk Usage: {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)")
        
        # Network connections
        connections = psutil.net_connections()
        active_connections = len([c for c in connections if c.status == 'ESTABLISHED'])
        print(f"   Active Network Connections: {active_connections}")
        
    except ImportError:
        print("   psutil not available - skipping system resource analysis")
        print("   Install with: uv add psutil (if needed for detailed analysis)")

async def run_comprehensive_test():
    """Run all performance tests and provide analysis."""
    print("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scottish Country Dance System Performance Analysis")
    print("=" * 70)
    
    # Load environment
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set. Please set it to run these tests.")
        return
    
    # Check database exists
    db_path = os.environ.get("SCDDB_SQLITE", "data/scddb/scddb.sqlite")
    if not Path(db_path).exists():
        print(f"❌ Database not found at {db_path}")
        return
    
    print(f"📊 Testing system performance...")
    print(f"Database: {db_path}")
    print(f"OpenAI Model: gpt-4o-mini")
    
    analyze_system_resources()
    
    try:
        # Test components individually
        agent = await test_component_performance()
        
        # Test different query types
        simple_time = await test_simple_agent_query(agent)
        tool_time = await test_tool_using_query(agent)
        complex_time = await test_complex_multi_tool_query(agent)
        
        # Test API directly
        api_time = await test_openai_api_latency()
        
        # Test Gradio simulation
        gradio_time = await test_gradio_simulation()
        
        # Analysis and recommendations
        print("\n" + "=" * 60)
        print("PERFORMANCE ANALYSIS SUMMARY")
        print("=" * 60)
        
        print(f"\nTiming Breakdown:")
        print(f"  • Direct OpenAI API:          {api_time:8.0f}ms")
        print(f"  • Simple Agent Query:         {simple_time:8.0f}ms")
        print(f"  • Tool-Using Query:           {tool_time:8.0f}ms")
        print(f"  • Complex Multi-Tool Query:   {complex_time:8.0f}ms")
        print(f"  • Gradio Flow Simulation:     {gradio_time:8.0f}ms")
        
        # Identify bottlenecks
        print(f"\nBottleneck Analysis:")
        
        if api_time > 30000:  # 30 seconds
            print("  🚨 MAJOR BOTTLENECK: OpenAI API calls are extremely slow")
            print("     This suggests network issues or API throttling")
        
        if simple_time > 60000:  # 1 minute
            print("  🚨 MAJOR BOTTLENECK: Basic agent queries are very slow")
            print("     This suggests LangGraph or LangChain overhead issues")
        
        overhead = tool_time - simple_time
        if overhead > 120000:  # 2 minutes
            print("  🚨 MAJOR BOTTLENECK: Tool execution adds excessive overhead")
            print(f"     Tool overhead: {overhead/1000:.1f}s")
        
        gradio_overhead = gradio_time - complex_time
        if gradio_overhead > 30000:  # 30 seconds
            print("  🚨 BOTTLENECK: Gradio interface adds significant overhead")
            print(f"     Gradio overhead: {gradio_overhead/1000:.1f}s")
        
        # Recommendations
        print(f"\nRecommendations:")
        
        if max(simple_time, tool_time, complex_time) < 30000:  # All under 30s
            print("  ✅ Core system performance looks good")
            print("  💡 Multi-minute delays are likely in the frontend or network")
        else:
            print("  📍 Performance bottlenecks identified above")
            
        if api_time > 10000:  # 10 seconds
            print("  💡 Consider using a faster OpenAI model or checking network")
            
        if tool_time > 2 * simple_time:
            print("  💡 MCP tool calls are adding significant overhead")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main test runner."""
    await run_comprehensive_test()

if __name__ == "__main__":
    asyncio.run(main())
