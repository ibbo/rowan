from typing import Dict, List, Any, Optional
from datetime import datetime
import time
import sys
import os
import json
import re
from pathlib import Path
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.tools import tool

class MCPSCDDBClient:
    """Client wrapper for the MCP SCDDB server with connection pooling."""
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._setup_complete = False
        self._connection_pool = []
        self._pool_lock = asyncio.Lock()
        self._max_connections = 3  # Keep a small pool of connections
    
    async def setup(self):
        """Initialize the MCP connection."""
        setup_start = time.perf_counter()
        if self._setup_complete:
            setup_end = time.perf_counter()
            print(f"DEBUG: MCP setup skipped (already complete) - {(setup_end - setup_start) * 1000:.2f}ms", file=sys.stderr)
            return
            
        # Use the actual database
        db_path = os.environ.get("SCDDB_SQLITE", "data/scddb/scddb.sqlite")
        db_path = str(Path(db_path).resolve())
        
        if not Path(db_path).exists():
            raise RuntimeError(f"Database not found at {db_path}. Run refresh_scddb.py first.")
        
        # Server script path
        server_script = str((Path(__file__).parent / "mcp_scddb_server.py").resolve())
        if not Path(server_script).exists():
            raise RuntimeError(f"Server script not found: {server_script}")
        
        # Setup server parameters
        self.params = StdioServerParameters(
            command=sys.executable,
            args=[server_script],
            env={
                "SCDDB_SQLITE": db_path,
                "SCDDB_LOG_LEVEL": "WARNING",  # Reduce noise
            },
        )
        self._setup_complete = True
        setup_end = time.perf_counter()
        print(f"DEBUG: MCP setup completed - {(setup_end - setup_start) * 1000:.2f}ms", file=sys.stderr)
    
    async def _get_pooled_session(self):
        """Get a session from the pool or create a new one."""
        async with self._pool_lock:
            # Try to reuse an existing session from the pool
            if self._connection_pool:
                session_info = self._connection_pool.pop()
                print(f"DEBUG: Reusing pooled MCP session", file=sys.stderr)
                return session_info
            
            # Create new session if pool is empty
            session_start = time.perf_counter()
            print(f"DEBUG: Creating new MCP session for pool", file=sys.stderr)
            
            # Create session context that we can reuse
            from mcp.client.stdio import stdio_client
            client_context = stdio_client(self.params)
            read_stream, write_stream = await client_context.__aenter__()
            
            session_context = ClientSession(read_stream, write_stream)
            session = await session_context.__aenter__()
            
            init_start = time.perf_counter()
            await session.initialize()
            init_end = time.perf_counter()
            
            total_time = (init_end - session_start) * 1000
            init_time = (init_end - init_start) * 1000
            print(f"DEBUG: New session created - Total: {total_time:.2f}ms (init: {init_time:.2f}ms)", file=sys.stderr)
            
            return {
                'session': session,
                'session_context': session_context,
                'client_context': client_context,
                'created_at': time.time()
            }
    
    async def _return_session_to_pool(self, session_info):
        """Return a session to the pool for reuse."""
        async with self._pool_lock:
            # Check if session is still fresh (less than 5 minutes old)
            if time.time() - session_info['created_at'] < 300 and len(self._connection_pool) < self._max_connections:
                self._connection_pool.append(session_info)
                print(f"DEBUG: Returned session to pool (pool size: {len(self._connection_pool)})", file=sys.stderr)
            else:
                # Session too old or pool full - close it
                try:
                    await session_info['session_context'].__aexit__(None, None, None)
                    await session_info['client_context'].__aexit__(None, None, None)
                except Exception as e:
                    print(f"DEBUG: Error closing session: {e}", file=sys.stderr)
                print(f"DEBUG: Closed expired/excess session", file=sys.stderr)
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Call an MCP tool using connection pooling for better performance."""
        call_start = time.perf_counter()
        print(f"DEBUG: Starting MCP call_tool '{name}' with args: {arguments}", file=sys.stderr)
        
        session_info = None
        returned_to_pool = False
        try:
            # Get session from pool
            session_info = await self._get_pooled_session()
            session = session_info['session']
            
            # Make the actual tool call
            tool_call_start = time.perf_counter()
            result = await session.call_tool(name=name, arguments=arguments)
            tool_call_end = time.perf_counter()
            print(f"DEBUG: MCP tool call '{name}' executed - {(tool_call_end - tool_call_start) * 1000:.2f}ms", file=sys.stderr)
            
            # Extract text content from MCP response
            content = []
            for block in result.content:
                if hasattr(block, 'text'):
                    # Parse JSON if it looks like JSON
                    text = block.text
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, list):
                            content.extend(parsed)
                        else:
                            content.append(parsed)
                    except json.JSONDecodeError:
                        content.append({"text": text})
            
            # Return session to pool for reuse
            if session_info:
                await self._return_session_to_pool(session_info)
                returned_to_pool = True
            
            call_end = time.perf_counter()
            total_time = (call_end - call_start) * 1000
            print(f"DEBUG: MCP call_tool '{name}' completed - Total: {total_time:.2f}ms", file=sys.stderr)
            return content
            
        except asyncio.CancelledError:
            # Ensure session cleanup even when the task is cancelled
            if session_info and not returned_to_pool:
                try:
                    await session_info['session_context'].__aexit__(None, None, None)
                    await session_info['client_context'].__aexit__(None, None, None)
                except Exception as cleanup_err:
                    print(f"DEBUG: Cancellation cleanup error: {cleanup_err}", file=sys.stderr)
            print(f"DEBUG: MCP call_tool '{name}' cancelled", file=sys.stderr)
            raise
            
        except Exception as e:
            call_end = time.perf_counter()
            total_time = (call_end - call_start) * 1000
            print(f"DEBUG: MCP call_tool '{name}' failed after {total_time:.2f}ms - Error: {e}", file=sys.stderr)
            
            # If session failed, don't return it to pool - let it get cleaned up
            if session_info and not returned_to_pool:
                try:
                    await session_info['session_context'].__aexit__(None, None, None)
                    await session_info['client_context'].__aexit__(None, None, None)
                except Exception as e:
                    print(f"DEBUG: Error cleaning up failed session: {e}", file=sys.stderr)
            
            return [{"error": str(e)}]
    
    async def close(self):
        """Clean up all pooled sessions."""
        async with self._pool_lock:
            for session_info in self._connection_pool:
                try:
                    await session_info['session_context'].__aexit__(None, None, None)
                    await session_info['client_context'].__aexit__(None, None, None)
                except:
                    pass
            self._connection_pool.clear()
            print(f"DEBUG: All MCP sessions closed", file=sys.stderr)


# Global MCP client instance
mcp_client = MCPSCDDBClient()

# Note: Cleanup should be done explicitly in async context
# Using atexit with asyncio.run() causes context manager issues

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
    
    ⚠️ IMPORTANT DISTINCTION - Dance Types vs. Formations:
    - kind='Reel'/'Jig'/'Strathspey' refers to DANCE TYPE (music/tempo), NOT dance figures!
    - To find dances with formations like "reel of three", "poussette", etc., use search_cribs instead!
    - "reel of three" is a FORMATION (figure), not a dance type
    
    IMPORTANT SYNTAX EXAMPLES:
    - kind: Use exact values like 'Reel', 'Jig', 'Strathspey', 'Hornpipe', 'Waltz', 'March'
      ⚠️ DO NOT use kind='Reel' when looking for "reel of three" formations!
    - metaform_contains: Use patterns like 'Longwise 3 3C', 'Longwise 4 3C', 'Circle 3C', 'Square 3C', 'Longwise 2 2C'
      (NOTE: For 3 couples longwise, use 'Longwise 3 3C' or 'Longwise 4 3C', NOT 'Longwise 3C')
      (NOTE: metaform describes SET FORMATION, not dance figures like "reel of three")
    - formation_token: Use specific tokens like 'POUSS;3C;', 'ALLMND;3C;', 'HR;3P;', 'R&L;3C;', 'REEL;R3;'
      (These are technical formation codes - for "reel of three" use search_cribs instead)
    
    FILTER BY DIFFICULTY:
    - Use min_intensity and max_intensity to filter by difficulty (1-100 scale)
    - Easy dances: max_intensity=40
    - Medium dances: min_intensity=40, max_intensity=70
    - Hard dances: min_intensity=70
    - Use sort_by_intensity='asc' for easiest first, 'desc' for hardest first
    
    Args:
        name_contains: Substring to search for in dance name (case-insensitive)
        kind: Dance TYPE - EXACT VALUES: 'Jig', 'Reel', 'Strathspey', 'Hornpipe', 'Waltz', 'March'
              ⚠️ This is music/tempo type, NOT dance figures! Don't use kind='Reel' for "reel of three" formations!
        metaform_contains: SET formation pattern - EXAMPLES: 'Longwise 3 3C', 'Longwise 4 3C', 'Circle 3C', 'Square 3C'
                           ⚠️ This is SET FORMATION, not dance figures! Don't use for "reel of three" - use search_cribs instead!
        max_bars: Maximum number of bars (per repeat) - common values: 32, 48, 64
        formation_token: Technical formation code - EXAMPLES: 'POUSS;3C;', 'ALLMND;3C;', 'REEL;R3;' (advanced use)
        official_rscds_dances: FILTER BY PUBLICATION - True=only official RSCDS published dances, False=only community/non-RSCDS dances, None=all dances
        min_intensity: FILTER BY DIFFICULTY - Minimum difficulty level (1-100, where 1=easiest, 100=hardest)
        max_intensity: FILTER BY DIFFICULTY - Maximum difficulty level (1-100, where 1=easiest, 100=hardest)
        sort_by_intensity: Sort by difficulty - 'asc' for easiest first, 'desc' for hardest first
        random_variety: DEFAULT=True for variety! Set to True for randomized diverse results, False for alphabetical order.
        limit: Maximum number of results (1-200, default 25)
    
    Returns:
        List of dance dictionaries with id, name, kind, metaform, bars, progression, and intensity (if filtering by difficulty)
    """
    func_start = time.perf_counter()
    print(f"DEBUG: find_dances tool called", file=sys.stderr)
    
    setup_start = time.perf_counter()
    await mcp_client.setup()
    setup_end = time.perf_counter()
    print(f"DEBUG: find_dances setup - {(setup_end - setup_start) * 1000:.2f}ms", file=sys.stderr)
    
    arguments = {"limit": limit}
    if name_contains:
        arguments["name_contains"] = name_contains
    if kind:
        arguments["kind"] = kind
    if metaform_contains:
        arguments["metaform_contains"] = metaform_contains
    if max_bars:
        arguments["max_bars"] = max_bars
    if formation_token:
        arguments["formation_token"] = formation_token
    if official_rscds_dances is not None:
        arguments["official_rscds_dances"] = official_rscds_dances
    if min_intensity is not None:
        arguments["min_intensity"] = min_intensity
    if max_intensity is not None:
        arguments["max_intensity"] = max_intensity
    if sort_by_intensity is not None:
        arguments["sort_by_intensity"] = sort_by_intensity
    if random_variety is not None:
        arguments["random_variety"] = random_variety
    
    print(f"DEBUG: Calling find_dances with arguments: {arguments}", file=sys.stderr)
    tool_call_start = time.perf_counter()
    result = await mcp_client.call_tool("find_dances", arguments)
    tool_call_end = time.perf_counter()
    func_end = time.perf_counter()
    
    tool_call_time = (tool_call_end - tool_call_start) * 1000
    total_func_time = (func_end - func_start) * 1000
    
    print(f"DEBUG: find_dances returned {len(result)} results - Tool call: {tool_call_time:.2f}ms, Total: {total_func_time:.2f}ms", file=sys.stderr)
    
    return result


