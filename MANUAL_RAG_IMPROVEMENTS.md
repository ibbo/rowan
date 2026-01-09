# RSCDS Manual RAG Improvements

## Problem Statement

The original RAG implementation for the RSCDS manual had accuracy issues:

1. **Formation Contamination**: When asking about "skip change", results included mixed content about "pas-de-basque" from the same page
2. **Pagination Issues**: "Rights and lefts" queries included content from "reels of three in tandem" that spilled onto the same page
3. **No Semantic Boundaries**: Generic text chunking (2000 chars) ignored the manual's hierarchical structure (formations, sub-sections)

## Solution Implemented

A multi-layered approach that **preserves your expensive vision-based embeddings** while adding semantic intelligence:

### 1. Metadata Enrichment (`enrich_manual_metadata.py`)

**What it does:**
- Analyzes each existing chunk using GPT-4o-mini (cost-efficient)
- Extracts semantic metadata:
  - `formations_mentioned`: List of all formations discussed in chunk
  - `primary_formation`: The main formation this section is about
  - `section_type`: Type of content (description, teaching_points, technique, diagram, example, transition, etc.)
  - `topics`: Topical tags (footwork, hand_hold, timing, positioning, etc.)
- Creates enriched database at `data/vector_db/rscds_manual_enriched`
- **Preserves original embeddings** - no re-embedding needed
- Creates backup of original database automatically

**Usage:**
```bash
# Run enrichment (takes ~10 minutes for 386 chunks)
uv run enrich_manual_metadata.py

# Validate results only
uv run enrich_manual_metadata.py --validate-only
```

**Output:**
- `data/vector_db/rscds_manual_enriched/` - Enhanced vector database
- `data/vector_db/rscds_manual_backup/` - Backup of original

### 2. Smart Manual Search (`dance_tools.py` updates)

**Enhanced `search_manual` tool with:**

#### Formation Detection
- Automatically extracts formation names from queries
- Recognizes 30+ formation patterns:
  - Multi-word: "skip change of step", "rights and lefts", "reels of three"
  - Single-word: "poussette", "allemande", "promenade"
- Normalizes variations (e.g., "pas-de-basque" → "pas de basque")

#### Metadata Filtering
- Filters chunks by `primary_formation` when formation is detected
- Falls back to full search if insufficient filtered results

#### Smart Re-ranking
- **+2.0 score**: Chunk's primary formation matches query formation
- **+1.0 score**: Formation mentioned in chunk
- **-0.5 score**: Chunk contains >2 other formations (indicates mixed content)
- **+0.5 score**: Section type is teaching_points, description, or technique
- **-0.3 score**: Section type is example (less directly useful)

#### Enhanced Formatting
- Shows detected formation: "🎯 *Focused on formation: poussette*"
- Displays section type: "[Teaching Points]", "[Description]", "[Technique]"
- Includes primary formation in headers

### 3. Backward Compatibility

The system automatically:
- Tries to load enriched database first
- Falls back to original database if enriched version unavailable
- Works with both enriched and non-enriched databases
- No changes required to agent or gradio app code

## Results

### Test Results (`test_improved_manual_rag.py`)

All 4 problematic queries now show significant improvements:

#### ✅ Skip Change
- **Detection**: Formation correctly identified
- **Results**: Focused on skip change content
- **Note**: Some chunks mention "pas-de-basque" in context of transitions (e.g., "Skip Change to Pas de Basque"), which is legitimate teaching content
- **Metadata**: Section types labeled as [Description], [Technique]

#### ✅ Rights and Lefts  
- **Detection**: Formation correctly identified
- **Results**: All 3 chunks focused on rights and lefts
- **No contamination**: No "reels of three in tandem" from adjacent pages
- **Note**: "Pelorus Jack" appears as a legitimate example dance mentioned in the rights and lefts section itself
- **Metadata**: Primary formation tagged correctly

