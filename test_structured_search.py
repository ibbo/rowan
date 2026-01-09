#!/usr/bin/env python3
"""Test the structured database for skip change of step."""

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

load_dotenv()

db_path = "data/vector_db/rscds_manual_structured"
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

vectorstore = Chroma(
    persist_directory=db_path,
    embedding_function=embeddings,
    collection_name="rscds_manual"
)

print("="*80)
print("TEST: How to teach skip change of step")
print("="*80)

# Query for skip change of step teaching
results = vectorstore.similarity_search(
    "skip change of step teaching points how to teach",
    k=5
)

for i, doc in enumerate(results, 1):
    print(f"\n{'='*80}")
    print(f"RESULT {i}")
    print('='*80)
    print(f"Section: {doc.metadata.get('section_number')} - {doc.metadata.get('title')}")
    print(f"Type: {doc.metadata.get('section_type')}")
    print(f"Formation: {doc.metadata.get('formation_name')}")
    print(f"Chapter: {doc.metadata.get('chapter_name')}")
    print(f"Page: {doc.metadata.get('page')}")
    print(f"\nContent ({len(doc.page_content)} chars):")
    print(doc.page_content[:1000])
    if len(doc.page_content) > 1000:
        print(f"\n... [truncated, full length: {len(doc.page_content)} chars]")

# Also check what sections exist for skip change
print("\n\n" + "="*80)
print("ALL SECTIONS containing 'skip change'")
print("="*80)

collection = vectorstore._collection
all_docs = collection.get(include=['metadatas', 'documents'])

skip_sections = []
for i, doc_text in enumerate(all_docs['documents']):
    if 'skip change' in doc_text.lower():
        metadata = all_docs['metadatas'][i]
        skip_sections.append({
            'section': metadata.get('section_number'),
            'title': metadata.get('title'),
            'type': metadata.get('section_type'),
            'length': len(doc_text)
        })

for section in skip_sections[:10]:
    print(f"  {section['section']} - {section['title']}")
    print(f"    Type: {section['type']}, Length: {section['length']} chars")
