#!/usr/bin/env python3
"""
Improved manual search with metadata filtering and query preprocessing.

This module provides enhanced RAG capabilities that:
1. Extracts formation names from queries
2. Filters chunks by formation metadata before retrieval
3. Uses hybrid retrieval (metadata + semantic search)
4. Provides more accurate, focused results
"""

import re
import json
from typing import List, Dict, Optional, Tuple
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings


class ImprovedManualSearch:
    """Enhanced manual search with metadata filtering."""
    
    def __init__(self, vectorstore: Chroma):
        """Initialize the improved search.
        
        Args:
            vectorstore: Chroma vectorstore (ideally enriched with metadata)
        """
        self.vectorstore = vectorstore
        
        # Common formation name patterns for extraction
        self.formation_patterns = [
            # Multi-word formations
            r'\b(skip change of step|skip change)\b',
            r'\b(pas de basque|pas-de-basque)\b',
            r'\b(slip step)\b',
            r'\b(strathspey traveling step)\b',
            r'\b(rights and lefts)\b',
            r'\b(hands across)\b',
            r'\b(grand chain)\b',
            r'\b(ladies[\'\']? chain)\b',
            r'\b(men[\'\']s chain)\b',
            r'\b(set and turn)\b',
            r'\b(set and link)\b',
            r'\b(advance and retire)\b',
            r'\b(reels? of three in tandem)\b',
            r'\b(reels? of three)\b',
            r'\b(reels? of four)\b',
            r'\b(inveran reels?)\b',
            r'\b(corners pass and turn)\b',
            r'\b(turn corners)\b',
            r'\b(balance in line)\b',
            r'\b(petronella turn)\b',
            r'\b(schiehallion reel)\b',
            # Single-word formations
            r'\b(poussette)\b',
            r'\b(allemande)\b',
            r'\b(poussin)\b',
            r'\b(espagnole)\b',
            r'\b(promenade)\b',
            r'\b(tournée)\b',
            r'\b(bourrel)\b',
            r'\b(cast(?:ing)?)\b',
        ]
    
    def extract_formation_from_query(self, query: str) -> Optional[str]:
        """Extract formation name from user query.
        
        Args:
            query: User's search query
            
        Returns:
            Extracted formation name or None
        """
        query_lower = query.lower()
        
        # Try to match known formations
        for pattern in self.formation_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                formation = match.group(1)
                # Normalize variations
                formation = formation.replace('-', ' ')
                if formation == 'skip change':
                    formation = 'skip change of step'
                return formation
        
        return None
    
    def search_with_metadata_filter(
        self,
        query: str,
        formation_filter: Optional[str] = None,
        k: int = 3,
        score_threshold: Optional[float] = None
    ) -> List[Dict]:
        """Search with optional formation metadata filtering.
        
        Args:
            query: Search query
            formation_filter: Formation name to filter by
            k: Number of results
            score_threshold: Minimum similarity score
            
        Returns:
            List of results with content and metadata
        """
        # If we have a formation filter and the vectorstore has metadata
        if formation_filter:
            # Try metadata filtering
            try:
                # First attempt: strict filter (primary_formation matches)
                filter_dict = {
                    "$or": [
                        {"primary_formation": {"$eq": formation_filter}},
                        {"formations_mentioned": {"$in": [formation_filter]}}
                    ]
                }
                
                results = self.vectorstore.similarity_search(
                    query,
                    k=k * 2,  # Get more results to filter
                    filter=filter_dict
                )
                
                # If we got good results, use them
                if results and len(results) >= k:
                    return results[:k]
                    
            except Exception as e:
                # Metadata filtering not available or failed
                print(f"ℹ️  Metadata filtering not available: {e}")
        
        # Fallback to standard similarity search
        results = self.vectorstore.similarity_search(query, k=k)
        return results
    
    def search_with_reranking(
        self,
        query: str,
        initial_k: int = 10,
        final_k: int = 3,
        formation_filter: Optional[str] = None
    ) -> List[Dict]:
        """Search with two-stage retrieval and re-ranking.
        
        Args:
            query: Search query
            initial_k: Number of initial candidates to retrieve
            final_k: Number of final results to return
            formation_filter: Optional formation name to filter by
            
        Returns:
            Re-ranked list of results
        """
        # Stage 1: Retrieve candidates with metadata filter
        candidates = self.search_with_metadata_filter(
            query,
            formation_filter=formation_filter,
            k=initial_k
        )
        
        if not candidates:
            return []
        
        # Stage 2: Re-rank by relevance
        # If we have a formation filter, prefer chunks focused on that formation
        if formation_filter:
            scored_results = []
            for doc in candidates:
                score = 0.0
                
                # Boost if this is the primary formation
                if doc.metadata.get('primary_formation') == formation_filter:
                    score += 2.0
                
                # Boost if formation is mentioned
                formations_raw = doc.metadata.get('formations_mentioned', '[]')
                # Parse JSON string if needed
                try:
                    formations_mentioned = json.loads(formations_raw) if isinstance(formations_raw, str) else formations_raw
                except:
                    formations_mentioned = []
                
                if formation_filter in formations_mentioned:
                    score += 1.0
                
                # Penalize if other formations are also prominent
                other_formations = [f for f in formations_mentioned if f != formation_filter]
                if len(other_formations) > 2:
                    score -= 0.5
                
                # Prefer teaching points and descriptions over examples
                section_type = doc.metadata.get('section_type', '')
                if section_type in ['teaching_points', 'description', 'technique']:
                    score += 0.5
                elif section_type == 'example':
                    score -= 0.3
                
                scored_results.append((score, doc))
            
            # Sort by score descending
            scored_results.sort(key=lambda x: x[0], reverse=True)
            return [doc for score, doc in scored_results[:final_k]]
        
        # No filter - just return top k
        return candidates[:final_k]
    
    def smart_search(
        self,
        query: str,
        num_results: int = 3,
        auto_extract_formation: bool = True
    ) -> Tuple[List[Dict], Optional[str]]:
        """Smart search with automatic formation detection and filtering.
        
        Args:
            query: User's search query
            num_results: Number of results to return
            auto_extract_formation: Whether to automatically extract formation from query
            
        Returns:
            Tuple of (results, detected_formation)
        """
        detected_formation = None
        
        # Try to extract formation from query
        if auto_extract_formation:
            detected_formation = self.extract_formation_from_query(query)
            if detected_formation:
                print(f"🎯 Detected formation: '{detected_formation}'")
        
        # Use enhanced search with re-ranking
        results = self.search_with_reranking(
            query,
            initial_k=min(num_results * 3, 15),
            final_k=num_results,
            formation_filter=detected_formation
        )
        
        return results, detected_formation