@tool
async def get_dance_detail(dance_id: int) -> Dict[str, Any]:
    """
    Get detailed information about a specific dance including metaform, formations, and crib.
    
    Args:
        dance_id: The ID of the dance to get details for
    
    Returns:
        Dictionary with dance details, formations, and best crib text
    """
    func_start = time.perf_counter()
    print(f"DEBUG: get_dance_detail tool called for dance_id: {dance_id}", file=sys.stderr)
    
    await mcp_client.setup()
    
    result = await mcp_client.call_tool("dance_detail", {"dance_id": dance_id})
    func_end = time.perf_counter()
    
    total_time = (func_end - func_start) * 1000
    print(f"DEBUG: get_dance_detail completed - {total_time:.2f}ms", file=sys.stderr)
    
    return result[0] if result else {}


@tool
async def search_cribs(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Full-text search the dance cribs for specific moves, terms, or descriptions.
    
    ⚠️ USE THIS TOOL to find dances with specific FORMATIONS/FIGURES like:
    - "reel of three" or "reel of 3" (NOT the same as Reel dance type!)
    - "poussette"
    - "allemande"
    - "rights and lefts"
    - "set and turn"
    - Any other dance figures or movements
    
    This is the PRIMARY tool for finding dances containing specific formations.
    Don't use find_dances with kind='Reel' when looking for "reel of three" formations!
    
    Args:
        query: Search query. Common searches: "reel of three", "poussette", "allemande"
               Supports FTS5 syntax (e.g., 'poussette OR allemande', 'turn AND right')
        limit: Maximum number of results (1-200, default 20)
    
    Returns:
        List of dances that match the search query in their cribs
    """
    func_start = time.perf_counter()
    print(f"DEBUG: search_cribs tool called with query: '{query}'", file=sys.stderr)
    
    await mcp_client.setup()
    
    result = await mcp_client.call_tool("search_cribs", {"query": query, "limit": limit})
    func_end = time.perf_counter()
    
    total_time = (func_end - func_start) * 1000
    print(f"DEBUG: search_cribs completed - {total_time:.2f}ms", file=sys.stderr)
    
    return result


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
        sort_by: Sort results by 'popularity' (most used formations first) or 'alphabetical' (default: popularity)
        limit: Maximum number of formations to return (1-500, default 50)
    
    Returns:
        List of formations with their names, tokens, and usage counts
    """
    func_start = time.perf_counter()
    print(f"DEBUG: list_formations tool called with name_contains: '{name_contains}', sort_by: '{sort_by}', limit: {limit}", file=sys.stderr)
    
    await mcp_client.setup()
    
    arguments = {"sort_by": sort_by, "limit": limit}
    if name_contains:
        arguments["name_contains"] = name_contains
    
    result = await mcp_client.call_tool("list_formations", arguments)
    func_end = time.perf_counter()
    
    total_time = (func_end - func_start) * 1000
    print(f"DEBUG: list_formations completed - {total_time:.2f}ms", file=sys.stderr)
    
    return result


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
            print(f"⚠️  Manual index not found: {index_path}", file=sys.stderr)
            return False
        
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                self.index = json.load(f)
            self._loaded = True
            print(f"✅ Loaded RSCDS manual knowledge base ({len(self.index.get('sections', {}))} sections)", file=sys.stderr)
            return True
        except Exception as e:
            print(f"❌ Error loading manual index: {e}", file=sys.stderr)
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
            print(f"❌ Error loading chapter {chapter_num}: {e}", file=sys.stderr)
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
    
    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """Search for sections matching a query.
        
        Uses simple substring matching on titles - not vector similarity.
        For precise lookups, use lookup() instead.
        
        Args:
            query: Search query
            limit: Max results to return
            
        Returns:
            List of matching section summaries
        """
        if not self._loaded:
            if not self.load():
                return []
        
        query_lower = query.lower()
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
    
    header = f"📚 **{section_num} {title}**"
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
    func_start = time.perf_counter()
    print(f"DEBUG: find_videos tool called", file=sys.stderr)
    
    await mcp_client.setup()
    
    arguments = {"limit": limit}
    if dance_id is not None:
        arguments["dance_id"] = dance_id
    if dance_name:
        arguments["dance_name"] = dance_name
    if editors_pick is not None:
        arguments["editors_pick"] = editors_pick
    
    result = await mcp_client.call_tool("find_videos", arguments)
    func_end = time.perf_counter()
    
    total_time = (func_end - func_start) * 1000
    print(f"DEBUG: find_videos completed - {total_time:.2f}ms, {len(result)} results", file=sys.stderr)
    
    return result


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
        List of recording dictionaries with recording_name, artist, album, duration_seconds, dance_name, etc.
    """
    func_start = time.perf_counter()
    print(f"DEBUG: find_recordings tool called", file=sys.stderr)
    
    await mcp_client.setup()
    
    arguments = {"limit": limit}
    if dance_id is not None:
        arguments["dance_id"] = dance_id
    if dance_name:
        arguments["dance_name"] = dance_name
    if recording_name:
        arguments["recording_name"] = recording_name
    if artist_name:
        arguments["artist_name"] = artist_name
    if album_name:
        arguments["album_name"] = album_name
    
    result = await mcp_client.call_tool("find_recordings", arguments)
    func_end = time.perf_counter()
    
    total_time = (func_end - func_start) * 1000
    print(f"DEBUG: find_recordings completed - {total_time:.2f}ms, {len(result)} results", file=sys.stderr)
    
    return result


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
    func_start = time.perf_counter()
    print(f"DEBUG: find_devisors tool called", file=sys.stderr)
    
    await mcp_client.setup()
    
    arguments = {"sort_by": sort_by, "limit": limit}
    if name_contains:
        arguments["name_contains"] = name_contains
    if min_dances is not None:
        arguments["min_dances"] = min_dances
    
    result = await mcp_client.call_tool("find_devisors", arguments)
    func_end = time.perf_counter()
    
    total_time = (func_end - func_start) * 1000
    print(f"DEBUG: find_devisors completed - {total_time:.2f}ms, {len(result)} results", file=sys.stderr)
    
    return result


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
    func_start = time.perf_counter()
    print(f"DEBUG: find_publications tool called", file=sys.stderr)
    
    await mcp_client.setup()
    
    arguments = {"sort_by": sort_by, "limit": limit}
    if name_contains:
        arguments["name_contains"] = name_contains
    if rscds_only is not None:
        arguments["rscds_only"] = rscds_only
    if year_from is not None:
        arguments["year_from"] = year_from
    if year_to is not None:
        arguments["year_to"] = year_to
    
    result = await mcp_client.call_tool("find_publications", arguments)
    func_end = time.perf_counter()
    
    total_time = (func_end - func_start) * 1000
    print(f"DEBUG: find_publications completed - {total_time:.2f}ms, {len(result)} results", file=sys.stderr)
    
    return result


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
        Dictionary with 'publication' info and 'dances' list containing dance_id, dance_name, kind, bars, position_in_book
    """
    func_start = time.perf_counter()
    print(f"DEBUG: get_publication_dances tool called for publication_id: {publication_id}", file=sys.stderr)
    
    await mcp_client.setup()
    
    result = await mcp_client.call_tool("get_publication_dances", {"publication_id": publication_id, "limit": limit})
    func_end = time.perf_counter()
    
    total_time = (func_end - func_start) * 1000
    print(f"DEBUG: get_publication_dances completed - {total_time:.2f}ms", file=sys.stderr)
    
    return result[0] if result else {}


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
    
    **TODAY'S DATE: {current_date}** - Use this to interpret relative date references like "upcoming", "this week", "next month", etc.
    
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
    func_start = time.perf_counter()
    print(f"DEBUG: search_dance_lists tool called", file=sys.stderr)
    
    await mcp_client.setup()
    
    arguments = {"order_by": order_by, "limit": limit}
    if name_contains:
        arguments["name_contains"] = name_contains
    if owner:
        arguments["owner"] = owner
    if list_type:
        arguments["list_type"] = list_type
    if date_from:
        arguments["date_from"] = date_from
    if date_to:
        arguments["date_to"] = date_to
    
    result = await mcp_client.call_tool("search_dance_lists", arguments)
    func_end = time.perf_counter()
    
    total_time = (func_end - func_start) * 1000
    print(f"DEBUG: search_dance_lists completed - {total_time:.2f}ms, {len(result)} results", file=sys.stderr)
    
    return result

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
        Dictionary with list info (name, owner, type, date, notes) and 'items' array containing all dances/entries
    """
    func_start = time.perf_counter()
    print(f"DEBUG: get_dance_list_detail tool called for list_id: {list_id}", file=sys.stderr)
    
    await mcp_client.setup()
    
    result = await mcp_client.call_tool("get_dance_list_detail", {"list_id": list_id})
    func_end = time.perf_counter()
    
    total_time = (func_end - func_start) * 1000
    print(f"DEBUG: get_dance_list_detail completed - {total_time:.2f}ms", file=sys.stderr)
    
    return result[0] if result else {}


@tool
async def search_manual(
    query: str,
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
        query: The search query. Can be:
               - A formation/step name: "skip change of step", "poussette", "pas de basque"
               - A section number: "5.4.1", "6.21"
               - A topic: "teaching music", "history of scottish dancing"
        num_results: Number of relevant sections to return (default 3, max 10)
    
    Returns:
        Formatted string with relevant sections from the RSCDS manual, including page numbers
    """
    func_start = time.perf_counter()
    print(f"\n{'='*80}", file=sys.stderr)
    print(f"DEBUG: search_manual tool called", file=sys.stderr)
    print(f"  Query: '{query}'", file=sys.stderr)
    
    # Get the knowledge base
    kb = _get_manual_kb()
    if kb is None or not kb._loaded:
        return "⚠️  RSCDS manual knowledge base not available. Run 'uv run extract_manual_structured.py' to create it."
    
    # Limit num_results to reasonable range
    num_results = max(1, min(num_results, 10))
    
    try:
        # First, try direct lookup by name/alias (most precise)
        section = kb.lookup(query)
        
        if section:
            # Found exact match!
            print(f"  ✅ Direct lookup found: {section['section']} - {section['title']}", file=sys.stderr)
            response = _format_section_result(section)
            
            func_end = time.perf_counter()
            total_time = (func_end - func_start) * 1000
            print(f"DEBUG: search_manual completed (direct lookup) - {total_time:.2f}ms", file=sys.stderr)
            
            return response
        
        # No exact match - try fuzzy search
        print(f"  No direct match, trying search...", file=sys.stderr)
        search_results = kb.search(query, limit=num_results)
        
        if not search_results:
            return f"No relevant information found in the RSCDS manual for: '{query}'\n\nTry using specific terms like:\n- Formation names: 'skip change of step', 'poussette', 'rights and lefts'\n- Step names: 'pas de basque', 'slip step'\n- Topics: 'music for teaching', 'history of dancing'"
        
        # Format search results
        lines = [f"📚 **RSCDS Manual - Search results for '{query}':**", ""]
        
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
        
        func_end = time.perf_counter()
        total_time = (func_end - func_start) * 1000
        print(f"DEBUG: search_manual completed (search) - {total_time:.2f}ms, {len(search_results)} results", file=sys.stderr)
        
        return "\n".join(lines)
        
    except Exception as e:
        print(f"❌ Error searching RSCDS manual: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return f"Error searching RSCDS manual: {str(e)}"

