#!/usr/bin/env python3
"""
Process RSCDS Manual PDF with structure-aware chunking.

This version:
1. Extracts text from PDF (no vision model needed)
2. Parses hierarchical structure using section numbers
3. Creates semantic chunks preserving formation/step boundaries
4. Adds rich metadata for precise retrieval
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from dotenv import load_dotenv
import fitz  # PyMuPDF
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document


@dataclass
class Section:
    """Represents a section in the manual."""
    section_number: str
    title: str
    content: str
    page_start: int
    page_end: int
    subsections: List['Section']
    parent_section: Optional[str] = None


class StructuredManualProcessor:
    """Process RSCDS manual preserving hierarchical structure."""
    
    def __init__(
        self,
        pdf_path: str = "data/raw/rscds-manual.pdf",
        db_path: str = "data/vector_db/rscds_manual_structured"
    ):
        """Initialize the processor."""
        self.pdf_path = Path(pdf_path)
        self.db_path = Path(db_path)
        
        # Check for OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
        
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        
        # Section number patterns
        self.section_pattern = re.compile(r'^(\d+\.\d+(?:\.\d+)?)\s+(.+?)(?:\s{2,}|\n|$)', re.MULTILINE)
        
        # Chapter mapping (from TOC analysis)
        self.chapter_names = {
            "1": "History and Development",
            "2": "The RSCDS",
            "3": "The Scottish Country Dance",
            "4": "Music in Teaching Dance",
            "5": "Steps",
            "6": "Formations",
            "7": "Books",
            "8": "Teaching"
        }
    
    def extract_full_text(self, skip_toc_pages: int = 12) -> Dict[int, str]:
        """Extract text from all pages, skipping TOC."""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")
        
        print(f"📖 Extracting text from {self.pdf_path} (skipping TOC pages 1-{skip_toc_pages})")
        doc = fitz.open(self.pdf_path)
        
        page_texts = {}
        for page_num in range(skip_toc_pages, len(doc)):  # Skip TOC
            page = doc[page_num]
            text = page.get_text()
            page_texts[page_num + 1] = text  # 1-indexed pages
        
        doc.close()
        print(f"✅ Extracted {len(page_texts)} pages (skipped TOC)")
        return page_texts
    
    def parse_sections(self, page_texts: Dict[int, str]) -> List[Section]:
        """Parse the manual into hierarchical sections."""
        print("🔍 Parsing hierarchical structure...")
        
        sections = []
        current_content = []
        current_section = None
        current_page = 1
        
        # Combine all text with page markers
        full_text = ""
        page_map = {}  # char position -> page number
        char_pos = 0
        
        for page_num in sorted(page_texts.keys()):
            text = page_texts[page_num]
            page_map[char_pos] = page_num
            full_text += text
            char_pos += len(text)
        
        # Find all section headers
        matches = list(self.section_pattern.finditer(full_text))
        
        print(f"   Found {len(matches)} section headers")
        
        for i, match in enumerate(matches):
            section_num = match.group(1)
            section_title = match.group(2).strip()
            start_pos = match.start()
            
            # Find page number for this section
            page_num = max([p for p in page_map.keys() if p <= start_pos], default=1)
            page_num = page_map.get(page_num, 1)
            
            # Get content until next section
            if i < len(matches) - 1:
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(full_text)
            
            content = full_text[start_pos:end_pos].strip()
            
            # Determine parent section
            parent = self._get_parent_section(section_num)
            
            section = Section(
                section_number=section_num,
                title=section_title,
                content=content,
                page_start=page_num,
                page_end=page_num,  # Will update later if spans multiple pages
                subsections=[],
                parent_section=parent
            )
            
            sections.append(section)
        
        # Build hierarchy
        sections = self._build_hierarchy(sections)
        
        print(f"✅ Parsed {len(sections)} top-level sections")
        return sections
    
    def _get_parent_section(self, section_num: str) -> Optional[str]:
        """Determine parent section number."""
        parts = section_num.split('.')
        if len(parts) <= 2:
            return None  # Top-level section
        # Parent is everything except last part
        return '.'.join(parts[:-1])
    
    def _build_hierarchy(self, sections: List[Section]) -> List[Section]:
        """Build parent-child relationships."""
        # Create lookup dict
        section_dict = {s.section_number: s for s in sections}
        
        # Top-level sections only
        top_level = []
        
        for section in sections:
            if section.parent_section:
                parent = section_dict.get(section.parent_section)
                if parent:
                    parent.subsections.append(section)
            else:
                top_level.append(section)
        
        return top_level
    
    def create_documents(self, sections: List[Section]) -> List[Document]:
        """Create LangChain documents from sections."""
        print("📝 Creating structured documents...")
        
        documents = []
        
        def process_section(section: Section, depth: int = 0):
            """Recursively process sections into documents."""
            
            # Extract chapter info
            chapter_num = section.section_number.split('.')[0]
            chapter_name = self.chapter_names.get(chapter_num, f"Chapter {chapter_num}")
            
            # Detect section type and formation name
            section_type, formation_name = self._classify_section(section)
            
            # Split section if it contains "Points to observe" or similar
            subsection_chunks = self._split_teaching_subsections(section.content, section)
            
            if subsection_chunks:
                # Create separate documents for each subsection
                for chunk_content, chunk_type in subsection_chunks:
                    metadata = {
                        "section_number": section.section_number,
                        "title": section.title,
                        "chapter": chapter_num,
                        "chapter_name": chapter_name,
                        "section_type": chunk_type,
                        "page": section.page_start,
                        "parent_section": section.parent_section or "",
                        "formation_name": formation_name,
                        "hierarchy_depth": depth
                    }
                    
                    doc = Document(
                        page_content=chunk_content,
                        metadata=metadata
                    )
                    documents.append(doc)
            else:
                # Create single document for whole section
                metadata = {
                    "section_number": section.section_number,
                    "title": section.title,
                    "chapter": chapter_num,
                    "chapter_name": chapter_name,
                    "section_type": section_type,
                    "page": section.page_start,
                    "parent_section": section.parent_section or "",
                    "formation_name": formation_name,
                    "hierarchy_depth": depth
                }
                
                doc = Document(
                    page_content=section.content,
                    metadata=metadata
                )
                documents.append(doc)
            
            # Process subsections
            for subsection in section.subsections:
                process_section(subsection, depth + 1)
        
        # Process all top-level sections
        for section in sections:
            process_section(section)
        
        print(f"✅ Created {len(documents)} documents")
        return documents
    
    def _split_teaching_subsections(self, content: str, section: Section) -> Optional[List[Tuple[str, str]]]:
        """Split content into teaching subsections if they exist."""
        # Patterns for teaching subsections
        patterns = [
            (r'\nPoints to observe\s*\n', 'points_to_observe'),
            (r'\nTeaching points\s*\n', 'teaching_points'),
            (r'\nCommon mistakes\s*\n', 'common_mistakes'),
            (r'\nVariations?\s*\n', 'variation'),
        ]
        
        # Check if any patterns exist
        split_positions = []
        for pattern, subsection_type in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                split_positions.append((match.start(), match.group().strip(), subsection_type))
        
        if not split_positions:
            return None
        
        # Sort by position
        split_positions.sort(key=lambda x: x[0])
        
        # Split content into chunks
        chunks = []
        
        # Main description (before first split)
        if split_positions:
            main_content = content[:split_positions[0][0]].strip()
            if main_content:
                chunks.append((main_content, 'main_description'))
            
            # Each subsection
            for i, (pos, marker, subsec_type) in enumerate(split_positions):
                # Get content from this marker to next marker (or end)
                if i < len(split_positions) - 1:
                    next_pos = split_positions[i + 1][0]
                    subsec_content = content[pos:next_pos].strip()
                else:
                    subsec_content = content[pos:].strip()
                
                if subsec_content:
                    chunks.append((subsec_content, subsec_type))
        
        return chunks if len(chunks) > 1 else None
    
    def _classify_section(self, section: Section) -> Tuple[str, str]:
        """Classify section type and extract formation name."""
        title_lower = section.title.lower()
        content_lower = section.content.lower()
        
        # Determine formation/step name (title without section number)
        formation_name = section.title.lower().strip()
        
        # Detect section type
        if "points to observe" in title_lower or "points to observe" in content_lower[:200]:
            section_type = "points_to_observe"
        elif "teaching points" in title_lower or "teaching points" in content_lower[:200]:
            section_type = "teaching_points"
        elif any(word in title_lower for word in ["variation", "variant", "alternative"]):
            section_type = "variation"
        elif section.parent_section:
            section_type = "subsection"
        else:
            section_type = "main_description"
        
        return section_type, formation_name
    
    def build_vector_db(self, documents: List[Document]) -> Chroma:
        """Build ChromaDB vector database."""
        print(f"🔨 Building vector database at {self.db_path}...")
        
        # Create directory
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Delete existing database
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
        """Run the full processing pipeline."""
        print("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Processing RSCDS Manual with Structure Preservation")
        print("=" * 70)
        
        # Extract text
        page_texts = self.extract_full_text()
        
        # Parse sections
        sections = self.parse_sections(page_texts)
        
        # Create documents
        documents = self.create_documents(sections)
        
        # Build vector database
        vectorstore = self.build_vector_db(documents)
        
        print("\n✅ Processing complete!")
        print(f"📍 Database location: {self.db_path}")
        
        return vectorstore
    
    def test_search(self, vectorstore: Chroma, query: str, k: int = 3):
        """Test the vector database."""
        print(f"\n🔍 Testing: '{query}'")
        print("-" * 70)
        
        results = vectorstore.similarity_search(query, k=k)
        
        for i, doc in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"  Section: {doc.metadata.get('section_number')} - {doc.metadata.get('title')}")
            print(f"  Type: {doc.metadata.get('section_type')}")
            print(f"  Formation: {doc.metadata.get('formation_name')}")
            print(f"  Page: {doc.metadata.get('page')}")
            print(f"  Content: {doc.page_content[:200]}...")
            print("-" * 70)


def main():
    """Main function."""
    load_dotenv()
    
    try:
        processor = StructuredManualProcessor()
        vectorstore = processor.process()
        
        # Test searches
        print("\n" + "=" * 70)
        print("Running test searches...")
        print("=" * 70)
        
        test_queries = [
            "skip change of step",
            "how to teach skip change of step",
            "poussette teaching points",
            "pas de basque points to observe"
        ]
        
        for query in test_queries:
            processor.test_search(vectorstore, query, k=3)
        
        print("\n✅ All done! Structured database is ready.")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
