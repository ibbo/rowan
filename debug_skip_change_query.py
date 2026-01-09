#!/usr/bin/env python3
"""Debug skip change of step query to see what's being returned."""

import asyncio
from dotenv import load_dotenv
from dance_tools import search_manual

async def debug_query():
    """Test the exact query that's failing."""
    
    print("="*80)
    print("DEBUG: Testing 'how to teach skip change of step'")
    print("="*80)
    
    # Test the exact query
    result = await search_manual.ainvoke({
        "query": "how to teach skip change of step",
        "num_results": 5  # Get more results to see what's ranking
    })
    
    print("\nFULL RESULT:")
    print(result)
    print("\n" + "="*80)
    
    # Also test direct database query
    from langchain_openai import OpenAIEmbeddings
    from langchain_community.vectorstores import Chroma
    from pathlib import Path
    
    db_path = Path("data/vector_db/rscds_manual_structured")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    vectorstore = Chroma(
        persist_directory=str(db_path),
        embedding_function=embeddings,
        collection_name="rscds_manual"
    )
    
    print("\nDIRECT DATABASE QUERY (Top 5 results):")
    print("="*80)
    
    docs = vectorstore.similarity_search("how to teach skip change of step", k=5)
    
    for i, doc in enumerate(docs, 1):
        print(f"\n--- RESULT {i} ---")
        print(f"Section: {doc.metadata.get('section_number')} - {doc.metadata.get('title')}")
        print(f"Type: {doc.metadata.get('section_type')}")
        print(f"Formation: {doc.metadata.get('formation_name')}")
        print(f"Page: {doc.metadata.get('page')}")
        print(f"Content preview: {doc.page_content[:300]}...")

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(debug_query())
