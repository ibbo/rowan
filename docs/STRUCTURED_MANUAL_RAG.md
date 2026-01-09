# Structured RSCDS Manual RAG System

## Overview

This document describes the **structure-preserving RAG implementation** for the RSCDS manual, which solves the cross-contamination and relevance issues experienced with the previous page-by-page chunking approach.

## The Problem

### Previous Approach (Page-by-Page with Vision Model)

**Method:**
- Used GPT-4o vision model to describe each page
- Chunked by character count (2000 chars, 400 overlap)
- No awareness of document structure

**Issues:**
1. ❌ **Cross-contamination**: "Skip change of step" queries would return content about "pas de basque" and "slip step" from the same page
2. ❌ **Buried teaching points**: The "Points to observe" sections were embedded in large 2400+ character chunks
3. ❌ **Poor precision**: LLM couldn't distinguish between main description and teaching guidance
4. ❌ **High cost**: Vision model processing was expensive (~$0.50+ per manual)

## The Solution

### Structure-Aware Text Extraction

**Method:**
- Pure text extraction using PyMuPDF (fast, accurate)
- Parse hierarchical structure using section numbers (e.g., `5.4.1`, `6.21.3`)
- Split "Points to observe" and similar subsections into separate chunks
- Rich metadata for precise filtering

**Benefits:**
1. ✅ **No cross-contamination**: Each formation/step is a separate searchable unit
2. ✅ **Teaching-focused chunks**: "Points to observe" are standalone, highly relevant chunks
3. ✅ **Better precision**: Section types allow filtering (e.g., `section_type: "points_to_observe"`)
4. ✅ **Fast & cheap**: Text extraction only, no vision model needed

## Implementation Details

### Architecture

```
┌─────────────────────────┐
│  RSCDS Manual PDF       │
│  (253 pages)            │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Structure Parser       │
│  - Text extraction      │
│  - Section detection    │
│  - Skip TOC pages       │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Subsection Splitter    │
│  - "Points to observe"  │
│  - "Teaching points"    │
│  - "Variations"         │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Document Creator       │
│  - Rich metadata        │
│  - Hierarchy tracking   │
│  - ~450 semantic chunks │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  ChromaDB Vector DB     │
│  (Structure-Aware)      │
└─────────────────────────┘
```

### Key Components

#### 1. Structure Parser (`process_manual_structured.py`)

Parses the RSCDS manual preserving its hierarchical organization:

**Features:**
- Detects section boundaries using regex: `^\d+\.\d+(\.\d+)?`
- Skips table of contents pages (1-12)
- Builds parent-child relationships
- Tracks hierarchy depth

**Section Detection:**
```python
section_pattern = re.compile(r'^(\d+\.\d+(?:\.\d+)?)\s+(.+?)(?:\s{2,}|\n|$)', re.MULTILINE)
```

#### 2. Subsection Splitter

Splits sections containing teaching guidance into separate chunks:

**Patterns Detected:**
- `Points to observe` → `section_type: "points_to_observe"`
- `Teaching points` → `section_type: "teaching_points"`
- `Common mistakes` → `section_type: "common_mistakes"`
- `Variations` → `section_type: "variation"`

**Example Split:**

Original section (2406 chars):
```
5.4.1 Skip change of step
[main description]
Points to observe
1. The hop at the beginning...
2. The fully extended leg...
```

Becomes TWO chunks:
1. **Main Description** (714 chars) - `section_type: "main_description"`
2. **Points to Observe** (1690 chars) - `section_type: "points_to_observe"`

#### 3. Metadata Structure

Each chunk includes rich metadata:

```python
{
  "section_number": "5.4.1",
  "title": "Skip change of step",
  "chapter": "5",
  "chapter_name": "Steps",
  "section_type": "points_to_observe",  # 🎯 KEY for teaching queries
  "page": 74,
  "parent_section": "5.4",
  "formation_name": "skip change of step",
  "hierarchy_depth": 2
}
```

#### 4. Enhanced Search Tool

Updated `search_manual` in `dance_tools.py`:

**Features:**
- Automatically uses structured database if available
- Displays section types in results: `**[Points To Observe]**`
- Shows section numbers and titles
- Maintains backward compatibility with older databases

**Display Format:**
```
**Section 2 (Page 74)** - 5.4.1 Skip change of step **[Points To Observe]**
Points to observe
1. The hop at the beginning must be very positive...
```

## Results & Validation

### Test Results

**Query: "how to teach skip change of step"**

**Old System:**
- Returned 2400+ char chunk with everything mixed together
- Teaching points buried in middle of content
- Often included nearby formations (pas de basque, slip step)

