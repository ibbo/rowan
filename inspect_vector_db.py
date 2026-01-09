#!/usr/bin/env python3
"""
Inspect the existing RSCDS manual vector database to understand its structure.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

def inspect_vectorstore():
    """Inspect the existing vector database."""
    db_path = Path("data/vector_db/rscds_manual")
    
    if not db_path.exists():
        print(f"❌ Vector database not found at {db_path}")
        return 1
    
    print(f"📊 Inspecting vector database at {db_path}")
    print("=" * 60)
    
    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        vectorstore = Chroma(
            persist_directory=str(db_path),
            embedding_function=embeddings,
            collection_name="rscds_manual"
        )
        
        # Get collection info
        collection = vectorstore._collection
        print(f"\n📚 Collection: {collection.name}")
        print(f"📦 Total chunks: {collection.count()}")
        
        # Sample some documents
        print(f"\n🔍 Sample chunks:\n")
        results = vectorstore.similarity_search("formation", k=5)
        
        for i, doc in enumerate(results, 1):
            print(f"\n--- Chunk {i} ---")
            print(f"Page: {doc.metadata.get('page', 'N/A')}")
            print(f"Source: {doc.metadata.get('source', 'N/A')}")
            print(f"Metadata keys: {list(doc.metadata.keys())}")
            print(f"Content length: {len(doc.page_content)} chars")
            print(f"Content preview:\n{doc.page_content[:300]}...")
            print("-" * 60)
        
        # Test problematic queries
        print("\n\n🧪 Testing problematic queries:\n")
        
        test_queries = [
            "skip change",
            "pas-de-basque",
            "rights and lefts",
            "reels of three in tandem"
        ]
        
        for query in test_queries:
            print(f"\n🔍 Query: '{query}'")
            results = vectorstore.similarity_search(query, k=3)
            print(f"   Retrieved {len(results)} chunks from pages: {[r.metadata.get('page') for r in results]}")
            
            # Check for contamination
            for i, doc in enumerate(results, 1):
                print(f"\n   Chunk {i} (Page {doc.metadata.get('page')}):")
                # Show first 200 chars
                preview = doc.page_content[:200].replace('\n', ' ')
                print(f"   {preview}...")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    load_dotenv()
    sys.exit(inspect_vectorstore())
