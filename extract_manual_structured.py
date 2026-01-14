#!/usr/bin/env python3
"""
Extract RSCDS Manual PDF into structured JSON files.

This script parses the PDF using its hierarchical table of contents
and creates structured JSON files for precise lookup by the LLM.

Output:
- data/manual/index.json - Master lookup index
- data/manual/chapters/chapter_N_*.json - Per-chapter content
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

import fitz  # PyMuPDF


@dataclass
class Section:
    """Represents a section in the manual."""
    section_number: str
    title: str
    page: int
    content: str = ""
    aliases: List[str] = field(default_factory=list)
    teaching_points: List[str] = field(default_factory=list)
    subsections: Dict[str, 'Section'] = field(default_factory=dict)


class ManualExtractor:
    """Extract RSCDS manual into structured JSON format."""
    
    def __init__(
        self,
        pdf_path: str = "data/raw/rscds-manual.pdf",
        output_dir: str = "data/manual"
    ):
        self.pdf_path = Path(pdf_path)
        self.output_dir = Path(output_dir)
        self.chapters_dir = self.output_dir / "chapters"
        
        # Chapter names from TOC
        self.chapter_info = {
            "1": {"name": "History and Development", "slug": "history"},
            "2": {"name": "The RSCDS", "slug": "rscds"},
            "3": {"name": "The Scottish Country Dance", "slug": "dance_types"},
            "4": {"name": "Music in Teaching Dance", "slug": "music"},
            "5": {"name": "Steps", "slug": "steps"},
            "6": {"name": "Formations", "slug": "formations"},
            "7": {"name": "Notes for Dances", "slug": "book_notes"},
            "8": {"name": "Essential Teaching Skills", "slug": "teaching"},
        }
        
        # Patterns for extracting teaching points
        self.teaching_patterns = [
            r'\nPoints to observe\s*\n',
            r'\nTeaching points\s*\n',
            r'\nCommon mistakes\s*\n',
        ]
    
    def extract(self) -> Dict[str, Any]:
        """Run the full extraction pipeline."""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")
        
        print(f"📖 Opening {self.pdf_path}")
        doc = fitz.open(self.pdf_path)
        
        # Get TOC for structure
        toc = doc.get_toc()
        print(f"📑 Found {len(toc)} TOC entries")
        
        # Extract all page text
        page_texts = self._extract_page_texts(doc)
        
        # Build chapter structure from TOC
        chapters = self._build_chapter_structure(toc, page_texts, doc)
        
        doc.close()
        
        # Create output directories
        self.chapters_dir.mkdir(parents=True, exist_ok=True)
        
        # Write chapter files
        self._write_chapter_files(chapters)
        
        # Build and write index
        index = self._build_index(chapters)
        
        return index
    
    def _extract_page_texts(self, doc: fitz.Document) -> Dict[int, str]:
        """Extract text from all pages."""
        print("📄 Extracting page texts...")
        page_texts = {}
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            page_texts[page_num + 1] = text  # 1-indexed
        return page_texts
    
    def _build_chapter_structure(
        self,
        toc: List[Tuple[int, str, int]],
        page_texts: Dict[int, str],
        doc: fitz.Document
    ) -> Dict[str, Dict]:
        """Build chapter structure from TOC."""
        print("🏗️  Building chapter structure...")
        
        chapters = {}
        
        # Group TOC entries by chapter
        current_chapter = None
        chapter_sections = {}
        
        for level, title, page in toc:
            # Skip front matter
            if page < 12:
                continue
            
            # Detect chapter headers
            if "CHAPTER" in title:
                match = re.search(r'CHAPTER\s+(\d+)', title)
                if match:
                    current_chapter = match.group(1)
                    chapter_sections[current_chapter] = []
                continue
            
            # Skip non-chapter content (appendices, index)
            if "APPENDIX" in title or title == "INDEX":
                continue
            
            if current_chapter and current_chapter in self.chapter_info:
                chapter_sections.setdefault(current_chapter, []).append({
                    "level": level,
                    "title": title,
                    "page": page
                })
        
        # Process each chapter
        for chapter_num, sections in chapter_sections.items():
            if not sections:
                continue
                
            chapter_data = self._process_chapter(
                chapter_num, 
                sections, 
                page_texts,
                toc
            )
            chapters[chapter_num] = chapter_data
        
        return chapters
    
    def _process_chapter(
        self,
        chapter_num: str,
        sections: List[Dict],
        page_texts: Dict[int, str],
        toc: List[Tuple[int, str, int]]
    ) -> Dict:
        """Process a single chapter into structured format."""
        info = self.chapter_info.get(chapter_num, {})
        
        chapter = {
            "chapter": int(chapter_num),
            "name": info.get("name", f"Chapter {chapter_num}"),
            "sections": {}
        }
        
        # Create section lookup for content boundaries
        all_toc_pages = sorted(set(page for _, _, page in toc))
        
        for i, section in enumerate(sections):
            section_title = section["title"]
            section_page = section["page"]
            
            # Determine section number from title
            section_match = re.match(r'^(\d+(?:\.\d+)*)\s+(.+)$', section_title)
            if section_match:
                section_num = section_match.group(1)
                title_text = section_match.group(2).strip()
            else:
                # Non-numbered section (like BOOK 1, etc.)
                section_num = section_title.replace(" ", "_").lower()
                title_text = section_title
            
            # Get content boundaries
            next_page = None
            if i + 1 < len(sections):
                next_page = sections[i + 1]["page"]
            else:
                # Find next chapter or end
                for _, t, p in toc:
                    if p > section_page and ("CHAPTER" in t or "APPENDIX" in t):
                        next_page = p
                        break
            
            if next_page is None:
                next_page = max(page_texts.keys())
            
            # Extract content for this section
            content = self._extract_section_content(
                section_title, 
                section_page, 
                next_page,
                page_texts
            )
            
            # Extract teaching points if present
            teaching_points = self._extract_teaching_points(content)
            
            # Build section data
            section_data = {
                "title": title_text,
                "page": section_page,
                "content": content,
            }
            
            if teaching_points:
                section_data["teaching_points"] = teaching_points
            
            # Generate aliases
            aliases = self._generate_aliases(title_text)
            if aliases:
                section_data["aliases"] = aliases
            
            chapter["sections"][section_num] = section_data
        
        return chapter
    
    def _extract_section_content(
        self,
        section_title: str,
        start_page: int,
        end_page: int,
        page_texts: Dict[int, str]
    ) -> str:
        """Extract content for a section."""
        content_parts = []
        
        for page_num in range(start_page, min(end_page + 1, max(page_texts.keys()) + 1)):
            if page_num in page_texts:
                text = page_texts[page_num]
                
                # Clean up header/footer noise
                lines = text.split('\n')
                cleaned_lines = []
                for line in lines:
                    # Skip header lines (page numbers, edition info)
                    if re.match(r'^(Third edition|May 2013|\d{1,3}\s*$)', line.strip()):
                        continue
                    cleaned_lines.append(line)
                
                content_parts.append('\n'.join(cleaned_lines))
        
        full_content = '\n'.join(content_parts)
        
        # Try to isolate just this section's content
        # Look for section header pattern
        section_match = re.search(r'^(\d+(?:\.\d+)*)\s+(.+?)(?:\n|$)', section_title)
        if section_match:
            pattern = re.escape(section_match.group(1)) + r'\s+' + re.escape(section_match.group(2)[:30])
            match = re.search(pattern, full_content, re.IGNORECASE)
            if match:
                full_content = full_content[match.start():]
        
        # Trim to reasonable length (avoid including next sections)
        # This is approximate - we'll refine based on section number patterns
        next_section_match = re.search(r'\n(\d+\.\d+(?:\.\d+)?)\s+[A-Z]', full_content[200:])
        if next_section_match:
            full_content = full_content[:200 + next_section_match.start()]
        
        return full_content.strip()
    
    def _extract_teaching_points(self, content: str) -> List[str]:
        """Extract teaching points from content."""
        teaching_points = []
        
        for pattern in self.teaching_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                # Get text after the header
                remainder = content[match.end():]
                
                # Extract numbered points
                points = re.findall(r'^\s*(\d+)\.\s*(.+?)(?=^\s*\d+\.|$)', 
                                   remainder, re.MULTILINE | re.DOTALL)
                for num, point_text in points:
                    cleaned = ' '.join(point_text.split())
                    if cleaned:
                        teaching_points.append(cleaned)
                break
        
        return teaching_points
    
    def _generate_aliases(self, title: str) -> List[str]:
        """Generate common aliases for a section title.
        
        Handles:
        - Number variations (three/3, two/2, four/4)
        - Word order variations ("X for N couples" -> "N couple X")
        - Common abbreviations
        - Hyphenation variations
        """
        aliases = []
        title_lower = title.lower()
        
        # Number word to digit mapping
        num_words = {
            'one': '1', 'two': '2', 'three': '3', 'four': '4', 
            'five': '5', 'six': '6', 'eight': '8'
        }
        num_digits = {v: k for k, v in num_words.items()}
        
        # Pattern: "X for N couples" -> "N couple X"
        # e.g., "knot for three couples" -> "3 couple knot", "three couple knot"
        # Also handles "The X for N couples"
        match = re.match(r'^(?:the\s+)?(.+?)\s+for\s+(one|two|three|four|five|six)\s+couples?$', title_lower)
        if match:
            formation_name = match.group(1).strip()
            # Strip leading "the" from formation name if present
            formation_name = re.sub(r'^the\s+', '', formation_name)
            num_word = match.group(2)
            num_digit = num_words.get(num_word, num_word)
            
            # Add colloquial variations
            aliases.append(f"{num_digit} couple {formation_name}")
            aliases.append(f"{num_word} couple {formation_name}")
            aliases.append(f"{num_digit}-couple {formation_name}")
            # Also the base formation name alone for simple lookups
            if formation_name not in ['poussette', 'promenade']:  # Avoid overly generic
                aliases.append(formation_name)
        
        # Pattern: "X for N couples in Y" variations
        match = re.match(r'^(.+?)\s+for\s+(one|two|three|four)\s+couples?\s+(.+)$', title_lower)
        if match:
            formation_name = match.group(1).strip()
            num_word = match.group(2)
            suffix = match.group(3).strip()
            num_digit = num_words.get(num_word, num_word)
            aliases.append(f"{num_digit} couple {formation_name} {suffix}")
        
        # Pattern: "reel of three/four" variations
        match = re.match(r'^reels?\s+of\s+(three|four|3|4)(.*)$', title_lower)
        if match:
            num = match.group(1)
            suffix = match.group(2).strip()
            if num in num_words:
                aliases.append(f"reel of {num_words[num]}{' ' + suffix if suffix else ''}")
            if num in num_digits:
                aliases.append(f"reel of {num_digits[num]}{' ' + suffix if suffix else ''}")
            # Common colloquial: "reel of 3" 
            if num == 'three':
                aliases.extend(["reel of 3", "3 reel"])
            elif num == 'four':
                aliases.extend(["reel of 4", "4 reel"])
        
        # Specific common aliases
        if "skip change of step" in title_lower:
            aliases.append("skip change")
        elif "pas de basque" in title_lower:
            aliases.extend(["pas-de-basque", "pdb"])
        elif "rights and lefts" in title_lower:
            aliases.extend(["rights & lefts", "rights n lefts"])
        elif "ladies' chain" in title_lower or "ladies' chain" in title_lower:
            aliases.extend(["ladies chain", "lady's chain"])
        elif "men's chain" in title_lower or "men's chain" in title_lower:
            aliases.extend(["mens chain", "men chain"])
        elif "figure of eight" in title_lower:
            aliases.extend(["figure 8", "figure-of-eight"])
        elif "hands across" in title_lower:
            aliases.append("hands-across")
        elif "hands round" in title_lower:
            aliases.append("hands-round")
        elif "set and link" in title_lower:
            aliases.append("set-and-link")
        elif "set and turn" in title_lower:
            aliases.append("set-and-turn")
        elif "lead down the middle" in title_lower:
            aliases.extend(["lead down", "down the middle"])
        elif "petronella" in title_lower:
            aliases.append("petronella")
        elif "allemande" in title_lower:
            aliases.append("allemande")
        elif "poussette" in title_lower and "polka" not in title_lower:
            # Add base "poussette" for the main poussette sections
            if "for two couples" in title_lower:
                aliases.extend(["poussette", "2 couple poussette"])
        elif "half" in title_lower:
            # "half X" -> common abbreviated forms
            base = title_lower.replace("half ", "").strip()
            aliases.append(f"1/2 {base}")
        
        # Remove duplicates and empty strings
        aliases = list(set(a.strip() for a in aliases if a.strip()))
        
        return aliases
    
    def _write_chapter_files(self, chapters: Dict[str, Dict]) -> None:
        """Write individual chapter JSON files."""
        print("💾 Writing chapter files...")
        
        for chapter_num, chapter_data in chapters.items():
            info = self.chapter_info.get(chapter_num, {})
            slug = info.get("slug", f"chapter_{chapter_num}")
            filename = f"chapter_{chapter_num}_{slug}.json"
            filepath = self.chapters_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(chapter_data, f, indent=2, ensure_ascii=False)
            
            section_count = len(chapter_data.get("sections", {}))
            print(f"   ✅ {filename} ({section_count} sections)")
    
    def _build_index(self, chapters: Dict[str, Dict]) -> Dict:
        """Build master index for fast lookups."""
        print("📇 Building master index...")
        
        index = {
            "version": "1.0",
            "source": str(self.pdf_path),
            "chapters": {},
            "sections": {},  # name/alias -> section_number + chapter
        }
        
        for chapter_num, chapter_data in chapters.items():
            info = self.chapter_info.get(chapter_num, {})
            slug = info.get("slug", f"chapter_{chapter_num}")
            
            index["chapters"][chapter_num] = {
                "name": chapter_data["name"],
                "file": f"chapter_{chapter_num}_{slug}.json",
                "section_count": len(chapter_data.get("sections", {}))
            }
            
            # Add section lookups
            for section_num, section_data in chapter_data.get("sections", {}).items():
                title = section_data["title"].lower()
                
                # Add by title
                index["sections"][title] = {
                    "section": section_num,
                    "chapter": chapter_num,
                    "page": section_data.get("page", 0)
                }
                
                # Add by aliases
                for alias in section_data.get("aliases", []):
                    index["sections"][alias.lower()] = {
                        "section": section_num,
                        "chapter": chapter_num,
                        "page": section_data.get("page", 0)
                    }
        
        # Write index
        index_path = self.output_dir / "index.json"
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        
        print(f"   ✅ index.json ({len(index['sections'])} entries)")
        
        return index


def main():
    """Main entry point."""
    print("🏴󠁧󠁢󠁳󠁣󠁴󠁿 RSCDS Manual Structured Extraction")
    print("=" * 50)
    
    try:
        extractor = ManualExtractor()
        index = extractor.extract()
        
        print()
        print("✅ Extraction complete!")
        print(f"   Chapters: {len(index['chapters'])}")
        print(f"   Indexed sections: {len(index['sections'])}")
        print(f"   Output: data/manual/")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
