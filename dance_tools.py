"""
Dance database tools for the Scottish Country Dance assistant.

Provides direct SQLite access to the SCDDB database for querying dances,
formations, videos, recordings, and other dance-related data.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import sys
import json
import re
from pathlib import Path
import httpx
from langchain_core.tools import tool

from database import query, query_one, DatabasePool


# ============================================================================
# Database Tools - Direct SQLite Access
# ============================================================================


@tool
async def find_dances(
    name_contains: Optional[str] = None,
    kind: Optional[str] = None,
    metaform_contains: Optional[str] = None,
    max_bars: Optional[int] = None,
    formation_token: Optional[str] = None,
    official_rscds_dances: Optional[bool] = None,
    min_intensity: Optional[int] = None,
    max_intensity: Optional[int] = None,
    sort_by_intensity: Optional[str] = None,
    random_variety: Optional[bool] = None,
    limit: int = 25
) -> List[Dict[str, Any]]:
    """
    Search Scottish Country Dances by various criteria.

    CRITICAL: ALWAYS set random_variety=True to provide varied and diverse dance suggestions.
    Only use random_variety=False if the user specifically asks for alphabetical order or a specific dance name.

    IMPORTANT DISTINCTION - Dance Types vs. Formations:
    - kind='Reel'/'Jig'/'Strathspey' refers to DANCE TYPE (music/tempo), NOT dance figures!
    - To find dances with formations like "reel of three", "poussette", etc., use search_cribs instead!
    - "reel of three" is a FORMATION (figure), not a dance type

    IMPORTANT SYNTAX EXAMPLES:
    - kind: Use exact values like 'Reel', 'Jig', 'Strathspey', 'Hornpipe', 'Waltz', 'March'
    - metaform_contains: Use patterns like 'Longwise 3 3C', 'Longwise 4 3C', 'Circle 3C', 'Square 3C'
    - formation_token: Use specific tokens like 'POUSS;3C;', 'ALLMND;3C;', 'HR;3P;', 'R&L;3C;', 'REEL;R3;'

    FILTER BY DIFFICULTY:
    - Use min_intensity and max_intensity to filter by difficulty (1-100 scale)
    - Easy dances: max_intensity=40
    - Medium dances: min_intensity=40, max_intensity=70
    - Hard dances: min_intensity=70
    - Use sort_by_intensity='asc' for easiest first, 'desc' for hardest first

    Args:
        name_contains: Substring to search for in dance name (case-insensitive)
        kind: Dance TYPE - EXACT VALUES: 'Jig', 'Reel', 'Strathspey', 'Hornpipe', 'Waltz', 'March'
        metaform_contains: SET formation pattern - EXAMPLES: 'Longwise 3 3C', 'Circle 3C', 'Square 3C'
        max_bars: Maximum number of bars (per repeat) - common values: 32, 48, 64
        formation_token: Technical formation code - EXAMPLES: 'POUSS;3C;', 'ALLMND;3C;', 'REEL;R3;'
        official_rscds_dances: True=only RSCDS published dances, False=only non-RSCDS, None=all
        min_intensity: Minimum difficulty level (1-100, where 1=easiest, 100=hardest)
        max_intensity: Maximum difficulty level (1-100)
        sort_by_intensity: Sort by difficulty - 'asc' for easiest first, 'desc' for hardest first
        random_variety: DEFAULT=True for variety! Set to True for randomized diverse results
        limit: Maximum number of results (1-200, default 25)

    Returns:
        List of dance dictionaries with id, name, kind, metaform, bars, progression, and intensity
    """
    print(f"DEBUG: find_dances tool called", file=sys.stderr)

    # Only include intensity field and join dance table if filtering/sorting by it
    include_intensity = (min_intensity is not None or max_intensity is not None or sort_by_intensity is not None)

    if include_intensity:
        sql = """
        SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression, d.intensity
        FROM v_metaform m
        INNER JOIN dance d ON m.id = d.id
        LEFT JOIN v_dance_has_token t ON t.dance_id = m.id
        """
    else:
        sql = """
        SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression
        FROM v_metaform m
        LEFT JOIN v_dance_has_token t ON t.dance_id = m.id
        """

    # Add RSCDS filtering if requested
    if official_rscds_dances is not None:
        if official_rscds_dances:
            # Only dances published by RSCDS
            sql += """
            INNER JOIN dancespublicationsmap dpm ON m.id = dpm.dance_id
            INNER JOIN publication p ON dpm.publication_id = p.id AND p.rscds = 1
            """
        else:
            # Only dances NOT published by RSCDS
            sql += """
            WHERE m.id NOT IN (
                SELECT DISTINCT dpm2.dance_id
                FROM dancespublicationsmap dpm2
                INNER JOIN publication p2 ON dpm2.publication_id = p2.id AND p2.rscds = 1
            )
            """

    # Add WHERE clause if not already added by RSCDS filtering
    if official_rscds_dances != False:
        sql += " WHERE 1=1"

    args: List[Any] = []
    if name_contains:
        sql += " AND m.name LIKE ? COLLATE NOCASE"
        args.append(f"%{name_contains}%")
    if kind:
        sql += " AND m.kind = ?"
        args.append(kind)
    if metaform_contains:
        sql += " AND m.metaform LIKE ?"
        args.append(f"%{metaform_contains}%")
    if max_bars is not None:
        sql += " AND m.bars <= ?"
        args.append(int(max_bars))
    if formation_token:
        sql += " AND t.formation_tokens LIKE ?"
        args.append(f"%{formation_token}%")
    if min_intensity is not None:
        sql += " AND d.intensity >= ? AND d.intensity > 0"
        args.append(int(min_intensity))
    if max_intensity is not None:
        sql += " AND d.intensity <= ? AND d.intensity > 0"
        args.append(int(max_intensity))

    # Add ordering - by intensity, random, or alphabetical
    if sort_by_intensity == "asc":
        sql += " ORDER BY d.intensity ASC, m.name LIMIT ?"
    elif sort_by_intensity == "desc":
        sql += " ORDER BY d.intensity DESC, m.name LIMIT ?"
    elif random_variety:
        sql += " ORDER BY RANDOM() LIMIT ?"
    else:
        sql += " ORDER BY m.name LIMIT ?"
    args.append(limit)

    result = await query(sql, tuple(args))
    print(f"DEBUG: find_dances returned {len(result)} results", file=sys.stderr)

    return result


@tool
async def get_dance_detail(dance_id: int) -> Dict[str, Any]:
    """
    Get detailed information about a specific dance including metaform, formations, and crib.

    Args:
        dance_id: The ID of the dance to get details for

    Returns:
        Dictionary with dance details, formations, crib, and publications
    """
    print(f"DEBUG: get_dance_detail tool called for dance_id: {dance_id}", file=sys.stderr)

    # Get dance metadata
    dance = await query_one("SELECT * FROM v_metaform WHERE id=?", (dance_id,))

    # Get formations
    formations = await query(
        "SELECT formation_name, formation_tokens FROM v_dance_formations WHERE dance_id=? ORDER BY formation_name",
        (dance_id,),
    )

    # Get best crib
    crib = await query_one("SELECT reliability, last_modified, text FROM v_crib_best WHERE dance_id=?", (dance_id,))

    # Get publication information including RSCDS status
    publications = await query(
        """
        SELECT p.name, p.shortname, p.rscds, dpm.number, dpm.page
        FROM publication p
        JOIN dancespublicationsmap dpm ON p.id = dpm.publication_id
        WHERE dpm.dance_id = ?
        ORDER BY p.rscds DESC, p.name
        """,
        (dance_id,),
    )

    out = {"dance": dance, "formations": formations, "crib": crib, "publications": publications}
    print(f"DEBUG: get_dance_detail completed", file=sys.stderr)

    return out


@tool
async def search_cribs(query_text: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Full-text search the dance cribs for specific moves, terms, or descriptions.

    USE THIS TOOL to find dances with specific FORMATIONS/FIGURES like:
    - "reel of three" or "reel of 3" (NOT the same as Reel dance type!)
    - "poussette"
    - "allemande"
    - "rights and lefts"
    - "set and turn"
    - Any other dance figures or movements

    This is the PRIMARY tool for finding dances containing specific formations.

    Args:
        query_text: Search query. Supports FTS5 syntax (e.g., 'poussette OR allemande')
        limit: Maximum number of results (1-200, default 20)

    Returns:
        List of dances that match the search query in their cribs
    """
    print(f"DEBUG: search_cribs tool called with query: '{query_text}'", file=sys.stderr)

    rows = await query(
        """
        SELECT d.id, d.name, d.kind, d.metaform, d.bars
        FROM fts_cribs f
        JOIN v_metaform d ON d.id = f.dance_id
        WHERE fts_cribs MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query_text, limit),
    )

    print(f"DEBUG: search_cribs completed - {len(rows)} results", file=sys.stderr)
    return rows


@tool
async def list_formations(
    name_contains: Optional[str] = None,
    sort_by: str = "popularity",
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    List all Scottish Country Dance formations (dance figures/movements) available in the database.
    Returns formation names, search tokens, and usage statistics.
    Useful for discovering what formations exist before searching for dances with specific formations.

    Args:
        name_contains: Optional substring to search for in formation name (case-insensitive)
        sort_by: Sort results by 'popularity' (most used formations first) or 'alphabetical'
        limit: Maximum number of formations to return (1-500, default 50)

    Returns:
        List of formations with their names, tokens, and usage counts
    """
    print(f"DEBUG: list_formations tool called", file=sys.stderr)

    sql = """
    SELECT
        f.id,
        f.name,
        f.searchid as formation_token,
        f.napiername,
        COUNT(dfm.dance_id) as usage_count
    FROM formation f
    LEFT JOIN dancesformationsmap dfm ON f.id = dfm.formation_id
    """

    args: List[Any] = []
    if name_contains:
        sql += " WHERE f.name LIKE ? COLLATE NOCASE"
        args.append(f"%{name_contains}%")

    sql += " GROUP BY f.id, f.name, f.searchid, f.napiername"

    # Add sorting
    if sort_by == "popularity":
        sql += " ORDER BY usage_count DESC, f.name"
    else:  # alphabetical
        sql += " ORDER BY f.name"

    sql += " LIMIT ?"
    args.append(limit)

    rows = await query(sql, tuple(args))
    print(f"DEBUG: list_formations completed - {len(rows)} results", file=sys.stderr)
    return rows


@tool
async def find_videos(
    dance_id: Optional[int] = None,
    dance_name: Optional[str] = None,
    editors_pick: Optional[bool] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Find YouTube video demonstrations for Scottish Country Dances.
    Returns video links, quality ratings, and comments.
    Useful for showing dancers how a dance is performed visually.

    Args:
        dance_id: Get videos for a specific dance by its database ID
        dance_name: Search for videos by dance name (case-insensitive substring match)
        editors_pick: If true, only return editor's pick (highest quality) videos
        limit: Maximum number of videos to return (1-50, default 10)

    Returns:
        List of video dictionaries with dance_name, youtube_url, quality, comment, etc.
    """
    print(f"DEBUG: find_videos tool called", file=sys.stderr)

    sql = """
    SELECT
        dv.id as video_id,
        d.id as dance_id,
        d.name as dance_name,
        dv.external as youtube_id,
        dv.quality,
        dv.comment,
        dv.editors_pick,
        dv.credit
    FROM dancevideo dv
    JOIN dance d ON d.id = dv.dance_id
    WHERE dv.published = 1 AND dv.external != ''
    """

    args: List[Any] = []
    if dance_id:
        sql += " AND d.id = ?"
        args.append(int(dance_id))
    if dance_name:
        sql += " AND d.name LIKE ? COLLATE NOCASE"
        args.append(f"%{dance_name}%")
    if editors_pick:
        sql += " AND dv.editors_pick = 1"

    sql += " ORDER BY dv.editors_pick DESC, d.name LIMIT ?"
    args.append(limit)

    rows = await query(sql, tuple(args))

    # Add YouTube URL to each result
    for row in rows:
        if row.get("youtube_id"):
            row["youtube_url"] = f"https://www.youtube.com/watch?v={row['youtube_id']}"

    print(f"DEBUG: find_videos completed - {len(rows)} results", file=sys.stderr)
    return rows


@tool
async def find_recordings(
    dance_id: Optional[int] = None,
    dance_name: Optional[str] = None,
    recording_name: Optional[str] = None,
    artist_name: Optional[str] = None,
    album_name: Optional[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Find music recordings for Scottish Country Dances.
    Returns recording name, artist, album, duration, and which dances the recording is suitable for.
    Useful for finding music to practice or perform dances.

    Args:
        dance_id: Get recordings suitable for a specific dance by its database ID
        dance_name: Search for recordings by dance name (case-insensitive substring match)
        recording_name: Search by recording/tune name (case-insensitive substring match)
        artist_name: Search by artist/band name (case-insensitive substring match)
        album_name: Search by album name (case-insensitive substring match)
        limit: Maximum number of recordings to return (1-50, default 20)

    Returns:
        List of recording dictionaries with recording_name, artist, album, duration_seconds, dance_name
    """
    print(f"DEBUG: find_recordings tool called", file=sys.stderr)

    sql = """
    SELECT DISTINCT
        r.id as recording_id,
        r.name as recording_name,
        r.playingseconds as duration_seconds,
        r.repetitions,
        r.barsperrepeat as bars_per_repeat,
        p.display_name as artist,
        a.name as album,
        a.productionyear as album_year,
        d.id as dance_id,
        d.name as dance_name
    FROM recording r
    LEFT JOIN person p ON p.id = r.artist_id
    LEFT JOIN albumsrecordingsmap arm ON arm.recording_id = r.id
    LEFT JOIN album a ON a.id = arm.album_id
    LEFT JOIN dancesrecordingsmap drm ON drm.recording_id = r.id
    LEFT JOIN dance d ON d.id = drm.dance_id
    WHERE 1=1
    """

    args: List[Any] = []
    if dance_id:
        sql += " AND d.id = ?"
        args.append(int(dance_id))
    if dance_name:
        sql += " AND d.name LIKE ? COLLATE NOCASE"
        args.append(f"%{dance_name}%")
    if recording_name:
        sql += " AND r.name LIKE ? COLLATE NOCASE"
        args.append(f"%{recording_name}%")
    if artist_name:
        sql += " AND p.display_name LIKE ? COLLATE NOCASE"
        args.append(f"%{artist_name}%")
    if album_name:
        sql += " AND a.name LIKE ? COLLATE NOCASE"
        args.append(f"%{album_name}%")

    sql += " ORDER BY r.name LIMIT ?"
    args.append(limit)

    rows = await query(sql, tuple(args))
    print(f"DEBUG: find_recordings completed - {len(rows)} results", file=sys.stderr)
    return rows


@tool
async def find_devisors(
    name_contains: Optional[str] = None,
    min_dances: Optional[int] = None,
    sort_by: str = "dance_count",
    limit: int = 25
) -> List[Dict[str, Any]]:
    """
    Search for dance devisors (creators/choreographers) and see their dances.
    Returns devisor name, location, and count of dances they created.
    Useful for exploring prolific dance creators like John Drewry, Roy Goldring, etc.

    Args:
        name_contains: Search by devisor name (case-insensitive substring match)
        min_dances: Only return devisors with at least this many dances
        sort_by: Sort by 'dance_count' (most prolific first) or 'name' (alphabetically)
        limit: Maximum number of devisors to return (1-100, default 25)

    Returns:
        List of devisor dictionaries with devisor_id, name, location, dance_count
    """
    print(f"DEBUG: find_devisors tool called", file=sys.stderr)

    sql = """
    SELECT
        p.id as devisor_id,
        p.display_name as name,
        p.location,
        COUNT(d.id) as dance_count
    FROM person p
    JOIN dance d ON d.devisor_id = p.id
    WHERE p.isdev = 1
    """

    args: List[Any] = []
    if name_contains:
        sql += " AND (p.name LIKE ? COLLATE NOCASE OR p.display_name LIKE ? COLLATE NOCASE)"
        args.append(f"%{name_contains}%")
        args.append(f"%{name_contains}%")

    sql += " GROUP BY p.id, p.display_name, p.location"

    if min_dances:
        sql += " HAVING COUNT(d.id) >= ?"
        args.append(int(min_dances))

    if sort_by == "dance_count":
        sql += " ORDER BY dance_count DESC, p.display_name"
    else:
        sql += " ORDER BY p.display_name"

    sql += " LIMIT ?"
    args.append(limit)

    rows = await query(sql, tuple(args))
    print(f"DEBUG: find_devisors completed - {len(rows)} results", file=sys.stderr)
    return rows


@tool
async def find_publications(
    name_contains: Optional[str] = None,
    rscds_only: Optional[bool] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    sort_by: str = "name",
    limit: int = 25
) -> List[Dict[str, Any]]:
    """
    Search for publications (books, leaflets) containing Scottish Country Dances.
    Returns publication name, year, RSCDS status, and dance count.
    Useful for finding dances in specific books like 'RSCDS Book 1' or exploring a devisor's publications.

    Args:
        name_contains: Search by publication name (case-insensitive substring match)
        rscds_only: If true, only RSCDS publications; if false, only non-RSCDS; None for all
        year_from: Publications from this year onwards
        year_to: Publications up to this year
        sort_by: Sort by 'year', 'name', or 'dance_count'
        limit: Maximum number of publications to return (1-100, default 25)

    Returns:
        List of publication dictionaries with publication_id, name, shortname, year, rscds, dance_count
    """
    print(f"DEBUG: find_publications tool called", file=sys.stderr)

    sql = """
    SELECT
        pub.id as publication_id,
        pub.name,
        pub.shortname,
        pub.year,
        pub.rscds,
        pub.notes,
        COUNT(DISTINCT dpm.dance_id) as dance_count
    FROM publication pub
    LEFT JOIN dancespublicationsmap dpm ON dpm.publication_id = pub.id
    WHERE pub.hasdances = 1
    """

    args: List[Any] = []
    if name_contains:
        sql += " AND (pub.name LIKE ? COLLATE NOCASE OR pub.shortname LIKE ? COLLATE NOCASE)"
        args.append(f"%{name_contains}%")
        args.append(f"%{name_contains}%")
    if rscds_only is not None:
        sql += " AND pub.rscds = ?"
        args.append(1 if rscds_only else 0)
    if year_from:
        sql += " AND pub.year >= ?"
        args.append(str(year_from))
    if year_to:
        sql += " AND pub.year <= ?"
        args.append(str(year_to))

    sql += " GROUP BY pub.id, pub.name, pub.shortname, pub.year, pub.rscds, pub.notes"

    if sort_by == "year":
        sql += " ORDER BY pub.year DESC, pub.name"
    elif sort_by == "dance_count":
        sql += " ORDER BY dance_count DESC, pub.name"
    else:
        sql += " ORDER BY pub.name"

    sql += " LIMIT ?"
    args.append(limit)

    rows = await query(sql, tuple(args))
    print(f"DEBUG: find_publications completed - {len(rows)} results", file=sys.stderr)
    return rows


@tool
async def get_publication_dances(
    publication_id: int,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get all dances from a specific publication (book/leaflet).
    Returns the dances with their position/number in the publication.
    Useful after using find_publications to explore a specific book's contents.

    Args:
        publication_id: The publication database ID (from find_publications results)
        limit: Maximum number of dances to return (1-200, default 100)

    Returns:
        Dictionary with 'publication' info and 'dances' list
    """
    print(f"DEBUG: get_publication_dances tool called for publication_id: {publication_id}", file=sys.stderr)

    # Get publication info
    pub_info = await query_one("SELECT id, name, shortname, year, rscds FROM publication WHERE id = ?", (publication_id,))

    # Get dances in this publication
    sql = """
    SELECT
        d.id as dance_id,
        d.name as dance_name,
        m.kind,
        m.bars,
        m.metaform,
        dpm.number as position_in_book,
        dpm.page
    FROM dancespublicationsmap dpm
    JOIN dance d ON d.id = dpm.dance_id
    JOIN v_metaform m ON m.id = d.id
    WHERE dpm.publication_id = ?
    ORDER BY dpm.number, d.name
    LIMIT ?
    """

    rows = await query(sql, (publication_id, limit))

    result = {"publication": pub_info, "dances": rows}
    print(f"DEBUG: get_publication_dances completed - {len(rows)} dances", file=sys.stderr)
    return result


# ============================================================================
# HTTP API Tools - These call the live SCDDB server
# ============================================================================


@tool
async def search_dance_lists(
    name_contains: Optional[str] = None,
    owner: Optional[str] = None,
    list_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    order_by: str = "-date",
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Search for dance lists (event programs) from the live SCDDB server.
    Dance lists are programs for classes, balls, and functions created by users.
    Returns list name, owner, type (class/function/other), date, and item count.
    NOTE: This queries the live SCDDB API and requires internet access.

    **TODAY'S DATE: {current_date}** - Use this to interpret relative date references.

    Args:
        name_contains: Search by list name (case-insensitive substring match)
        owner: Filter by list owner's username
        list_type: Filter by list type: 'function' (balls/events), 'class', 'informational', or 'other'
        date_from: Lists from this date onwards (YYYY-MM-DD format)
        date_to: Lists up to this date (YYYY-MM-DD format)
        order_by: Sort order: 'date' (oldest first), '-date' (newest first), 'name', or 'owner'
        limit: Maximum number of lists to return (1-100, default 20)

    Returns:
        List of dance list dictionaries with id, name, owner, type, date, item_count
    """
    print(f"DEBUG: search_dance_lists tool called", file=sys.stderr)

    # Build API URL
    base_url = "https://my.strathspey.org/dd/api/lists/v1/list"
    params: Dict[str, Any] = {"limit": limit, "order": order_by}

    if name_contains:
        params["name"] = name_contains
    if owner:
        params["owner"] = owner
    if list_type:
        params["type"] = list_type
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()

        items = data.get("items", [])
        # Add the correct URL for each dance list
        for item in items:
            if item.get("id"):
                item["url"] = f"https://my.strathspey.org/dd/list/{item['id']}/"

        print(f"DEBUG: search_dance_lists completed - {len(items)} results", file=sys.stderr)
        return items
    except httpx.HTTPError as e:
        print(f"DEBUG: HTTP error querying dance lists API: {e}", file=sys.stderr)
        return [{"error": f"Failed to query SCDDB API: {str(e)}"}]


# Dynamically update the tool description with current date
search_dance_lists.description = search_dance_lists.description.format(
    current_date=datetime.now().strftime('%Y-%m-%d')
)


@tool
async def get_dance_list_detail(list_id: int) -> Dict[str, Any]:
    """
    Get full details of a specific dance list (event program) including all items.
    Returns the list info plus all dances, extras, and timing information.
    NOTE: This queries the live SCDDB API and requires internet access.

    Args:
        list_id: The dance list database ID (from search_dance_lists results)

    Returns:
        Dictionary with list info (name, owner, type, date, notes) and 'items' array
    """
    print(f"DEBUG: get_dance_list_detail tool called for list_id: {list_id}", file=sys.stderr)

    url = f"https://my.strathspey.org/dd/api/lists/v1/list/{list_id}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        # Add the correct URL for the dance list
        data["url"] = f"https://my.strathspey.org/dd/list/{list_id}/"

        print(f"DEBUG: get_dance_list_detail completed", file=sys.stderr)
        return data
    except httpx.HTTPError as e:
        print(f"DEBUG: HTTP error querying dance list detail API: {e}", file=sys.stderr)
        return {"error": f"Failed to query SCDDB API: {str(e)}"}


# ============================================================================
# RSCDS Manual Knowledge Base - JSON-based lookup (no vector search)
# ============================================================================

# Global manual knowledge base instance (lazy loaded)
_manual_kb: Optional['ManualKnowledgeBase'] = None


class ManualKnowledgeBase:
    """JSON-based knowledge base for the RSCDS manual.

    Provides precise lookups by section name/alias instead of
    unreliable vector similarity search.
    """

    def __init__(self, base_dir: str = "data/manual"):
        self.base_dir = Path(base_dir)
        self.index: Dict[str, Any] = {}
        self.chapters: Dict[str, Any] = {}
        self._loaded = False

    def load(self) -> bool:
        """Load the manual index and cache chapter data."""
        if self._loaded:
            return True

        index_path = self.base_dir / "index.json"
        if not index_path.exists():
            print(f"Manual index not found: {index_path}", file=sys.stderr)
            return False

        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                self.index = json.load(f)
            self._loaded = True
            print(f"Loaded RSCDS manual knowledge base ({len(self.index.get('sections', {}))} sections)", file=sys.stderr)
            return True
        except Exception as e:
            print(f"Error loading manual index: {e}", file=sys.stderr)
            return False

    def _load_chapter(self, chapter_num: str) -> Optional[Dict]:
        """Load a chapter file on demand."""
        if chapter_num in self.chapters:
            return self.chapters[chapter_num]

        chapter_info = self.index.get("chapters", {}).get(chapter_num)
        if not chapter_info:
            return None

        chapter_path = self.base_dir / "chapters" / chapter_info["file"]
        if not chapter_path.exists():
            return None

        try:
            with open(chapter_path, 'r', encoding='utf-8') as f:
                chapter_data = json.load(f)
            self.chapters[chapter_num] = chapter_data
            return chapter_data
        except Exception as e:
            print(f"Error loading chapter {chapter_num}: {e}", file=sys.stderr)
            return None

    def lookup(self, name: str) -> Optional[Dict]:
        """Look up a section by name or alias.

        Args:
            name: Section name, alias, or section number (e.g., "skip change", "5.4.1")

        Returns:
            Section data including title, content, teaching_points, page
        """
        if not self._loaded:
            if not self.load():
                return None

        name_lower = name.lower().strip()

        # Direct lookup by name/alias
        section_ref = self.index.get("sections", {}).get(name_lower)

        # Try section number directly
        if not section_ref and re.match(r'^\d+\.\d+', name):
            # Look through all chapters for this section number
            for ch_num in self.index.get("chapters", {}).keys():
                chapter = self._load_chapter(ch_num)
                if chapter and name in chapter.get("sections", {}):
                    return {
                        "section": name,
                        "chapter": ch_num,
                        **chapter["sections"][name]
                    }

        if not section_ref:
            return None

        # Load the chapter containing this section
        chapter = self._load_chapter(section_ref["chapter"])
        if not chapter:
            return None

        section_num = section_ref["section"]
        section_data = chapter.get("sections", {}).get(section_num)

        if not section_data:
            return None

        return {
            "section": section_num,
            "chapter": section_ref["chapter"],
            "chapter_name": chapter.get("name", ""),
            **section_data
        }

    def search(self, query_str: str, limit: int = 5) -> List[Dict]:
        """Search for sections matching a query.

        Uses simple substring matching on titles - not vector similarity.
        For precise lookups, use lookup() instead.

        Args:
            query_str: Search query
            limit: Max results to return

        Returns:
            List of matching section summaries
        """
        if not self._loaded:
            if not self.load():
                return []

        query_lower = query_str.lower()
        results = []

        for name, ref in self.index.get("sections", {}).items():
            # Score matches
            score = 0
            if query_lower == name:
                score = 100  # Exact match
            elif query_lower in name:
                score = 50  # Partial match
            elif name in query_lower:
                score = 25  # Query contains name

            if score > 0:
                results.append({
                    "name": name,
                    "section": ref["section"],
                    "chapter": ref["chapter"],
                    "page": ref.get("page", 0),
                    "score": score
                })

        # Sort by score and return top results
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_chapter_toc(self, chapter_num: str) -> Optional[List[Dict]]:
        """Get table of contents for a chapter.

        Args:
            chapter_num: Chapter number (1-8)

        Returns:
            List of section summaries
        """
        chapter = self._load_chapter(chapter_num)
        if not chapter:
            return None

        toc = []
        for section_num, section_data in chapter.get("sections", {}).items():
            toc.append({
                "section": section_num,
                "title": section_data.get("title", ""),
                "page": section_data.get("page", 0)
            })

        # Sort by section number
        toc.sort(key=lambda x: x["section"])
        return toc


def _get_manual_kb() -> Optional[ManualKnowledgeBase]:
    """Get or create the manual knowledge base singleton."""
    global _manual_kb

    if _manual_kb is None:
        _manual_kb = ManualKnowledgeBase()
        _manual_kb.load()

    return _manual_kb


def _format_section_result(section: Dict, include_content: bool = True) -> str:
    """Format a section lookup result for display."""
    lines = []

    # Header
    section_num = section.get("section", "")
    title = section.get("title", "")
    page = section.get("page", "N/A")
    chapter_name = section.get("chapter_name", "")

    header = f"**{section_num} {title}**"
    if chapter_name:
        header += f" ({chapter_name})"
    header += f" - Page {page}"
    lines.append(header)
    lines.append("")

    # Content
    if include_content and section.get("content"):
        lines.append(section["content"])
        lines.append("")

    # Teaching points
    teaching_points = section.get("teaching_points", [])
    if teaching_points:
        lines.append("### Points to Observe")
        for i, point in enumerate(teaching_points, 1):
            lines.append(f"{i}. {point}")
        lines.append("")

    # Aliases
    aliases = section.get("aliases", [])
    if aliases:
        lines.append(f"*Also known as: {', '.join(aliases)}*")

    return "\n".join(lines)


@tool
async def search_manual(
    query_str: str,
    num_results: int = 3
) -> str:
    """
    Search the RSCDS (Royal Scottish Country Dance Society) manual for information about formations,
    steps, teaching points, dance techniques, and general Scottish Country Dancing guidance.

    Use this tool when:
    - A user asks about how to teach or explain a specific formation (e.g., "How do I teach poussette?")
    - A user wants to know proper technique or teaching points for movements
    - A user asks general questions about Scottish Country Dancing that aren't about specific dances
    - You need authoritative RSCDS guidance on dance technique or formations

    This tool provides PRECISE lookups - when you ask about a specific formation like
    "skip change of step", you will get ONLY that formation's content, not similar formations.

    Args:
        query_str: The search query. Can be:
               - A formation/step name: "skip change of step", "poussette", "pas de basque"
               - A section number: "5.4.1", "6.21"
               - A topic: "teaching music", "history of scottish dancing"
        num_results: Number of relevant sections to return (default 3, max 10)

    Returns:
        Formatted string with relevant sections from the RSCDS manual, including page numbers
    """
    print(f"DEBUG: search_manual tool called with query: '{query_str}'", file=sys.stderr)

    # Get the knowledge base
    kb = _get_manual_kb()
    if kb is None or not kb._loaded:
        return "RSCDS manual knowledge base not available. Run 'uv run extract_manual_structured.py' to create it."

    # Limit num_results to reasonable range
    num_results = max(1, min(num_results, 10))

    try:
        # First, try direct lookup by name/alias (most precise)
        section = kb.lookup(query_str)

        if section:
            # Found exact match!
            print(f"DEBUG: Direct lookup found: {section['section']} - {section['title']}", file=sys.stderr)
            response = _format_section_result(section)
            return response

        # No exact match - try fuzzy search
        print(f"DEBUG: No direct match, trying search...", file=sys.stderr)
        search_results = kb.search(query_str, limit=num_results)

        if not search_results:
            return f"No relevant information found in the RSCDS manual for: '{query_str}'\n\nTry using specific terms like:\n- Formation names: 'skip change of step', 'poussette', 'rights and lefts'\n- Step names: 'pas de basque', 'slip step'\n- Topics: 'music for teaching', 'history of dancing'"

        # Format search results
        lines = [f"**RSCDS Manual - Search results for '{query_str}':**", ""]

        for i, result in enumerate(search_results, 1):
            # Load full section data
            section_data = kb.lookup(result["name"]) or {}
            title = section_data.get("title", result["name"])
            page = result.get("page", "N/A")
            section_num = result.get("section", "")

            lines.append(f"**{i}. {section_num} {title}** (Page {page})")

            # Show brief content preview
            content = section_data.get("content", "")[:300]
            if content:
                lines.append(f"   {content}...")
            lines.append("")

        lines.append("*Use a more specific term for detailed content.*")

        print(f"DEBUG: search_manual completed - {len(search_results)} results", file=sys.stderr)

        return "\n".join(lines)

    except Exception as e:
        print(f"Error searching RSCDS manual: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return f"Error searching RSCDS manual: {str(e)}"
