#!/usr/bin/env python3
"""Show pages 74-76 to see skip change of step structure."""

import fitz  # PyMuPDF

pdf_path = "data/raw/rscds-manual.pdf"
doc = fitz.open(pdf_path)

# Pages 74-76 (indices 73-75)
for i in range(73, 78):
    print(f"\n{'='*80}")
    print(f"PAGE {i+1}")
    print('='*80)
    print(doc[i].get_text())

doc.close()
