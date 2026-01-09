#!/usr/bin/env python3
"""Inspect the RSCDS manual PDF structure."""

import fitz  # PyMuPDF

pdf_path = "data/raw/rscds-manual.pdf"
doc = fitz.open(pdf_path)

print(f"📖 Total pages: {len(doc)}\n")
print("=" * 80)

# Extract first 20 pages to see table of contents and structure
for i in range(min(20, len(doc))):
    page = doc[i]
    text = page.get_text()
    
    print(f"\n{'='*80}")
    print(f"PAGE {i+1}")
    print('='*80)
    print(text[:2000])  # First 2000 chars
    
    if i >= 19:  # Stop after examining enough pages
        break

doc.close()