def format_search_results(
    results: List[Dict],
    query: str,
    detected_formation: Optional[str] = None
) -> str:
    """Format search results into a readable string.
    
    Args:
        results: List of search results
        query: Original query
        detected_formation: Detected formation name if any
        
    Returns:
        Formatted string
    """
    if not results:
        return f"No relevant information found in the RSCDS manual for: '{query}'"
    
    formatted = []
    
    # Header
    header = f"📚 **RSCDS Manual - Relevant Information for '{query}'**"
    if detected_formation:
        header += f"\n🎯 *Focused on formation: {detected_formation}*"
    formatted.append(header)
    formatted.append("")
    
    # Results
    for i, doc in enumerate(results, 1):
        page = doc.metadata.get('page', 'N/A')
        primary_formation = doc.metadata.get('primary_formation', 'N/A')
        section_type = doc.metadata.get('section_type', 'N/A')
        
        # Section header with metadata
        section_header = f"**Section {i} (Page {page})**"
        if primary_formation != 'N/A':
            section_header += f" - *{primary_formation}*"
        if section_type in ['teaching_points', 'technique', 'description']:
            section_header += f" [{section_type.replace('_', ' ').title()}]"
        
        formatted.append(section_header)
        formatted.append(doc.page_content.strip())
        formatted.append("-" * 50)
        formatted.append("")
    
    return "\n".join(formatted)


# Example usage and testing
if __name__ == "__main__":
    from pathlib import Path
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Load enriched vectorstore
    db_path = Path("data/vector_db/rscds_manual_enriched")
    if not db_path.exists():
        print(f"❌ Enriched database not found. Run enrich_manual_metadata.py first.")
        exit(1)
    
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = Chroma(
        persist_directory=str(db_path),
        embedding_function=embeddings,
        collection_name="rscds_manual"
    )
    
    # Test improved search
    searcher = ImprovedManualSearch(vectorstore)
    
    test_queries = [
        "How do I teach skip change of step?",
        "Explain pas-de-basque technique",
        "What are the teaching points for rights and lefts?",
        "How to dance a poussette"
    ]
    
    for query in test_queries:
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        print("=" * 60)
        
        results, detected_formation = searcher.smart_search(query, num_results=3)
        formatted = format_search_results(results, query, detected_formation)
        print(formatted)