**New System:**
- Returns 1690 char "Points to Observe" chunk
- ✅ Section 2: **5.4.1 Skip change of step [Points To Observe]**
- ✅ Clean, focused teaching guidance
- ✅ No contamination from other formations

### Performance Comparison

| Metric | Old (Vision) | New (Structured) |
|--------|-------------|------------------|
| Processing time | ~45 min | ~15 sec |
| Processing cost | ~$0.50 | ~$0.01 |
| Total chunks | 652 | ~450 |
| Avg chunk size | 1000 chars | Variable (semantic) |
| Teaching point precision | Low | High ✅ |
| Cross-contamination | Yes ❌ | No ✅ |

## Usage

### Building the Database

```bash
# Build structure-aware database
uv run process_manual_structured.py

# Result: data/vector_db/rscds_manual_structured/
```

### Testing

```bash
# Run integration tests
uv run test_structured_manual_integration.py

# Run detailed search tests
uv run test_structured_search.py
```

### Using the Tool

The `search_manual` tool automatically uses the structured database:

```python
from dance_tools import search_manual

# Query for teaching guidance
result = await search_manual.ainvoke({
    "query": "how to teach skip change of step",
    "num_results": 3
})

# Returns "Points to Observe" section with teaching guidance
```

## Technical Details

### Section Number Patterns

The manual uses hierarchical section numbering:

- **Chapter level**: `5` (Steps), `6` (Formations)
- **Section level**: `5.4` (Reel and jig steps)
- **Formation level**: `5.4.1` (Skip change of step)
- **Variant level**: `6.21.1` (Poussette for two couples)

### Chunking Strategy

**Principles:**
1. **Semantic boundaries**: Split at section headings, not arbitrary character counts
2. **Complete context**: Keep full descriptions intact
3. **Teaching focus**: Separate teaching subsections for high precision
4. **Hierarchy preservation**: Maintain parent-child relationships

**Chunk Sizes:**
- Subsections (e.g., "Points to observe"): 200-2000 chars
- Full sections: 500-3000 chars
- No arbitrary splits mid-sentence

### Database Statistics

```
Total documents: ~450 semantic chunks
Chapter 5 (Steps): ~85 chunks
Chapter 6 (Formations): ~310 chunks
Section types:
  - main_description: ~280
  - points_to_observe: ~45
  - subsection: ~100
  - teaching_points: ~15
  - variation: ~10
```

## Files Created/Modified

### New Files
- `process_manual_structured.py` - Structure-aware processor
- `test_structured_search.py` - Search validation tests
- `test_structured_manual_integration.py` - End-to-end tests
- `docs/STRUCTURED_MANUAL_RAG.md` - This documentation

### Modified Files
- `dance_tools.py` - Updated `_load_manual_vectorstore()` to use structured DB
- `dance_tools.py` - Enhanced `_format_manual_results()` to show section types

### Database Location
- `data/vector_db/rscds_manual_structured/` - New structured database (preferred)
- `data/vector_db/rscds_manual_enriched/` - Old enriched DB (fallback)
- `data/vector_db/rscds_manual/` - Original DB (fallback)

## Maintenance

### Updating the Manual

If the RSCDS manual is updated:

1. Place new PDF at `data/raw/rscds-manual.pdf`
2. Rebuild database: `uv run process_manual_structured.py`
3. Validate: `uv run test_structured_manual_integration.py`

### Rebuilding from Scratch

```bash
# Remove old structured database
rm -rf data/vector_db/rscds_manual_structured/

# Rebuild
uv run process_manual_structured.py

# Takes ~15 seconds, costs ~$0.01 in embedding fees
```

## Future Enhancements

Potential improvements:

- [ ] Add filtering by `section_type` in search queries
- [ ] Extract and preserve table structures (bar counts, step descriptions)
- [ ] Cross-reference formations mentioned in descriptions
- [ ] Add support for dance diagrams (if needed)
- [ ] Build hierarchy-aware search (parent → child navigation)

## Conclusion

The structure-aware RAG system successfully solves the cross-contamination issue by:

1. **Preserving document structure** - Uses section numbers as natural boundaries
2. **Separating teaching content** - "Points to observe" are standalone, searchable units
3. **Rich metadata** - Enables precise filtering and better LLM understanding
4. **Cost efficiency** - Pure text extraction, no expensive vision model

**Result:** "How to teach skip change of step" now returns focused, relevant teaching guidance without contamination from adjacent formations. ✅

---

*Last updated: 2025-01-23*
