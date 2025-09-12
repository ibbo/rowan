#!/usr/bin/env python3
"""
Test script for the improved dance search functionality.
Tests both variety (randomization) and RSCDS filtering improvements.
"""

import asyncio
import json
import sys
import os
from mcp_scddb_server import call_tool

async def test_variety():
    """Test that random_variety=True gives different results"""
    print("=== Testing Variety (Randomization) ===")
    
    # Get results with random_variety=True twice
    args1 = {"random_variety": True, "limit": 10}
    args2 = {"random_variety": True, "limit": 10}
    
    result1 = await call_tool("find_dances", args1)
    result2 = await call_tool("find_dances", args2)
    
    dances1 = json.loads(result1[0].text)
    dances2 = json.loads(result2[0].text)
    
    print(f"Random search 1 returned {len(dances1)} dances:")
    for dance in dances1[:5]:  # Show first 5
        print(f"  - {dance['name']} ({dance['kind']})")
    
    print(f"\nRandom search 2 returned {len(dances2)} dances:")
    for dance in dances2[:5]:  # Show first 5
        print(f"  - {dance['name']} ({dance['kind']})")
    
    # Check if results are different (they should be unless we're very unlucky)
    names1 = [d['name'] for d in dances1]
    names2 = [d['name'] for d in dances2]
    
    if names1 != names2:
        print("✓ SUCCESS: Random searches returned different results!")
    else:
        print("⚠ WARNING: Random searches returned identical results (this could happen by chance)")
    
    # Test alphabetical ordering (default)
    print("\n--- Testing Alphabetical Order (default) ---")
    args_alpha = {"limit": 10}
    result_alpha = await call_tool("find_dances", args_alpha)
    dances_alpha = json.loads(result_alpha[0].text)
    
    print(f"Alphabetical search returned {len(dances_alpha)} dances:")
    for dance in dances_alpha[:5]:
        print(f"  - {dance['name']} ({dance['kind']})")
    
    # Check if alphabetically ordered
    names_alpha = [d['name'] for d in dances_alpha]
    is_sorted = names_alpha == sorted(names_alpha)
    if is_sorted:
        print("✓ SUCCESS: Default search returns alphabetically sorted results!")
    else:
        print("✗ ERROR: Default search is not alphabetically sorted!")

async def test_rscds_filtering():
    """Test RSCDS filtering with new parameter name"""
    print("\n=== Testing RSCDS Filtering ===")
    
    # Test official RSCDS dances
    print("--- Testing Official RSCDS Dances ---")
    args_rscds = {"official_rscds_dances": True, "limit": 5}
    result_rscds = await call_tool("find_dances", args_rscds)
    dances_rscds = json.loads(result_rscds[0].text)
    
    print(f"RSCDS-only search returned {len(dances_rscds)} dances:")
    for dance in dances_rscds:
        print(f"  - {dance['name']} ({dance['kind']}, {dance['bars']} bars)")
        
        # Get details to confirm RSCDS publication
        detail_result = await call_tool("dance_detail", {"dance_id": dance['id']})
        detail = json.loads(detail_result[0].text)
        rscds_pubs = [p for p in detail['publications'] if p['rscds']]
        if rscds_pubs:
            print(f"    ✓ Published by RSCDS: {', '.join([p['name'] for p in rscds_pubs])}")
        else:
            print(f"    ✗ ERROR: No RSCDS publications found!")
    
    # Test non-RSCDS dances
    print("\n--- Testing Non-RSCDS Dances ---")
    args_non_rscds = {"official_rscds_dances": False, "limit": 5}
    result_non_rscds = await call_tool("find_dances", args_non_rscds)
    dances_non_rscds = json.loads(result_non_rscds[0].text)
    
    print(f"Non-RSCDS search returned {len(dances_non_rscds)} dances:")
    for dance in dances_non_rscds[:3]:  # Check first 3
        print(f"  - {dance['name']} ({dance['kind']}, {dance['bars']} bars)")
        
        # Get details to confirm no RSCDS publication
        detail_result = await call_tool("dance_detail", {"dance_id": dance['id']})
        detail = json.loads(detail_result[0].text)
        rscds_pubs = [p for p in detail['publications'] if p['rscds']]
        if not rscds_pubs:
            print(f"    ✓ No RSCDS publications (community dance)")
        else:
            print(f"    ✗ ERROR: Found RSCDS publications: {', '.join([p['name'] for p in rscds_pubs])}")

async def test_backward_compatibility():
    """Test that old parameter name still works"""
    print("\n=== Testing Backward Compatibility ===")
    
    # Test old parameter name
    args_old = {"rscds_only": True, "limit": 3}
    result_old = await call_tool("find_dances", args_old)
    dances_old = json.loads(result_old[0].text)
    
    print(f"Old parameter 'rscds_only' returned {len(dances_old)} dances:")
    for dance in dances_old:
        print(f"  - {dance['name']} ({dance['kind']})")
    
    if len(dances_old) > 0:
        print("✓ SUCCESS: Backward compatibility maintained!")
    else:
        print("✗ ERROR: Old parameter name not working!")

async def main():
    # Check if database exists
    db_path = os.environ.get("SCDDB_SQLITE", "data/scddb/scddb.sqlite")
    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        print("Please run refresh_scddb.py first or set SCDDB_SQLITE environment variable")
        return 1
    
    try:
        await test_variety()
        await test_rscds_filtering()
        await test_backward_compatibility()
        print("\n🎉 All tests completed!")
        return 0
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
