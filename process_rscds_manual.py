#!/usr/bin/env python3
"""
Process RSCDS Manual PDF into a vector database for RAG.

This script:
1. Extracts text from the RSCDS manual PDF
2. Chunks the content intelligently (by formations/sections)
3. Generates embeddings using OpenAI
4. Stores everything in ChromaDB for semantic search

Usage:
    export OPENAI_API_KEY="your-key-here"
    uv run process_rscds_manual.py
"""

import os
import sys
from pathlib import Path
from typing import List, Dict

from dotenv import load_dotenv
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document


class RSCDSManualProcessor:
    """Process RSCDS manual into a vector database."""
    
    def __init__(
        self,
        pdf_path: str = "data/raw/rscds-manual.pdf",
        db_path: str = "data/vector_db/rscds_manual",
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """Initialize the processor.
        
        Args:
            pdf_path: Path to the RSCDS manual PDF
            db_path: Path to store the vector database
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
        """
        self.pdf_path = Path(pdf_path)
        self.db_path = Path(db_path)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Check for OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OpenAI API key not found. Please set OPENAI_API_KEY environment variable.\n"
                "Example: export OPENAI_API_KEY='your-key-here'"
            )
        
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small"
        )
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=[
                "\n\n\n",  # Major section breaks
                "\n\n",    # Paragraph breaks
                "\n",      # Line breaks
                ". ",      # Sentence breaks
                " ",       # Word breaks
                ""         # Character breaks
            ]
        )
    
    def extract_text_from_pdf(self) -> List[Dict[str, any]]:
        """Extract text from PDF with page numbers.
        
        Returns:
            List of dicts with 'page', 'text', and 'page_number' keys
        """
        print(f"📖 Extracting text from {self.pdf_path}...")
        
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")
        
        reader = PdfReader(str(self.pdf_path))
        pages_data = []
        
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text.strip():  # Only include pages with text
                pages_data.append({
                    "page_number": page_num,
                    "text": text,
                    "source": str(self.pdf_path)
                })
        
        print(f"✅ Extracted {len(pages_data)} pages")
        return pages_data
    
    def create_documents(self, pages_data: List[Dict]) -> List[Document]:
        """Create LangChain documents from page data.
        
        Args:
            pages_data: List of page dictionaries
            
        Returns:
            List of Document objects with metadata
        """
        print(f"📝 Creating documents and chunking...")
        
        documents = []
        for page_data in pages_data:
            # Create a document for this page
            doc = Document(
                page_content=page_data["text"],
                metadata={
                    "source": page_data["source"],
                    "page": page_data["page_number"]
                }
            )
            documents.append(doc)
        
        # Split documents into chunks
        chunked_docs = self.text_splitter.split_documents(documents)
        
        print(f"✅ Created {len(chunked_docs)} chunks from {len(documents)} pages")
        return chunked_docs
    
    def build_vector_db(self, documents: List[Document]) -> Chroma:
        """Build ChromaDB vector database from documents.
        
        Args:
            documents: List of Document objects
            
        Returns:
            Chroma vector store
        """
        print(f"🔨 Building vector database at {self.db_path}...")
        
        # Create directory if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Delete existing database if present
        if self.db_path.exists():
            import shutil
            shutil.rmtree(self.db_path)
            print(f"🗑️  Removed existing database")
        
        # Create vector store
        vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory=str(self.db_path),
            collection_name="rscds_manual"
        )
        
        print(f"✅ Vector database built with {len(documents)} chunks")
        return vectorstore
    
    def process(self) -> Chroma:
        """Run the full processing pipeline.
        
        Returns:
            Chroma vector store
        """
        print("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Processing RSCDS Manual for RAG")
        print("=" * 50)
        
        # Extract text from PDF
        pages_data = self.extract_text_from_pdf()
        
        # Create and chunk documents
        documents = self.create_documents(pages_data)
        
        # Build vector database
        vectorstore = self.build_vector_db(documents)
        
        print("\n✅ Processing complete!")
        print(f"📍 Database location: {self.db_path}")
        
        return vectorstore
    
    def test_search(self, vectorstore: Chroma, query: str, k: int = 3):
        """Test the vector database with a sample query.
        
        Args:
            vectorstore: The Chroma vector store
            query: Test query
            k: Number of results to return
        """
        print(f"\n🔍 Testing search with query: '{query}'")
        print("-" * 50)
        
        results = vectorstore.similarity_search(query, k=k)
        
        for i, doc in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"Page: {doc.metadata.get('page', 'N/A')}")
            print(f"Content preview: {doc.page_content[:200]}...")
            print("-" * 50)


def main():
    """Main function."""
    load_dotenv()
    
    try:
        # Process the manual
        processor = RSCDSManualProcessor()
        vectorstore = processor.process()
        
        # Run some test searches
        print("\n" + "=" * 50)
        print("Running test searches...")
        print("=" * 50)
        
        test_queries = [
            "poussette formation",
            "allemande teaching points",
            "rights and lefts"
        ]
        
        for query in test_queries:
            processor.test_search(vectorstore, query, k=2)
        
        print("\n✅ All done! Vector database is ready for use.")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
