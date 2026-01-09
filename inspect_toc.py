#!/usr/bin/env python3
"""Inspect the RSCDS manual table of contents."""

import fitz  # PyMuPDF

pdf_path = "data/raw/rscds-manual.pdf"
doc = fitz.open(pdf_path)

print(f"📖 Total pages: {len(doc)}\n")

# Look at pages 1-10 to find table of contents
for i in range(min(10, len(doc))):
    page = doc[i]
    text = page.get_text()
    
    print(f"\n{'='*80}")
    print(f"PAGE {i+1}")
    print('='*80)
    
    # Check if this looks like a TOC page
    if "contents" in text.lower()[:200] or i < 5:
        print(text[:3000])  # Show more for TOC pages
    else:
        print(text[:800])  # Just preview for other pages

doc.close()
