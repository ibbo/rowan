#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import logging
import sqlite3
import random
import time
import httpx
from typing import Any, Dict, List, Optional

from mcp.server import Server, InitializationOptions, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent  # TextContent used for outputs
import mcp.types as types

# --- Config ---
DB_PATH = os.environ.get("SCDDB_SQLITE", "data/scddb/scddb.sqlite")

# --- DB helpers with profiling ---
def q(sql: str, args: tuple = ()) -> List[Dict[str, Any]]:
    start_time = time.perf_counter()
    con = sqlite3.connect(DB_PATH)
    try:
        con.row_factory = sqlite3.Row
        query_start = time.perf_counter()
        cur = con.execute(sql, args)
        fetch_start = time.perf_counter()
        results = [dict(r) for r in cur.fetchall()]
        end_time = time.perf_counter()
        
        # Log detailed timing
        total_time = (end_time - start_time) * 1000
        query_time = (fetch_start - query_start) * 1000
        fetch_time = (end_time - fetch_start) * 1000
        connection_time = (query_start - start_time) * 1000
        
        logger.info(f"QUERY PERF: Total={total_time:.2f}ms (Conn={connection_time:.2f}ms, Query={query_time:.2f}ms, Fetch={fetch_time:.2f}ms), Rows={len(results)}")
        logger.debug(f"SQL: {sql[:200]}{'...' if len(sql) > 200 else ''}")
        
        return results
    finally:
        con.close()

def q_one(sql: str, args: tuple = ()) -> Optional[Dict[str, Any]]:
    start_time = time.perf_counter()
    con = sqlite3.connect(DB_PATH)
    try:
        con.row_factory = sqlite3.Row
        query_start = time.perf_counter()
        cur = con.execute(sql, args)
        fetch_start = time.perf_counter()
        row = cur.fetchone()
        result = dict(row) if row else None
        end_time = time.perf_counter()
        
        # Log detailed timing
        total_time = (end_time - start_time) * 1000
        query_time = (fetch_start - query_start) * 1000
        fetch_time = (end_time - fetch_start) * 1000
        connection_time = (query_start - start_time) * 1000
        
        logger.info(f"QUERY_ONE PERF: Total={total_time:.2f}ms (Conn={connection_time:.2f}ms, Query={query_time:.2f}ms, Fetch={fetch_time:.2f}ms), Found={result is not None}")
        logger.debug(f"SQL: {sql[:200]}{'...' if len(sql) > 200 else ''}")
        
        return result
    finally:
        con.close()

# --- MCP server ---
# Allow overriding log level via env var for easier diagnostics
LOG_LEVEL = os.environ.get("SCDDB_LOG_LEVEL", "INFO").upper()
# Force logging to stderr to avoid corrupting MCP stdio protocol on stdout
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), stream=sys.stderr, force=True)
logger = logging.getLogger("scddb")
server = Server("scddb")

