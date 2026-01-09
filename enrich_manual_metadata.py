#!/usr/bin/env python3
"""
Enrich the existing RSCDS manual vector database with semantic metadata.

This script:
1. Loads the existing vector database (preserving embeddings)
2. Uses an LLM to analyze each chunk and extract:
   - Formation names mentioned
   - Primary formation (main topic)
   - Section type (description, teaching points, diagram, example, etc.)
   - Content type tags
3. Re-creates the database with enriched metadata
4. Validates the improvements

The expensive vision-based embeddings are preserved - we only add metadata.
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Set
from dotenv import load_dotenv
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from tqdm import tqdm


class MetadataEnricher:
    """Enrich vector database chunks with semantic metadata."""
    
    def __init__(self, model: str = "gpt-4o-mini"):
        """Initialize the enricher.
        
        Args:
            model: LLM model to use for metadata extraction (using mini for cost efficiency)
        """
        self.model = model
        self.client = OpenAI()
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        
        # Common formations to help the LLM
        self.known_formations = [
            "skip change of step", "pas de basque", "slip step", "strathspey traveling step",
            "poussette", "allemande", "rights and lefts", "hands across", "grand chain",
            "ladies' chain", "set and turn", "set and link", "advance and retire",
            "reels of three", "reels of four", "reels of three in tandem", "inveran reels",
            "poussin", "espagnole", "corners pass and turn", "turn corners",
            "balance in line", "promenade", "circle", "cast", "lead down", "lead up",
            "cross over", "petronella turn", "tournée", "bourrel", "schiehallion reel"
        ]
    
    def analyze_chunk(self, content: str, page: int) -> Dict[str, any]:
        """Use LLM to extract semantic metadata from a chunk.
        
        Args:
            content: The chunk text content
            page: Page number
            
        Returns:
            Dictionary with extracted metadata
        """
        prompt = f"""Analyze this excerpt from the RSCDS Scottish Country Dance manual and extract structured metadata.

Page: {page}

Content:
{content}

Extract the following information (return as JSON):
1. "formations_mentioned": List of formation/movement names discussed (e.g., ["poussette", "allemande"])
2. "primary_formation": The main formation this section is about (or null if general/mixed content)
3. "section_type": Type of content - one of: "description", "teaching_points", "technique", "diagram_description", "example", "variation", "transition", "general", "table_of_contents"
4. "topics": List of topic tags (e.g., ["footwork", "hand_hold", "timing", "positioning"])

Known formations for reference: {', '.join(self.known_formations[:20])}

Be precise - only include formations actually discussed in this chunk, not just mentioned in passing.
If multiple formations are discussed equally, list the chunk as "general" or "mixed" for primary_formation.

