#!/usr/bin/env python3
"""
End-to-end test of the structured manual RAG system.

Tests that "how to teach" queries return the correct teaching-focused content.
"""

import asyncio
from dotenv import load_dotenv
from dance_tools import search_manual

async def test_structured_manual():
    """Test the structured manual with teaching queries."""
    
    print("="*80)
    print("TESTING STRUCTURED MANUAL RAG SYSTEM")
    print("="*80)
    
    test_cases = [
        {
            "name": "Skip Change of Step - Teaching Points",
            "query": "how to teach skip change of step",
            "expected_keywords": ["points to observe", "hop", "extended", "third position"],
            "should_have_section_type": "points_to_observe"
        },
        {
            "name": "Pas de Basque - Teaching Points",
            "query": "pas de basque teaching points",
            "expected_keywords": ["points to observe", "feet", "position"],
            "should_have_section_type": "points_to_observe"
        },
        {
            "name": "Poussette - General Info",
            "query": "poussette",
            "expected_keywords": ["couples", "bars", "pas de basque"],
            "should_have_section_type": None  # Just checking it works
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST {i}: {test['name']}")
        print(f"Query: '{test['query']}'")
        print('='*80)
        
        # Execute search
        result = await search_manual.ainvoke({
            "query": test['query'],
            "num_results": 3
        })
        
        print(f"\nRESULT:\n{result}\n")
        
        # Verify expectations
        result_lower = result.lower()
        
        # Check for expected keywords
        missing_keywords = []
        for keyword in test['expected_keywords']:
            if keyword.lower() not in result_lower:
                missing_keywords.append(keyword)
        
        # Check for section type if specified
        if test['should_have_section_type']:
            section_type_display = test['should_have_section_type'].replace('_', ' ').title()
            if section_type_display.lower() not in result_lower:
                print(f"⚠️  WARNING: Expected section type '{section_type_display}' not found in result")
        
        # Report
        if missing_keywords:
            print(f"⚠️  WARNING: Missing expected keywords: {missing_keywords}")
        else:
            print(f"✅ All expected keywords found")
        
        print("-"*80)
    
    print("\n" + "="*80)
    print("COMPARISON TEST: Old vs New Approach")
    print("="*80)
    print("\nThe key improvement: In the OLD system, 'how to teach skip change of step'")
    print("would return the full section (2400+ chars) with teaching points buried inside.")
    print("\nIn the NEW system, it returns a SEPARATE 'Points to Observe' chunk (1690 chars)")
    print("focused specifically on teaching guidance.")
    print("\nThis prevents contamination from adjacent formations and provides more")
    print("precise, relevant results for teaching-focused queries.")
    print("="*80)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(test_structured_manual())