# Tool definitions (JSON Schemas keep the client honest)
@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    logger.info("list_tools")
    return [
        Tool(
            name="find_dances",
            description=(
                "Search Scottish Country Dances by various criteria. "
                "IMPORTANT: Use 'official_rscds_dances=true' to find official RSCDS published dances, "
                "or 'official_rscds_dances=false' for community/non-RSCDS dances. "
                "Use 'random_variety=true' for varied results instead of alphabetical order. "
                "FILTER BY DIFFICULTY: Use 'min_intensity' and 'max_intensity' to find dances by difficulty level (1-100 scale)."
            ),
            inputSchema={
                "type":"object",
                "properties":{
                    "name_contains":{"type":["string","null"], "description":"Substring to search for in dance name (case-insensitive)"},
                    "kind":{"type":["string","null"], "description":"Dance type: Jig | Reel | Strathspey | Hornpipe | Waltz | March | ..."},
                    "metaform_contains":{"type":["string","null"], "description":"Formation pattern like 'Longwise 3C', 'Square', 'Circle', etc."},
                    "max_bars":{"type":["integer","null"], "minimum":1, "description":"Maximum number of bars (per repeat)"},
                    "formation_token":{"type":["string","null"], "description":"Specific formation token like 'REEL;3P;' or 'JIG;4C;'"},
                    "official_rscds_dances":{"type":["boolean","null"], "description":"FILTER BY PUBLICATION: true=only official RSCDS published dances, false=only community/non-RSCDS dances, null=all dances. Use this to distinguish between official and community dances!"},
                    "min_intensity":{"type":["integer","null"], "minimum":1, "maximum":100, "description":"FILTER BY DIFFICULTY: Minimum difficulty/intensity level (1=easiest, 100=hardest). Use for 'easy dances' (e.g., max 40), 'medium dances' (40-65), or 'hard dances' (65+)."},
                    "max_intensity":{"type":["integer","null"], "minimum":1, "maximum":100, "description":"FILTER BY DIFFICULTY: Maximum difficulty/intensity level (1=easiest, 100=hardest). Use for 'easy dances' (e.g., max 40), 'medium dances' (40-65), or 'hard dances' (65+)."},
                    "sort_by_intensity":{"type":["string","null"], "enum":["asc","desc"], "description":"Sort results by difficulty: 'asc'=easiest first, 'desc'=hardest first. Omit for alphabetical (or random if random_variety=true)"},
                    "random_variety":{"type":["boolean","null"], "description":"If true, randomize results for variety instead of alphabetical order. Recommended for diverse suggestions!"},
                    "limit":{"type":"integer","minimum":1,"maximum":200,"default":25}
                },
                "required":[]
            },
        ),
        Tool(
            name="dance_detail",
            description="Get one dance with joined metaform, formations, and best crib.",
            inputSchema={
                "type":"object",
                "properties":{"dance_id":{"type":"integer","minimum":1}},
                "required":["dance_id"]
            },
        ),
        Tool(
            name="search_cribs",
            description="Full-text search the best cribs. Query supports FTS5 syntax (e.g., 'poussette OR allemande').",
            inputSchema={
                "type":"object",
                "properties":{
                    "query":{"type":"string"},
                    "limit":{"type":"integer","minimum":1,"maximum":200,"default":20}
                },
                "required":["query"]
            },
        ),
        Tool(
            name="list_formations",
            description=(
                "List all Scottish Country Dance formations (dance figures/movements) available in the database. "
                "Returns formation names, search tokens, and usage statistics. "
                "Useful for discovering what formations exist before searching for dances with specific formations. "
                "Can filter by name substring and sort by popularity (most used) or alphabetically."
            ),
            inputSchema={
                "type":"object",
                "properties":{
                    "name_contains":{"type":["string","null"], "description":"Substring to search for in formation name (case-insensitive)"},
                    "sort_by":{"type":"string","enum":["popularity","alphabetical"],"default":"popularity", "description":"Sort results by popularity (most used formations first) or alphabetically"},
                    "limit":{"type":"integer","minimum":1,"maximum":500,"default":50, "description":"Maximum number of formations to return"}
                },
                "required":[]
            },
        ),
        Tool(
            name="find_videos",
            description=(
                "Find YouTube video demonstrations for Scottish Country Dances. "
                "Returns video links, quality ratings, and comments. "
                "Useful for showing dancers how a dance is performed visually."
            ),
            inputSchema={
                "type":"object",
                "properties":{
                    "dance_id":{"type":["integer","null"], "minimum":1, "description":"Get videos for a specific dance by its database ID"},
                    "dance_name":{"type":["string","null"], "description":"Search for videos by dance name (case-insensitive substring match)"},
                    "editors_pick":{"type":["boolean","null"], "description":"If true, only return editor's pick (highest quality) videos"},
                    "limit":{"type":"integer","minimum":1,"maximum":50,"default":10, "description":"Maximum number of videos to return"}
                },
                "required":[]
            },
        ),
        Tool(
            name="find_recordings",
            description=(
                "Find music recordings for Scottish Country Dances. "
                "Returns recording name, artist, album, duration, and which dances the recording is suitable for. "
                "Useful for finding music to practice or perform dances."
            ),
            inputSchema={
                "type":"object",
                "properties":{
                    "dance_id":{"type":["integer","null"], "minimum":1, "description":"Get recordings suitable for a specific dance by its database ID"},
                    "dance_name":{"type":["string","null"], "description":"Search for recordings by dance name (case-insensitive substring match)"},
                    "recording_name":{"type":["string","null"], "description":"Search by recording/tune name (case-insensitive substring match)"},
                    "artist_name":{"type":["string","null"], "description":"Search by artist/band name (case-insensitive substring match)"},
                    "album_name":{"type":["string","null"], "description":"Search by album name (case-insensitive substring match)"},
                    "limit":{"type":"integer","minimum":1,"maximum":50,"default":20, "description":"Maximum number of recordings to return"}
                },
                "required":[]
            },
        ),
        Tool(
            name="find_devisors",
            description=(
                "Search for dance devisors (creators/choreographers) and see their dances. "
                "Returns devisor name, location, and count of dances they created. "
                "Useful for exploring prolific dance creators like John Drewry, Roy Goldring, etc."
            ),
            inputSchema={
                "type":"object",
                "properties":{
                    "name_contains":{"type":["string","null"], "description":"Search by devisor name (case-insensitive substring match)"},
                    "min_dances":{"type":["integer","null"], "minimum":1, "description":"Only return devisors with at least this many dances"},
                    "sort_by":{"type":"string","enum":["dance_count","name"],"default":"dance_count", "description":"Sort by number of dances (most prolific first) or alphabetically by name"},
                    "limit":{"type":"integer","minimum":1,"maximum":100,"default":25, "description":"Maximum number of devisors to return"}
                },
                "required":[]
            },
        ),
        Tool(
            name="find_publications",
            description=(
                "Search for publications (books, leaflets) containing Scottish Country Dances. "
                "Returns publication name, year, RSCDS status, and dance count. "
                "Useful for finding dances in specific books like 'RSCDS Book 1' or exploring a devisor's publications."
            ),
            inputSchema={
                "type":"object",
                "properties":{
                    "name_contains":{"type":["string","null"], "description":"Search by publication name (case-insensitive substring match)"},
                    "rscds_only":{"type":["boolean","null"], "description":"If true, only RSCDS publications; if false, only non-RSCDS; null for all"},
                    "year_from":{"type":["integer","null"], "description":"Publications from this year onwards"},
                    "year_to":{"type":["integer","null"], "description":"Publications up to this year"},
                    "sort_by":{"type":"string","enum":["year","name","dance_count"],"default":"name", "description":"Sort by year, name, or number of dances"},
                    "limit":{"type":"integer","minimum":1,"maximum":100,"default":25, "description":"Maximum number of publications to return"}
                },
                "required":[]
            },
        ),
        Tool(
            name="get_publication_dances",
            description=(
                "Get all dances from a specific publication (book/leaflet). "
                "Returns the dances with their position/number in the publication. "
                "Useful after using find_publications to explore a specific book's contents."
            ),
            inputSchema={
                "type":"object",
                "properties":{
                    "publication_id":{"type":"integer","minimum":1, "description":"The publication database ID"},
                    "limit":{"type":"integer","minimum":1,"maximum":200,"default":100, "description":"Maximum number of dances to return"}
                },
                "required":["publication_id"]
            },
        ),
        Tool(
            name="search_dance_lists",
            description=(
                "Search for dance lists (event programs) from the live SCDDB server. "
                "Dance lists are programs for classes, balls, and functions created by users. "
                "Returns list name, owner, type (class/function/other), date, and item count. "
                "NOTE: This queries the live SCDDB API and requires internet access."
            ),
            inputSchema={
                "type":"object",
                "properties":{
                    "name_contains":{"type":["string","null"], "description":"Search by list name (case-insensitive substring match)"},
                    "owner":{"type":["string","null"], "description":"Filter by list owner's username"},
                    "list_type":{"type":["string","null"], "enum":["function","class","informational","other"], "description":"Filter by list type: function (balls/events), class, informational, or other"},
                    "date_from":{"type":["string","null"], "description":"Lists from this date onwards (YYYY-MM-DD format)"},
                    "date_to":{"type":["string","null"], "description":"Lists up to this date (YYYY-MM-DD format)"},
                    "order_by":{"type":"string","enum":["date","-date","name","owner"],"default":"-date", "description":"Sort order: date (oldest first), -date (newest first), name, or owner"},
                    "limit":{"type":"integer","minimum":1,"maximum":100,"default":20, "description":"Maximum number of lists to return"}
                },
                "required":[]
            },
        ),
        Tool(
            name="get_dance_list_detail",
            description=(
                "Get full details of a specific dance list (event program) including all items. "
                "Returns the list info plus all dances, extras, and timing information. "
                "NOTE: This queries the live SCDDB API and requires internet access."
            ),
            inputSchema={
                "type":"object",
                "properties":{
                    "list_id":{"type":"integer","minimum":1, "description":"The dance list database ID from search_dance_lists"}
                },
                "required":["list_id"]
            },
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent | ImageContent]:
    tool_start_time = time.perf_counter()
    try:
        logger.info("call_tool: %s", name)
        logger.debug("arguments: %s", arguments)
        if name == "find_dances":
            name_contains = arguments.get("name_contains")
            kind = arguments.get("kind")
            metaform_contains = arguments.get("metaform_contains")
            max_bars = arguments.get("max_bars")
            formation_token = arguments.get("formation_token")
            # Support both old and new parameter names for compatibility
            rscds_only = arguments.get("rscds_only") or arguments.get("official_rscds_dances")
            min_intensity = arguments.get("min_intensity")
            max_intensity = arguments.get("max_intensity")
            sort_by_intensity = arguments.get("sort_by_intensity")
            random_variety = arguments.get("random_variety", False)
            limit = int(arguments.get("limit", 25))

            logger.info("find_dances called with: name_contains=%s, kind=%s, metaform_contains=%s, max_bars=%s, formation_token=%s, rscds_only=%s, min_intensity=%s, max_intensity=%s, sort_by_intensity=%s, random_variety=%s, limit=%s", 
                       name_contains, kind, metaform_contains, max_bars, formation_token, rscds_only, min_intensity, max_intensity, sort_by_intensity, random_variety, limit)

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
            if rscds_only is not None:
                if rscds_only:
                    # Only dances published by RSCDS
                    sql += """
                    INNER JOIN dancespublicationsmap dpm ON m.id = dpm.dance_id
                    INNER JOIN publication p ON dpm.publication_id = p.id AND p.rscds = 1
                    """
                else:
                    # Only dances NOT published by RSCDS (exclude any dance that has any RSCDS publication)
                    sql += """
                    WHERE m.id NOT IN (
                        SELECT DISTINCT dpm2.dance_id 
                        FROM dancespublicationsmap dpm2
                        INNER JOIN publication p2 ON dpm2.publication_id = p2.id AND p2.rscds = 1
                    )
                    """
            
            # Add WHERE clause if not already added by RSCDS filtering
            if rscds_only != False:  # False case already adds WHERE clause
                sql += " WHERE 1=1"
            
            args: List[Any] = []
            if name_contains:
                sql += " AND m.name LIKE ? COLLATE NOCASE"; args.append(f"%{name_contains}%")
            if kind:
                sql += " AND m.kind = ?"; args.append(kind)
            if metaform_contains:
                sql += " AND m.metaform LIKE ?"; args.append(f"%{metaform_contains}%")
            if max_bars is not None:
                sql += " AND m.bars <= ?"; args.append(int(max_bars))
            if formation_token:
                sql += " AND t.formation_tokens LIKE ?"; args.append(f"%{formation_token}%")
            if min_intensity is not None:
                sql += " AND d.intensity >= ? AND d.intensity > 0"; args.append(int(min_intensity))
            if max_intensity is not None:
                sql += " AND d.intensity <= ? AND d.intensity > 0"; args.append(int(max_intensity))
            
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

            logger.debug("Executing SQL: %s with args: %s", sql, args)
            query_start = time.perf_counter()
            rows = q(sql, tuple(args))
            query_end = time.perf_counter()
            tool_end = time.perf_counter()
            
            query_time = (query_end - query_start) * 1000
            total_tool_time = (tool_end - tool_start_time) * 1000
            
            logger.info(f"find_dances TOOL PERF: Total={total_tool_time:.2f}ms, MainQuery={query_time:.2f}ms, Results={len(rows)}")
            
            # Log first few results for debugging
            if rows:
                logger.info(f"Sample results: {json.dumps(rows[:3], ensure_ascii=False)}")
            
            return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False))]

        if name == "dance_detail":
            dance_id = int(arguments["dance_id"])
            
            # Time individual queries
            dance_start = time.perf_counter()
            dance = q_one("SELECT * FROM v_metaform WHERE id=?", (dance_id,))
            dance_end = time.perf_counter()
            
            formations_start = time.perf_counter()
            formations = q(
                "SELECT formation_name, formation_tokens FROM v_dance_formations WHERE dance_id=? ORDER BY formation_name",
                (dance_id,),
            )
            formations_end = time.perf_counter()
            
            crib_start = time.perf_counter()
            crib = q_one("SELECT reliability, last_modified, text FROM v_crib_best WHERE dance_id=?", (dance_id,))
            crib_end = time.perf_counter()
            
            # Get publication information including RSCDS status
            pub_start = time.perf_counter()
            publications = q(
                """
                SELECT p.name, p.shortname, p.rscds, dpm.number, dpm.page
                FROM publication p
                JOIN dancespublicationsmap dpm ON p.id = dpm.publication_id
                WHERE dpm.dance_id = ?
                ORDER BY p.rscds DESC, p.name
                """,
                (dance_id,),
            )
            pub_end = time.perf_counter()
            tool_end = time.perf_counter()
            
            # Log timing breakdown
            dance_time = (dance_end - dance_start) * 1000
            formations_time = (formations_end - formations_start) * 1000
            crib_time = (crib_end - crib_start) * 1000
            pub_time = (pub_end - pub_start) * 1000
            total_tool_time = (tool_end - tool_start_time) * 1000
            
            logger.info(f"dance_detail TOOL PERF: Total={total_tool_time:.2f}ms (Dance={dance_time:.2f}ms, Formations={formations_time:.2f}ms, Crib={crib_time:.2f}ms, Pubs={pub_time:.2f}ms)")
            
            out = {"dance": dance, "formations": formations, "crib": crib, "publications": publications}
            return [TextContent(type="text", text=json.dumps(out, ensure_ascii=False))]

        if name == "search_cribs":
            query = str(arguments["query"])
            limit = int(arguments.get("limit", 20))
            
            search_start = time.perf_counter()
            rows = q(
                """
                SELECT d.id, d.name, d.kind, d.metaform, d.bars
                FROM fts_cribs f
                JOIN v_metaform d ON d.id = f.dance_id
                WHERE fts_cribs MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )
            search_end = time.perf_counter()
            tool_end = time.perf_counter()
            
            search_time = (search_end - search_start) * 1000
            total_tool_time = (tool_end - tool_start_time) * 1000
            
            logger.info(f"search_cribs TOOL PERF: Total={total_tool_time:.2f}ms, FTSQuery={search_time:.2f}ms, Results={len(rows)}")
            return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False))]

        if name == "list_formations":
            name_contains = arguments.get("name_contains")
            sort_by = arguments.get("sort_by", "popularity")
            limit = int(arguments.get("limit", 50))
            
            logger.info("list_formations called with: name_contains=%s, sort_by=%s, limit=%s", 
                       name_contains, sort_by, limit)
            
            # Build SQL query with optional name filtering and usage count
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
            
            logger.debug("Executing SQL: %s with args: %s", sql, args)
            query_start = time.perf_counter()
            rows = q(sql, tuple(args))
            query_end = time.perf_counter()
            tool_end = time.perf_counter()
            
            query_time = (query_end - query_start) * 1000
            total_tool_time = (tool_end - tool_start_time) * 1000
            
            logger.info(f"list_formations TOOL PERF: Total={total_tool_time:.2f}ms, Query={query_time:.2f}ms, Results={len(rows)}")
            return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False))]

        if name == "find_videos":
            dance_id = arguments.get("dance_id")
            dance_name = arguments.get("dance_name")
            editors_pick = arguments.get("editors_pick")
            limit = int(arguments.get("limit", 10))
            
            logger.info("find_videos called with: dance_id=%s, dance_name=%s, editors_pick=%s, limit=%s",
                       dance_id, dance_name, editors_pick, limit)
            
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
            
            query_start = time.perf_counter()
            rows = q(sql, tuple(args))
            query_end = time.perf_counter()
            
            # Add YouTube URL to each result
            for row in rows:
                if row.get("youtube_id"):
                    row["youtube_url"] = f"https://www.youtube.com/watch?v={row['youtube_id']}"
            
            tool_end = time.perf_counter()
            query_time = (query_end - query_start) * 1000
            total_tool_time = (tool_end - tool_start_time) * 1000
            
            logger.info(f"find_videos TOOL PERF: Total={total_tool_time:.2f}ms, Query={query_time:.2f}ms, Results={len(rows)}")
            return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False))]

        if name == "find_recordings":
            dance_id = arguments.get("dance_id")
            dance_name = arguments.get("dance_name")
            recording_name = arguments.get("recording_name")
            artist_name = arguments.get("artist_name")
            album_name = arguments.get("album_name")
            limit = int(arguments.get("limit", 20))
            
            logger.info("find_recordings called with: dance_id=%s, dance_name=%s, recording_name=%s, artist_name=%s, album_name=%s, limit=%s",
                       dance_id, dance_name, recording_name, artist_name, album_name, limit)
            
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
            
            query_start = time.perf_counter()
            rows = q(sql, tuple(args))
            query_end = time.perf_counter()
            tool_end = time.perf_counter()
            
            query_time = (query_end - query_start) * 1000
            total_tool_time = (tool_end - tool_start_time) * 1000
            
            logger.info(f"find_recordings TOOL PERF: Total={total_tool_time:.2f}ms, Query={query_time:.2f}ms, Results={len(rows)}")
            return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False))]

        if name == "find_devisors":
            name_contains = arguments.get("name_contains")
            min_dances = arguments.get("min_dances")
            sort_by = arguments.get("sort_by", "dance_count")
            limit = int(arguments.get("limit", 25))
            
            logger.info("find_devisors called with: name_contains=%s, min_dances=%s, sort_by=%s, limit=%s",
                       name_contains, min_dances, sort_by, limit)
            
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
            
            query_start = time.perf_counter()
            rows = q(sql, tuple(args))
            query_end = time.perf_counter()
            tool_end = time.perf_counter()
            
            query_time = (query_end - query_start) * 1000
            total_tool_time = (tool_end - tool_start_time) * 1000
            
            logger.info(f"find_devisors TOOL PERF: Total={total_tool_time:.2f}ms, Query={query_time:.2f}ms, Results={len(rows)}")
            return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False))]

        if name == "find_publications":
            name_contains = arguments.get("name_contains")
            rscds_only = arguments.get("rscds_only")
            year_from = arguments.get("year_from")
            year_to = arguments.get("year_to")
            sort_by = arguments.get("sort_by", "name")
            limit = int(arguments.get("limit", 25))
            
            logger.info("find_publications called with: name_contains=%s, rscds_only=%s, year_from=%s, year_to=%s, sort_by=%s, limit=%s",
                       name_contains, rscds_only, year_from, year_to, sort_by, limit)
            
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
            
            query_start = time.perf_counter()
            rows = q(sql, tuple(args))
            query_end = time.perf_counter()
            tool_end = time.perf_counter()
            
            query_time = (query_end - query_start) * 1000
            total_tool_time = (tool_end - tool_start_time) * 1000
            
            logger.info(f"find_publications TOOL PERF: Total={total_tool_time:.2f}ms, Query={query_time:.2f}ms, Results={len(rows)}")
            return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False))]

        if name == "get_publication_dances":
            publication_id = int(arguments["publication_id"])
            limit = int(arguments.get("limit", 100))
            
            logger.info("get_publication_dances called with: publication_id=%s, limit=%s", publication_id, limit)
            
            # Get publication info
            pub_info = q_one("SELECT id, name, shortname, year, rscds FROM publication WHERE id = ?", (publication_id,))
            
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
            
            query_start = time.perf_counter()
            rows = q(sql, (publication_id, limit))
            query_end = time.perf_counter()
            tool_end = time.perf_counter()
            
            query_time = (query_end - query_start) * 1000
            total_tool_time = (tool_end - tool_start_time) * 1000
            
            result = {"publication": pub_info, "dances": rows}
            
            logger.info(f"get_publication_dances TOOL PERF: Total={total_tool_time:.2f}ms, Query={query_time:.2f}ms, Results={len(rows)}")
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

        if name == "search_dance_lists":
            name_contains = arguments.get("name_contains")
            owner = arguments.get("owner")
            list_type = arguments.get("list_type")
            date_from = arguments.get("date_from")
            date_to = arguments.get("date_to")
            order_by = arguments.get("order_by", "-date")
            limit = int(arguments.get("limit", 20))
            
            logger.info("search_dance_lists called with: name_contains=%s, owner=%s, list_type=%s, date_from=%s, date_to=%s, order_by=%s, limit=%s",
                       name_contains, owner, list_type, date_from, date_to, order_by, limit)
            
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
                api_start = time.perf_counter()
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(base_url, params=params)
                    response.raise_for_status()
                    data = response.json()
                api_end = time.perf_counter()
                tool_end = time.perf_counter()
                
                api_time = (api_end - api_start) * 1000
                total_tool_time = (tool_end - tool_start_time) * 1000
                
                items = data.get("items", [])
                # Add the correct URL for each dance list (uses /dd/list/ not /dd/dance/)
                for item in items:
                    if item.get("id"):
                        item["url"] = f"https://my.strathspey.org/dd/list/{item['id']}/"
                
                logger.info(f"search_dance_lists TOOL PERF: Total={total_tool_time:.2f}ms, API={api_time:.2f}ms, Results={len(items)}")
                return [TextContent(type="text", text=json.dumps(items, ensure_ascii=False))]
            except httpx.HTTPError as e:
                logger.error(f"HTTP error querying dance lists API: {e}")
                return [TextContent(type="text", text=json.dumps({"error": f"Failed to query SCDDB API: {str(e)}"}))]

        if name == "get_dance_list_detail":
            list_id = int(arguments["list_id"])
            
            logger.info("get_dance_list_detail called with: list_id=%s", list_id)
            
            url = f"https://my.strathspey.org/dd/api/lists/v1/list/{list_id}"
            
            try:
                api_start = time.perf_counter()
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                api_end = time.perf_counter()
                tool_end = time.perf_counter()
                
                api_time = (api_end - api_start) * 1000
                total_tool_time = (tool_end - tool_start_time) * 1000
                
                # Add the correct URL for the dance list (uses /dd/list/ not /dd/dance/)
                data["url"] = f"https://my.strathspey.org/dd/list/{list_id}/"
                
                logger.info(f"get_dance_list_detail TOOL PERF: Total={total_tool_time:.2f}ms, API={api_time:.2f}ms")
                return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False))]
            except httpx.HTTPError as e:
                logger.error(f"HTTP error querying dance list detail API: {e}")
                return [TextContent(type="text", text=json.dumps({"error": f"Failed to query SCDDB API: {str(e)}"}))]

        # Unknown tool
        tool_end = time.perf_counter()
        total_tool_time = (tool_end - tool_start_time) * 1000
        logger.warning(f"Unknown tool {name} - Total time: {total_tool_time:.2f}ms")
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool {name}"}))]
    except Exception as e:
        tool_end = time.perf_counter()
        total_tool_time = (tool_end - tool_start_time) * 1000
        logger.exception(f"Error in call_tool {name} after {total_tool_time:.2f}ms")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

# Optional: allow client to set server-side logging level
@server.set_logging_level()
async def set_logging_level(level: types.LoggingLevel) -> None:
    try:
        val = getattr(level, "value", None) or getattr(level, "name", None) or str(level)
        s = str(val).lower()
        mapping = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "notice": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
            "alert": logging.CRITICAL,
            "emergency": logging.CRITICAL,
        }
        logging.getLogger().setLevel(mapping.get(s, logging.INFO))
        logger.info("Logging level set to %s", s)
    except Exception:
        logger.exception("Failed to set logging level")

async def run_stdio():
    # Build InitializationOptions matching current server capabilities
    notif = NotificationOptions(
        prompts_changed=False,
        resources_changed=False,
        tools_changed=False,
    )
    capabilities = server.get_capabilities(notif, experimental_capabilities={})
    logger.info("Starting stdio server with capabilities: %s", capabilities)
    init_opts = InitializationOptions(
        server_name="scddb",
        server_version="0.1.0",
        capabilities=capabilities,
        instructions=None,
    )
    try:
        async with stdio_server() as (read, write):
            # Extra diagnostics to understand initialize handshake issues
            logger.debug("stdio_server context opened; running server.run …")
            print("[scddb] stdio_server opened; entering server.run", file=sys.stderr, flush=True)
            # Provide explicit initialization options, bubble exceptions for diagnosis
            await server.run(read, write, initialization_options=init_opts, raise_exceptions=True)
            logger.debug("server.run returned (session closed)")
    except Exception:
        logger.exception("server.run raised an exception")

def main():
    # quick sanity check that DB exists
    if not os.path.exists(DB_PATH):
        print(json.dumps({"error": f"DB not found at {DB_PATH}. Run refresh_scddb.py first or set SCDDB_SQLITE."}))
        raise SystemExit(2)
    asyncio.run(run_stdio())

if __name__ == "__main__":
    main()
