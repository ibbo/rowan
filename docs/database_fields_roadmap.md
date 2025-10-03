# Database Fields Enhancement Roadmap

## Overview
This document outlines all available database fields that could be exposed via MCP tools to enhance the Scottish Country Dance agent's capabilities.

**Database Statistics:**
- Total dances: 22,633
- RSCDS published dances: 1,061
- Community dances: 21,572

---

## Currently Exposed Fields ✅

| Field | Description | Coverage |
|-------|-------------|----------|
| `name` | Dance name (searchable substring) | 100% |
| `kind/type` | Dance type (Jig, Reel, Strathspey, etc.) | 100% |
| `metaform` | Formation pattern (e.g., "Longwise 3C") | 100% |
| `bars` | Number of bars per repeat | 100% |
| `formation_token` | Specific formation search tokens | 100% |
| `official_rscds_dances` | RSCDS publication filter | 100% |
| `min_intensity` / `max_intensity` | Difficulty level filter (1-100 scale) | 43.5% |
| `sort_by_intensity` | Sort by difficulty (asc/desc) | 43.5% |
| `random_variety` | Randomize results for variety | N/A |

---

## Tier 1 - High Impact 🔥
**Implement First - Maximum User Value**

### 1. Intensity/Difficulty ⭐ ✅ COMPLETED (2025-10-03)
- **Database Field:** `dance.intensity` (integer, 0-100+ scale)
- **Coverage:** 9,852 / 22,633 dances (43.5%)
- **Data Range:** 1 (easiest) to 100 (hardest), some outliers at 231
- **Difficulty Distribution:**
  - Easy (1-40): 342 dances
  - Medium (41-69): 6,407 dances
  - Hard (70+): 3,103 dances

**Use Cases:**
```
"Find easy dances for beginners"
"Show me challenging dances for experienced dancers"
"Medium difficulty reels"
"Dances with intensity less than 50"
```

**Implementation:**
- ✅ Added `min_intensity` parameter to `find_dances` tool
- ✅ Added `max_intensity` parameter to `find_dances` tool
- ✅ Added `sort_by_intensity` parameter (asc/desc) to `find_dances` tool
- ✅ Intensity field included in search results
- ✅ Unrated dances handled (intensity=-1 excluded when filtering with `d.intensity > 0`)

**Technical Notes:**
- Database uses `-1` for unrated dances (not NULL)
- Filtering automatically excludes unrated dances to provide meaningful results
- 12,774 dances are unrated (intensity=-1), 9,852 have ratings (intensity > 0)

---

### 2. Available Recordings 🎼
- **Database Tables:** `recording`, `album` (via `dancesrecordingsmap`, `albumsrecordingsmap`)
- **Coverage:** 5,715 / 22,633 dances (25%)

**Use Cases:**
```
"Find dances with available recordings"
"Show dances from the 'Book 31' album"
"Reels that I can listen to"
"Dances with music available"
```

**Implementation Options:**
- **Option A:** Add `has_recording` boolean filter to `find_dances`
- **Option B:** New tool `find_dances_with_recordings` with album/recording filters
- **Option C:** Add recording info to `dance_detail` response (already feasible)

**Sample Data:**
```
Dance: Autumn in Appin
Recording: Autumn in Appin
Album: Scottish Dance Favourites Volume 2
```

---

### 3. Associated Tunes 🎵
- **Database Tables:** `tune` (via `dancestunesmap`)
- **Coverage:** 10,424 / 22,633 dances (46%)

**Use Cases:**
```
"Find dances that use 'Mrs. MacLeod' tune"
"What dances go with this tune?"
"Show me dances with recommended tunes"
"Dances using traditional tunes"
```

**Implementation Options:**
- **Option A:** Add `tune_name` parameter to `find_dances`
- **Option B:** New tool `find_dances_by_tune`
- **Option C:** Add tune info to `dance_detail` response

**Sample Data:**
```
Dance: Alewife and her Barrel, The
Tune: Alewife and her Barrel, The
```

---

## Tier 2 - Medium Impact 📊
**Implement Next - Good User Value**

### 4. Year Devised 📅
- **Database Field:** `dance.devised` (date)
- **Coverage:** 10,437 / 22,633 dances (46%)
- **Date Range:** Historical (1800s) to 3006 (likely data error), mostly 1900-2025

**Use Cases:**
```
"Find modern dances created after 2020"
"Show traditional dances from the 1800s"
"Dances created in the last 5 years"
"Historical dances before 1950"
```

**Implementation:**
- Add `devised_after` and `devised_before` parameters (date or year)
- Consider decade grouping for better UX

---

### 5. Devisor/Choreographer 👤
- **Database Table:** `person` (via `dance.devisor_id`)
- **Coverage:** 100% (all dances have a devisor)

**Use Cases:**
```
"Find dances by John Drewry"
"Show me dances devised by Roy Goldring"
"What dances did Murrough Landon create?"
"Dances choreographed by RSCDS"
```

**Implementation:**
- Add `devisor_name` parameter to `find_dances` (substring search)
- Consider adding devisor info to search results

---

### 6. Videos Available 🎥
- **Database Table:** `dancevideo`
- **Coverage:** Unknown (needs investigation)

**Use Cases:**
```
"Show dances with video demonstrations"
"Find dances I can watch"
"Dances with instructional videos"
```

