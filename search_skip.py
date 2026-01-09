#!/usr/bin/env python3
"""Search for skip change of step."""

import fitz  # PyMuPDF

pdf_path = "data/raw/rscds-manual.pdf"
doc = fitz.open(pdf_path)

print(f"Searching {len(doc)} pages for 'skip change'...")

matches = []
for page_num in range(len(doc)):
    page = doc[page_num]
    text = page.get_text().lower()
    
    if "skip change" in text:
        matches.append(page_num + 1)

print(f"\nFound 'skip change' on pages: {matches[:20]}")  # First 20 matches

# Show first match in detail
if matches:
    first_page = matches[0] - 1
    print(f"\n{'='*80}")
    print(f"FIRST MATCH - PAGE {first_page + 1}")
    print('='*80)
    print(doc[first_page].get_text())

doc.close()