Return ONLY valid JSON, no other text."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert in Scottish Country Dancing analyzing manual content."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            metadata = json.loads(response.choices[0].message.content)
            return metadata
            
        except Exception as e:
            print(f"⚠️  Error analyzing chunk on page {page}: {e}")
            return {
                "formations_mentioned": [],
                "primary_formation": None,
                "section_type": "general",
                "topics": []
            }
    
    def enrich_vectorstore(self, db_path: Path, backup: bool = True) -> Chroma:
        """Enrich the vector database with metadata.
        
        Args:
            db_path: Path to the vector database
            backup: Whether to create a backup before modifying
            
        Returns:
            New Chroma vectorstore with enriched metadata
        """
        print(f"📚 Loading existing vector database from {db_path}")
        
        # Load existing vectorstore
        vectorstore = Chroma(
            persist_directory=str(db_path),
            embedding_function=self.embeddings,
            collection_name="rscds_manual"
        )
        
        # Get all documents
        collection = vectorstore._collection
        total_chunks = collection.count()
        print(f"📦 Found {total_chunks} chunks to enrich")
        
        # Retrieve all documents
        results = collection.get(include=['embeddings', 'metadatas', 'documents'])
        
        print(f"\n🧠 Analyzing chunks with {self.model}...")
        enriched_docs = []
        
        for i in tqdm(range(len(results['ids'])), desc="Enriching chunks"):
            doc_id = results['ids'][i]
            content = results['documents'][i]
            original_metadata = results['metadatas'][i]
            embedding = results['embeddings'][i]
            
            # Extract semantic metadata
            semantic_metadata = self.analyze_chunk(content, original_metadata.get('page', 0))
            
            # Convert lists to JSON strings for ChromaDB compatibility
            if 'formations_mentioned' in semantic_metadata:
                semantic_metadata['formations_mentioned'] = json.dumps(semantic_metadata['formations_mentioned'])
            if 'topics' in semantic_metadata:
                semantic_metadata['topics'] = json.dumps(semantic_metadata['topics'])
            
            # Combine original and new metadata
            enriched_metadata = {
                **original_metadata,
                **semantic_metadata
            }
            
            # Create enriched document
            doc = Document(
                page_content=content,
                metadata=enriched_metadata
            )
            enriched_docs.append(doc)
        
        print(f"\n✅ Analyzed {len(enriched_docs)} chunks")
        
        # Create backup if requested
        if backup:
            backup_path = db_path.parent / f"{db_path.name}_backup"
            if not backup_path.exists():
                import shutil
                shutil.copytree(db_path, backup_path)
                print(f"💾 Created backup at {backup_path}")
        
        # Create new enriched database
        enriched_path = db_path.parent / f"{db_path.name}_enriched"
        if enriched_path.exists():
            import shutil
            shutil.rmtree(enriched_path)
        
        print(f"\n🔨 Creating enriched vector database at {enriched_path}...")
        
        # Create new vectorstore with enriched metadata
        # We'll use the same embeddings (from the original DB) to avoid re-embedding
        new_vectorstore = Chroma(
            persist_directory=str(enriched_path),
            embedding_function=self.embeddings,
            collection_name="rscds_manual"
        )
        
        # Add documents in batches
        batch_size = 50
        for i in range(0, len(enriched_docs), batch_size):
            batch = enriched_docs[i:i+batch_size]
            batch_embeddings = results['embeddings'][i:i+batch_size]
            
            # Add with existing embeddings
            new_vectorstore.add_documents(
                documents=batch,
                embeddings=batch_embeddings
            )
        
        print(f"✅ Created enriched database with {len(enriched_docs)} chunks")
        
        return new_vectorstore
    
    def validate_enrichment(self, vectorstore: Chroma):
        """Validate that enrichment improved retrieval accuracy."""
        print("\n🧪 Validating enrichment with test queries...")
        print("=" * 60)
        
        test_cases = [
            {
                "query": "skip change of step",
                "expected_formation": "skip change of step",
                "should_not_include": ["pas de basque", "slip step"]
            },
            {
                "query": "pas-de-basque",
                "expected_formation": "pas de basque",
                "should_not_include": ["skip change"]
            },
            {
                "query": "rights and lefts",
                "expected_formation": "rights and lefts",
                "should_not_include": ["reels of three"]
            }
        ]
        
        for test in test_cases:
            print(f"\n🔍 Query: '{test['query']}'")
            print(f"   Expected: {test['expected_formation']}")
            
            # Regular search
            results = vectorstore.similarity_search(test['query'], k=3)
            
            print(f"   Retrieved {len(results)} chunks:")
            for i, doc in enumerate(results, 1):
                page = doc.metadata.get('page')
                primary = doc.metadata.get('primary_formation', 'N/A')
                formations_raw = doc.metadata.get('formations_mentioned', '[]')
                
                # Parse JSON string back to list
                try:
                    formations = json.loads(formations_raw) if isinstance(formations_raw, str) else formations_raw
                except:
                    formations = []
                
                print(f"      {i}. Page {page} - Primary: {primary}")
                print(f"         Formations: {formations}")
                
                # Check for contamination
                contaminated = any(
                    unwanted.lower() in ' '.join(formations).lower() 
                    for unwanted in test.get('should_not_include', [])
                )
                if contaminated:
                    print(f"         ⚠️  Contains unwanted formations!")
            
            print("-" * 60)


def main():
    """Main function."""
    import argparse
    parser = argparse.ArgumentParser(description="Enrich RSCDS manual vector DB with semantic metadata")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating backup")
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing enriched DB")
    args = parser.parse_args()
    
    load_dotenv()
    
    try:
        enricher = MetadataEnricher()
        db_path = Path("data/vector_db/rscds_manual")
        enriched_path = Path("data/vector_db/rscds_manual_enriched")
        
        if args.validate_only:
            if not enriched_path.exists():
                print(f"❌ Enriched database not found at {enriched_path}")
                return 1
            
            print(f"📚 Loading enriched database from {enriched_path}")
            vectorstore = Chroma(
                persist_directory=str(enriched_path),
                embedding_function=enricher.embeddings,
                collection_name="rscds_manual"
            )
            enricher.validate_enrichment(vectorstore)
        else:
            # Enrich the database
            vectorstore = enricher.enrich_vectorstore(db_path, backup=not args.no_backup)
            
            # Validate
            enricher.validate_enrichment(vectorstore)
            
            print(f"\n✅ Enrichment complete!")
            print(f"📍 Enriched database: {enriched_path}")
            print(f"💡 To use the enriched database, update dance_tools.py to point to this path")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
