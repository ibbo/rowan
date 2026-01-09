#!/usr/bin/env python3
"""
Test the improved manual RAG to verify it solves the contamination issues.

This tests the specific problems mentioned:
1. Skip change contaminated with pas-de-basque
2. Rights and lefts contaminated with reels of three (Pelorus Jack example)
"""

import asyncio
from dotenv import load_dotenv
from dance_tools import search_manual


async def test_problematic_queries():
    """Test the queries that previously had contamination issues."""
    
    print("🧪 Testing Improved Manual RAG")
    print("=" * 70)
    print("\nThese queries previously returned contaminated results.")
    print("Now testing with metadata-enriched retrieval...\n")
    
    test_cases = [
        {
            "name": "Skip Change (previously mixed with pas-de-basque)",
            "query": "How do I teach skip change of step?",
            "expected": "Should focus on skip change only",
            "avoid": "pas-de-basque should be minimal or absent"
        },
        {
            "name": "Rights and Lefts (previously contaminated with reels/Pelorus Jack)",
            "query": "Explain rights and lefts formation",
            "expected": "Should focus on rights and lefts only",
            "avoid": "Should not mention reels of three or Pelorus Jack"
        },
        {
            "name": "Pas-de-basque (should not include skip change)",
            "query": "What are the teaching points for pas-de-basque?",
            "expected": "Should focus on pas-de-basque only",
            "avoid": "skip change should be minimal or absent"
        },
        {
            "name": "Poussette technique",
            "query": "How to teach poussette?",
            "expected": "Should focus on poussette",
            "avoid": "Should not mix with other formations"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'=' * 70}")
        print(f"TEST {i}: {test['name']}")
        print(f"{'=' * 70}")
        print(f"Query: {test['query']}")
        print(f"Expected: {test['expected']}")
        print(f"Avoid: {test['avoid']}")
        print(f"\n{'-' * 70}\n")
        
        # Call the improved search_manual tool
        result = await search_manual.ainvoke({
            "query": test['query'],
            "num_results": 3
        })
        
        print(result)
        print(f"\n{'-' * 70}")
        
        # Simple contamination check
        query_lower = test['query'].lower()
        result_lower = result.lower()
        
        print("\n📊 Analysis:")
        
        # Check if the right formation is mentioned
        if "skip change" in query_lower and "skip change" in result_lower:
            print("✓ Contains expected formation (skip change)")
        elif "rights and lefts" in query_lower and "rights and lefts" in result_lower:
            print("✓ Contains expected formation (rights and lefts)")
        elif "pas" in query_lower and "pas de basque" in result_lower:
            print("✓ Contains expected formation (pas-de-basque)")
        elif "poussette" in query_lower and "poussette" in result_lower:
            print("✓ Contains expected formation (poussette)")
        
        # Check for contamination
        warnings = []
        if "skip change" in query_lower and "pas de basque" in result_lower and "pas" not in query_lower:
            warnings.append("⚠️  May contain pas-de-basque content")
        if "rights and lefts" in query_lower:
            if "pelorus jack" in result_lower:
                warnings.append("⚠️  Contains Pelorus Jack (from wrong page)")
            if "reel" in result_lower and "three" in result_lower:
                # Check if it's genuinely contaminated or just incidental mention
                if "reels of three" in result_lower or "reel of three" in result_lower:
                    warnings.append("⚠️  May contain reels of three content")
        
        if warnings:
            for warning in warnings:
                print(warning)
        else:
            print("✓ No obvious contamination detected")
        
        # Check for metadata indicators
        if "Focused on formation:" in result:
            print("✓ Formation detection working")
        if "[Teaching Points]" in result or "[Description]" in result or "[Technique]" in result:
            print("✓ Section type metadata working")
        
        print()
    
    print("\n" + "=" * 70)
    print("✅ All tests completed!")
    print("=" * 70)
    print("\nNote: Review the results above to verify contamination has been reduced.")
    print("The improved RAG should:")
    print("  1. Detect the formation name from the query (shown as 'Focused on formation')")
    print("  2. Return chunks primarily about that formation")
    print("  3. Include metadata tags like [Teaching Points], [Description], etc.")
    print("  4. Minimize or eliminate cross-contamination from other formations")


async def main():
    """Run the tests."""
    load_dotenv()
    
    try:
        await test_problematic_queries()
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
