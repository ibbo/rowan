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
import base64
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Optional, Generator

from dotenv import load_dotenv
from openai import OpenAI
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
        chunk_size: int = 2000,  # Increased for richer content
        chunk_overlap: int = 400,
        vision_model: str = "gpt-4o"
    ):
        """Initialize the processor.
        
        Args:
            pdf_path: Path to the RSCDS manual PDF
            db_path: Path to store the vector database
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            vision_model: The multimodal model to use for analysis
        """
        self.pdf_path = Path(pdf_path)
        self.db_path = Path(db_path)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.vision_model = vision_model
        
        # Check for OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OpenAI API key not found. Please set OPENAI_API_KEY environment variable.\n"
                "Example: export OPENAI_API_KEY='your-key-here'"
            )
        
        # Initialize OpenAI client
        self.openai_client = OpenAI()

        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small"
        )
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n\n", "\n\n", "\n", ". ", " ", ""]
        )
    
    def process_pages_multimodally(
        self,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None
    ) -> Generator[Dict[str, any], None, None]:
        """
        Extracts images and text from each page of a PDF and generates
        a multimodal description using a vision model.

        Args:
            start_page: Optional page number to start processing from.
            end_page: Optional page number to stop processing at.

        Yields:
            A dictionary for each page with page number, source, and generated description.
        """
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")

        print(f"📖 Opening PDF: {self.pdf_path}")
        doc = fitz.open(self.pdf_path)

        # Determine page range
        start_idx = (start_page - 1) if start_page else 0
        end_idx = end_page if end_page else len(doc)
        
        print(f"🧠 Processing pages {start_idx + 1} to {end_idx} using {self.vision_model}...")

        for page_num in range(start_idx, end_idx):
            page = doc.load_page(page_num)

            # Render page to an image
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")

            # Generate description with vision model
            try:
                print(f"  - Analyzing page {page_num + 1}...")
                response = self.openai_client.chat.completions.create(
                    model=self.vision_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an expert in Scottish Country Dancing. "
                                "Your task is to provide a detailed, comprehensive description of the provided page from the RSCDS manual. "
                                "Transcribe all text content accurately. "
                                "Describe any figures, diagrams, or images in meticulous detail, explaining their meaning and context within the dance. "
                                "Preserve the structure of the original content using Markdown. "
                                "Ensure the final output is a complete and accurate representation of the page's information."
                            )
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Describe this page from the RSCDS manual."},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{img_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=4000,
                )
                description = response.choices[0].message.content

                yield {
                    "page_number": page_num + 1,
                    "source": str(self.pdf_path),
                    "text": description
                }

            except Exception as e:
                print(f"❗️ Error processing page {page_num + 1}: {e}")

        print("✅ Finished multimodal processing.")
    
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
    
    def process(self, start_page: Optional[int] = None, end_page: Optional[int] = None) -> Chroma:
        """Run the full processing pipeline.
        
        Args:
            start_page: Optional page to start processing from.
            end_page: Optional page to end processing at.

        Returns:
            Chroma vector store
        """
        print("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Processing RSCDS Manual for RAG")
        print("=" * 50)
        
        # Process pages multimodally
        pages_generator = self.process_pages_multimodally(start_page=start_page, end_page=end_page)
        
        # Create and chunk documents
        documents = self.create_documents(list(pages_generator))
        
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
    import argparse
    parser = argparse.ArgumentParser(description="Process RSCDS Manual PDF into a vector database.")
    parser.add_argument("--start-page", type=int, help="Page to start processing from.")
    parser.add_argument("--end-page", type=int, help="Page to end processing at.")
    parser.add_argument("--query", type=str, help="Run a test query after processing.")
    args = parser.parse_args()

    load_dotenv()
    
    try:
        # Process the manual
        processor = RSCDSManualProcessor()
        vectorstore = processor.process(start_page=args.start_page, end_page=args.end_page)
        
        # Run test searches
        print("\n" + "=" * 50)
        print("Running test searches...")
        print("=" * 50)
        
        test_queries = [
            "poussette formation",
            "allemande teaching points",
            "rights and lefts"
        ]
        
        if args.query:
            test_queries.append(args.query)

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
