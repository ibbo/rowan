#!/usr/bin/env python3
"""Show example of skip change of step section structure."""

import fitz  # PyMuPDF

pdf_path = "data/raw/rscds-manual.pdf"
doc = fitz.open(pdf_path)

print("Looking for 'Skip change of step' section...")

# Search for skip change of step
found = False
for page_num in range(len(doc)):
    page = doc[page_num]
    text = page.get_text()
    
    # Look for section 5.2.1 skip change of step
    if "5.2.1" in text and "Skip change" in text:
        print(f"\n✓ Found Skip change of step on page {page_num + 1}")
        print("="*80)
        
        # Show this page and next few pages
        for i in range(page_num, min(page_num + 4, len(doc))):
            page_text = doc[i].get_text()
            print(f"\n{'='*80}")
            print(f"PAGE {i+1}")
            print('='*80)
            print(page_text)
            
            # Stop if we hit the next major section
            if i > page_num and ("5.2.2" in page_text or "5.3" in page_text):
                break
        
        found = True
        break

if not found:
    print("Could not find Skip change of step section")

doc.close()