#### ✅ Pas-de-Basque
- **Detection**: Formation correctly identified
- **Results**: All chunks focused on pas-de-basque
- **No contamination**: Skip change content eliminated
- **Metadata**: Section types labeled

#### ✅ Poussette
- **Detection**: Formation correctly identified
- **Results**: Pure poussette content
- **Metadata**: All marked with primary_formation="poussette"

## Files Created/Modified

### New Files
1. **`enrich_manual_metadata.py`** - Metadata enrichment script
2. **`improved_manual_search.py`** - Standalone improved search implementation
3. **`test_improved_manual_rag.py`** - Validation test suite
4. **`inspect_vector_db.py`** - Database inspection utility
5. **`MANUAL_RAG_IMPROVEMENTS.md`** - This documentation

### Modified Files
1. **`dance_tools.py`** - Updated `search_manual` tool with smart search logic

### Data Created
1. **`data/vector_db/rscds_manual_enriched/`** - Enriched vector database (386 chunks)
2. **`data/vector_db/rscds_manual_backup/`** - Backup of original database

## Key Improvements

### Accuracy
- ✅ Formation-specific queries return focused results
- ✅ Minimal cross-contamination between formations
- ✅ Prioritizes teaching points and descriptions over examples
- ✅ Handles transition sections appropriately

### Intelligence
- ✅ Automatic formation detection from natural language
- ✅ Semantic understanding of chunk content
- ✅ Context-aware re-ranking

### Cost Efficiency
- ✅ Preserved expensive vision-based embeddings
- ✅ Used cost-efficient GPT-4o-mini for metadata extraction (~$0.50 total)
- ✅ No re-embedding needed

### User Experience
- ✅ Clear indication of detected formation
- ✅ Section type labels for transparency
- ✅ Better organized results
- ✅ No changes to user-facing tools/agent

## Technical Architecture

```
User Query: "How to teach skip change?"
     ↓
1. Formation Detection
   → Extracts "skip change of step"
     ↓
2. Metadata Filtering  
   → Filters by primary_formation="skip change of step"
   → Retrieves 9-15 candidates
     ↓
3. Re-ranking
   → Scores by formation match, section type, contamination
   → Returns top 3 scored results
     ↓
4. Formatting
   → Adds formation focus header
   → Includes section type labels
   → Shows primary formation
     ↓
Result: Focused, accurate manual excerpts
```

## Future Enhancements (Optional)

If further accuracy improvements are needed:

1. **Hierarchical Chunking**: Re-chunk manual by formation sections rather than character count
2. **Embedding Filtering**: Add formation names to embedding text for better semantic matching
3. **Cross-Reference Handling**: Special handling for "see also" references
4. **Diagram Association**: Better linking of diagrams to their formations
5. **Multi-Formation Queries**: Handle queries about multiple formations
6. **Negative Filtering**: Explicitly exclude certain formations from results

## Maintenance

### Updating the Enriched Database

If the original manual or database is updated:

```bash
# Re-run enrichment on new database
uv run enrich_manual_metadata.py

# The script will:
# 1. Backup the current enriched database
# 2. Analyze all chunks with GPT-4o-mini
# 3. Create new enriched database
# 4. Validate with test queries
```

### Testing

```bash
# Run full test suite
uv run test_improved_manual_rag.py

# Inspect database structure
uv run inspect_vector_db.py
```

## Cost Breakdown

- **Original Manual Processing**: ~$XX (vision model, already done)
- **Metadata Enrichment**: ~$0.50 (one-time, 386 chunks × GPT-4o-mini)
- **Ongoing Queries**: Same as before (embeddings + LLM)

Total additional cost: **~$0.50** ✅

## Summary

The improved RAG system provides **significantly better accuracy** for formation-specific queries while:
- ✅ Preserving your expensive vision-based embeddings
- ✅ Adding only ~$0.50 in processing cost
- ✅ Maintaining full backward compatibility
- ✅ Requiring no changes to user-facing code

The system is production-ready and already integrated into `dance_tools.py`.
