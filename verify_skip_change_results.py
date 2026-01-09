#!/usr/bin/env python3
"""
Comprehensive verification of skip change of step results.
Run this to verify the structured database is working correctly.
"""

import asyncio
from dotenv import load_dotenv
from pathlib import Path

async def verify():
    load_dotenv()
    
    print("="*80)
    print("VERIFICATION: Skip Change of Step Query")
    print("="*80)
    
    # 1. Check which database exists
    print("\n1. CHECKING DATABASE FILES:")
    print("-"*80)
    
    db_dir = Path("data/vector_db")
    if db_dir.exists():
        for db in db_dir.iterdir():
            if db.is_dir():
                size = sum(f.stat().st_size for f in db.rglob('*') if f.is_file())
                print(f"   {db.name}: {size/1024/1024:.2f} MB")
    
    structured_path = Path("data/vector_db/rscds_manual_structured")
    if structured_path.exists():
        print("\n   ✅ Structured database exists")
    else:
        print("\n   ❌ Structured database NOT found!")
        print("   Run: uv run process_manual_structured.py")
        return
    
    # 2. Test direct database query
    print("\n2. DIRECT DATABASE QUERY:")
    print("-"*80)
    
    from langchain_openai import OpenAIEmbeddings
    from langchain_community.vectorstores import Chroma
    
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = Chroma(
        persist_directory=str(structured_path),
        embedding_function=embeddings,
        collection_name="rscds_manual"
    )
    
    # Query for skip change
    docs = vectorstore.similarity_search("how to teach skip change of step", k=3)
    
    print(f"\n   Retrieved {len(docs)} documents:")
    for i, doc in enumerate(docs, 1):
        section_num = doc.metadata.get('section_number', 'N/A')
        title = doc.metadata.get('title', 'N/A')
        section_type = doc.metadata.get('section_type', 'N/A')
        formation = doc.metadata.get('formation_name', 'N/A')
        
        print(f"\n   Document {i}:")
        print(f"      Section: {section_num}")
        print(f"      Title: {title}")
        print(f"      Type: {section_type}")
        print(f"      Formation: {formation}")
        
        # Check content
        content_preview = doc.page_content[:200].replace('\n', ' ')
        print(f"      Content: {content_preview}...")
        
        # Flag any issues
        if "5.4.1" in section_num and section_type == "points_to_observe":
            print(f"      ✅ This is the TEACHING POINTS section!")
        elif "5.4.2" in section_num:
            print(f"      ⚠️  This is PAS DE BASQUE, not skip change!")
    
    # 3. Test search_manual tool
    print("\n3. TESTING search_manual TOOL:")
    print("-"*80)
    
    from dance_tools import search_manual
    
    result = await search_manual.ainvoke({
        "query": "how to teach skip change of step",
        "num_results": 3
    })
    
    print("\n   Tool result (first 1500 chars):")
    print(result[:1500])
    
    # 4. Analysis
    print("\n4. ANALYSIS:")
    print("-"*80)
    
    # Check what's in the results
    has_skip_change = "5.4.1" in result
    has_points_to_observe = "points to observe" in result.lower()
    has_pas_de_basque_section = "5.4.2" in result
    mentions_pas_de_basque = "pas de basque" in result.lower()
    
    print(f"   Contains skip change section (5.4.1): {has_skip_change}")
    print(f"   Contains 'Points to observe': {has_points_to_observe}")
    print(f"   Contains pas de basque section (5.4.2): {has_pas_de_basque_section}")
    print(f"   Mentions 'pas de basque': {mentions_pas_de_basque}")
    
    if has_skip_change and has_points_to_observe:
        print("\n   ✅ CORRECT: Results include skip change teaching points")
    else:
        print("\n   ❌ PROBLEM: Skip change teaching points not found")
    
    if has_pas_de_basque_section:
        print("   ❌ PROBLEM: Results incorrectly include pas de basque main section")
    elif mentions_pas_de_basque and not has_pas_de_basque_section:
        print("   ℹ️  NOTE: Mentions 'pas de basque' in transition context (this is OK)")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    if has_skip_change and has_points_to_observe and not has_pas_de_basque_section:
        print("\n✅ The structured database is working CORRECTLY!")
        print("   - Returns skip change of step content")
        print("   - Includes 'Points to observe' teaching section")
        print("   - No cross-contamination with pas de basque")
        
        if mentions_pas_de_basque:
            print("\nℹ️  Note: The word 'pas de basque' appears in Section 3")
            print("   This is about TRANSITIONS between steps (legitimate context)")
    else:
        print("\n❌ There may be an issue with the database or query")
        print("   Please share this output for debugging")

if __name__ == "__main__":
    asyncio.run(verify())
