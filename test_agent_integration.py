#!/usr/bin/env python3
"""
Test that the dance agent properly exposes the new RSCDS filtering and variety parameters.
"""

import asyncio
import sys
from dance_agent import find_dances, mcp_client

async def test_agent_tool():
    """Test the updated find_dances tool in dance_agent.py"""
    print("=== Testing Dance Agent Tool Integration ===")
    
    await mcp_client.setup()
    
    # Test RSCDS filtering through agent
    print("--- Testing Official RSCDS Dances through Agent ---")
    rscds_results = await find_dances.ainvoke({
        "official_rscds_dances": True, 
        "limit": 3
    })
    
    print(f"RSCDS search returned {len(rscds_results)} dances:")
    for dance in rscds_results:
        print(f"  - {dance['name']} ({dance['kind']}, {dance['bars']} bars)")
    
    # Test variety through agent
    print("\n--- Testing Random Variety through Agent ---")
    variety_results = await find_dances.ainvoke({
        "random_variety": True, 
        "limit": 5
    })
    
    print(f"Random search returned {len(variety_results)} dances:")
    for dance in variety_results:
        print(f"  - {dance['name']} ({dance['kind']}, {dance['bars']} bars)")
    
    # Test combination
    print("\n--- Testing Combined Parameters ---")
    combined_results = await find_dances.ainvoke({
        "kind": "Reel",
        "official_rscds_dances": True,
        "random_variety": True,
        "limit": 3
    })
    
    print(f"Combined search (RSCDS Reels, randomized) returned {len(combined_results)} dances:")
    for dance in combined_results:
        print(f"  - {dance['name']} ({dance['kind']}, {dance['bars']} bars)")
    
    print("\n✅ All agent integration tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_agent_tool())