**Implementation:**
- Add `has_video` boolean filter to `find_dances`
- Include video URLs in `dance_detail` response

---

## Tier 3 - Nice to Have 📝
**Implement Later - Specialized Use Cases**

### 7. Progression Pattern 🔄
- **Database Table:** `progression`
- **Coverage:** ~100% (most dances have progression)
- **Values:** 2341, 2413, OnceOnly, ChangePtnr, Canon, Becket, Nonprogressive, etc.

**Use Cases:**
```
"Find non-progressive dances"
"Show dances with 2341 progression"
"Dances where you change partners"
```

**Implementation:**
- Add `progression` parameter to `find_dances`
- Requires user knowledge of progression notation

---

### 8. Dance Notes/Description 📖
- **Database Field:** `dance.notes` (text)
- **Coverage:** 8,516 / 22,633 dances (38%)

**Use Cases:**
```
"Find dances with historical context"
"Search notes for 'teaching dance'"
"Dances with special instructions"
```

**Implementation:**
- Add `notes_contains` parameter to `find_dances`
- Or enhance `search_cribs` to include notes

---

### 9. Diagrams Available 📊
- **Database Table:** `dancediagram`
- **Coverage:** Unknown (needs investigation)

**Use Cases:**
```
"Find dances with diagrams"
"Show dances with visual aids"
```

**Implementation:**
- Add `has_diagram` boolean filter
- Include diagram URLs in `dance_detail`

---

## Tier 4 - Specialized 🔬
**Low Priority - Niche Use Cases**

### 10. Shape/Set Formation 🔲
- **Database Table:** `shape`
- **Coverage:** ~100%
- **Values:** Longwise (2-8), Square, Circle, Triangular, Round the room, Hexagonal, etc.
- **Note:** Already partially exposed via `metaform_contains`

**Use Cases:**
```
"Find square set dances"
"Show me circle dances"
"Triangular formation dances"
```

**Implementation:**
- Add explicit `shape` parameter (may be redundant with metaform)

---

### 11. Number of Couples 👥
- **Database Table:** `couples`
- **Coverage:** ~100%
- **Values:** 1-8+ couples, variations like "4 couples (3x,4x)"
- **Note:** Already partially exposed via `metaform_contains`

**Use Cases:**
```
"Find dances for exactly 3 couples"
"Show dances for 4 or more couples"
"Dances for small sets (2-3 couples)"
```

**Implementation:**
- Add `min_couples` / `max_couples` parameters
- Parse couples from metaform or use direct field

---

### 12. Medley Type 🎭
- **Database Table:** `medleytype`
- **Coverage:** Limited (only for medley dances)
- **Values:** Combinations like "J48+S64+R48", "S32+R32"

**Use Cases:**
```
"Find specific medley combinations"
"Show medleys with Jig and Strathspey"
```

**Implementation:**
- Very niche - low priority

---

### 13. Verification Status ✓
- **Database Fields:** `data_verified`, `steps_verified`, `formations_verified`, `tunes_verified`
- **Coverage:** 100%

**Use Cases:**
- Data quality filtering (probably internal use only)
- "Show only fully verified dances"

**Implementation:**
- Low priority - mainly for data quality assurance

---

## Implementation Strategy

### Phase 1: Quick Wins (Week 1)
1. **Intensity/Difficulty** - Add to `find_dances` tool
2. **Recordings** - Add to `dance_detail` response (easy)
3. **Tunes** - Add to `dance_detail` response (easy)

### Phase 2: Search Enhancements (Week 2)
4. **Year Devised** - Add date range filters
5. **Devisor** - Add choreographer search
6. **Has Recording/Video** - Add boolean filters

### Phase 3: Advanced Features (Week 3+)
7. **Progression Pattern** - For advanced users
8. **Notes Search** - Full-text search enhancement
9. **Diagrams/Videos** - Include in detail responses

---

## Technical Considerations

### Database Performance
- Most fields are indexed or in views (v_metaform, v_dances)
- Intensity filtering will need index on `dance.intensity`
- Date filtering may need index on `dance.devised`

### NULL Handling
- Many fields have NULL values (intensity: 57%, devised: 54%, etc.)
- Need clear documentation on NULL behavior
- Consider "has_intensity" filter for explicit NULL filtering

### API Design
- Keep `find_dances` tool focused, avoid parameter explosion
- Consider separate tools for specialized searches
- Maintain backward compatibility with existing parameters

### LLM Prompt Engineering
- Clear parameter descriptions crucial for LLM tool selection
- Include example queries in tool descriptions
- Use prominent keywords (e.g., "FILTER BY DIFFICULTY")

---

## Success Metrics

### User Engagement
- Track which new filters are most used
- Monitor query success rates
- Gather user feedback on difficulty ratings

### Data Quality
- Identify dances missing key fields (intensity, recordings)
- Consider data enrichment efforts
- Track verification status improvements

---

## Future Enhancements

### Community Features
- User ratings/difficulty feedback
- Personal favorites/collections
- Dance recommendations based on skill level

### Music Integration
- Direct links to Spotify/YouTube recordings
- Tempo/BPM information
- Music style preferences

### Learning Paths
- Beginner → Intermediate → Advanced progressions
- Skill-based dance recommendations
- Formation complexity analysis

---

## Notes
- Created: 2025-10-03
- Last Updated: 2025-10-03
- Database: scddb.sqlite
- Total Dances: 22,633
