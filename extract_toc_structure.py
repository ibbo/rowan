#!/usr/bin/env python3
"""Extract the full table of contents structure from RSCDS manual."""

import fitz  # PyMuPDF
import re

pdf_path = "data/raw/rscds-manual.pdf"
doc = fitz.open(pdf_path)

print(f"📖 Total pages: {len(doc)}\n")

# Extract pages 3-12 which should contain the full TOC
toc_text = ""
for i in range(2, 12):  # Pages 3-12
    page = doc[i]
    toc_text += page.get_text()

print("="*80)
print("TABLE OF CONTENTS STRUCTURE")
print("="*80)

# Print the TOC
lines = toc_text.split('\n')
for line in lines:
    # Only print lines that look like TOC entries (have section numbers or CHAPTER)
    if re.search(r'^\d+\.\d+|^CHAPTER|^\d+\.\d+\.\d+', line.strip()) or \
       ('.' * 10 in line and re.search(r'\d+\s*$', line)):
        print(line)

doc.close()

print("\n" + "="*80)
print("Now let's look at an actual formation section (skip change of step)")
print("="*80)

# Re-open to find skip change of step
doc = fitz.open(pdf_path)

# Search for "skip change of step" and show that section
for page_num in range(len(doc)):
    page = doc[page_num]
    text = page.get_text()
    
    # Look for the section heading
    if "5.2.1" in text and "Skip change of step" in text:
        print(f"\nFound on page {page_num + 1}:")
        print("-" * 80)
        # Show this page and next 2 pages to see full structure
        for i in range(page_num, min(page_num + 3, len(doc))):
            print(f"\n--- PAGE {i+1} ---")
            print(doc[i].get_text()[:2500])
        break

doc.close()
