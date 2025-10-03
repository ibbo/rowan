from typing import Dict, List, Any, Optional
import time
import sys
import os
import json
from pathlib import Path
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

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
    
    IMPORTANT SYNTAX EXAMPLES:
    - kind: Use exact values like 'Reel', 'Jig', 'Strathspey', 'Hornpipe', 'Waltz', 'March'
    - metaform_contains: Use patterns like 'Longwise 3 3C', 'Longwise 4 3C', 'Circle 3C', 'Square 3C', 'Longwise 2 2C'
      (NOTE: For 3 couples longwise, use 'Longwise 3 3C' or 'Longwise 4 3C', NOT 'Longwise 3C')
    - formation_token: Use specific tokens like 'POUSS;3C;', 'ALLMND;3C;', 'HR;3P;', 'R&L;3C;', 'REEL;ACROSS;R3;'
      (These are technical formation codes - usually better to use metaform_contains instead)
    
    FILTER BY DIFFICULTY:
    - Use min_intensity and max_intensity to filter by difficulty (1-100 scale)
    - Easy dances: max_intensity=40
    - Medium dances: min_intensity=40, max_intensity=70
    - Hard dances: min_intensity=70
    - Use sort_by_intensity='asc' for easiest first, 'desc' for hardest first
    
    Args:
        name_contains: Substring to search for in dance name (case-insensitive)
        kind: Dance type - EXACT VALUES: 'Jig', 'Reel', 'Strathspey', 'Hornpipe', 'Waltz', 'March', etc.
        metaform_contains: Formation pattern - EXAMPLES: 'Longwise 3 3C', 'Longwise 4 3C', 'Circle 3C', 'Square 3C'
        max_bars: Maximum number of bars (per repeat) - common values: 32, 48, 64
        formation_token: Technical formation code - EXAMPLES: 'POUSS;3C;', 'ALLMND;3C;', 'HR;3P;' (advanced use)
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
    
    Args:
        query: Search query. Supports FTS5 syntax (e.g., 'poussette OR allemande', 'turn AND right')
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


# Global vector store instance (lazy loaded)
_manual_vectorstore: Optional[Chroma] = None
_manual_vectorstore_lock = asyncio.Lock()


def _load_manual_vectorstore() -> Optional[Chroma]:
    """Load the RSCDS manual vector store (cached after first load)."""
    global _manual_vectorstore
    
    if _manual_vectorstore is not None:
        return _manual_vectorstore
    
    db_path = Path("data/vector_db/rscds_manual")
    
    if not db_path.exists():
        print(f"⚠️  RSCDS manual vector database not found at {db_path}", file=sys.stderr)
        print(f"   Run 'uv run process_rscds_manual.py' to create it.", file=sys.stderr)
        return None
    
    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        _manual_vectorstore = Chroma(
            persist_directory=str(db_path),
            embedding_function=embeddings,
            collection_name="rscds_manual"
        )
        print(f"✅ Loaded RSCDS manual vector database", file=sys.stderr)
        return _manual_vectorstore
    except Exception as e:
        print(f"❌ Error loading RSCDS manual vector database: {e}", file=sys.stderr)
        return None


@tool
async def search_manual(
    query: str,
    num_results: int = 3
) -> str:
    """
    Search the RSCDS (Royal Scottish Country Dance Society) manual for information about formations,
    teaching points, dance techniques, and general Scottish Country Dancing guidance.
    
    Use this tool when:
    - A user asks about how to teach or explain a specific formation (e.g., "How do I teach poussette?")
    - A user wants to know proper technique or teaching points for movements
    - A user asks general questions about Scottish Country Dancing that aren't about specific dances
    - You need authoritative RSCDS guidance on dance technique or formations
    
    Args:
        query: The search query (e.g., "poussette teaching points", "allemande technique", "rights and lefts")
        num_results: Number of relevant sections to return (default 3, max 10)
    
    Returns:
        Formatted string with relevant sections from the RSCDS manual, including page numbers
    """
    func_start = time.perf_counter()
    print(f"DEBUG: search_manual tool called with query: '{query}'", file=sys.stderr)
    
    # Load vector store
    async with _manual_vectorstore_lock:
        vectorstore = _load_manual_vectorstore()
    
    if vectorstore is None:
        return "⚠️  RSCDS manual database not available. Please contact the administrator to set it up."
    
    # Limit num_results to reasonable range
    num_results = max(1, min(num_results, 10))
    
    try:
        # Perform similarity search
        search_start = time.perf_counter()
        results = vectorstore.similarity_search(query, k=num_results)
        search_end = time.perf_counter()
        
        if not results:
            return f"No relevant information found in the RSCDS manual for: '{query}'"
        
        # Format results
        formatted_results = []
        formatted_results.append(f"📚 **RSCDS Manual - Relevant Information for '{query}':**\n")
        
        for i, doc in enumerate(results, 1):
            page = doc.metadata.get('page', 'N/A')
            content = doc.page_content.strip()
            
            formatted_results.append(f"\n**Section {i} (Page {page}):**")
            formatted_results.append(content)
            formatted_results.append("-" * 50)
        
        response = "\n".join(formatted_results)
        
        func_end = time.perf_counter()
        search_time = (search_end - search_start) * 1000
        total_time = (func_end - func_start) * 1000
        
        print(f"DEBUG: search_manual completed - Search: {search_time:.2f}ms, Total: {total_time:.2f}ms", file=sys.stderr)
        
        return response
        
    except Exception as e:
        print(f"❌ Error searching RSCDS manual: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return f"Error searching RSCDS manual: {str(e)}"
