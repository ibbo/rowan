#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import logging
import sqlite3
import random
from typing import Any, Dict, List, Optional

from mcp.server import Server, InitializationOptions, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent  # TextContent used for outputs
import mcp.types as types

# --- Config ---
DB_PATH = os.environ.get("SCDDB_SQLITE", "data/scddb/scddb.sqlite")

# --- DB helpers ---
def q(sql: str, args: tuple = ()) -> List[Dict[str, Any]]:
    con = sqlite3.connect(DB_PATH)
    try:
        con.row_factory = sqlite3.Row
        cur = con.execute(sql, args)
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()

def q_one(sql: str, args: tuple = ()) -> Optional[Dict[str, Any]]:
    con = sqlite3.connect(DB_PATH)
    try:
        con.row_factory = sqlite3.Row
        cur = con.execute(sql, args)
        row = cur.fetchone()
        return dict(row) if row else None
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
                "Use 'random_variety=true' for varied results instead of alphabetical order."
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
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent | ImageContent]:
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
            random_variety = arguments.get("random_variety", False)
            limit = int(arguments.get("limit", 25))

            logger.info("find_dances called with: name_contains=%s, kind=%s, metaform_contains=%s, max_bars=%s, formation_token=%s, rscds_only=%s, random_variety=%s, limit=%s", 
                       name_contains, kind, metaform_contains, max_bars, formation_token, rscds_only, random_variety, limit)

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
            
            # Add ordering - random or alphabetical
            if random_variety:
                sql += " ORDER BY RANDOM() LIMIT ?"
            else:
                sql += " ORDER BY m.name LIMIT ?"
            args.append(limit)

            logger.debug("Executing SQL: %s with args: %s", sql, args)
            rows = q(sql, tuple(args))
            logger.info("find_dances returned %d results", len(rows))
            return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False))]

        if name == "dance_detail":
            dance_id = int(arguments["dance_id"])
            dance = q_one("SELECT * FROM v_metaform WHERE id=?", (dance_id,))
            formations = q(
                "SELECT formation_name, formation_tokens FROM v_dance_formations WHERE dance_id=? ORDER BY formation_name",
                (dance_id,),
            )
            crib = q_one("SELECT reliability, last_modified, text FROM v_crib_best WHERE dance_id=?", (dance_id,))
            
            # Get publication information including RSCDS status
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
            
            out = {"dance": dance, "formations": formations, "crib": crib, "publications": publications}
            return [TextContent(type="text", text=json.dumps(out, ensure_ascii=False))]

        if name == "search_cribs":
            query = str(arguments["query"])
            limit = int(arguments.get("limit", 20))
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
            return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False))]

        # Unknown tool
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool {name}"}))]
    except Exception as e:
        logger.exception("Error in call_tool")
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
