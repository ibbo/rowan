#!/usr/bin/env python3
"""
LangGraph agent that uses MCP SCDDB tools to answer Scottish Country Dance queries.

Usage:
    export OPENAI_API_KEY="your-key-here"
    uv run dance_agent.py

The agent can:
- Search for dances by name, kind, or metaform
- Get detailed information about specific dances
- Search dance cribs for specific moves or terms
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

from dotenv import load_dotenv

# LangGraph and LangChain imports
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

# MCP imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPSCDDBClient:
    """Client wrapper for the MCP SCDDB server."""
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._setup_complete = False
    
    async def setup(self):
        """Initialize the MCP connection."""
        if self._setup_complete:
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
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Call an MCP tool and return the results."""
        async with stdio_client(self.params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                try:
                    result = await session.call_tool(name=name, arguments=arguments)
                    
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
                    
                    return content
                except Exception as e:
                    return [{"error": str(e)}]


# Global MCP client instance
mcp_client = MCPSCDDBClient()


@tool
async def find_dances(
    name_contains: Optional[str] = None,
    kind: Optional[str] = None,
    metaform_contains: Optional[str] = None,
    max_bars: Optional[int] = None,
    formation_token: Optional[str] = None,
    official_rscds_dances: Optional[bool] = None,
    random_variety: Optional[bool] = None,
    limit: int = 25
) -> List[Dict[str, Any]]:
    """
    Search Scottish Country Dances by various criteria.
    
    IMPORTANT SYNTAX EXAMPLES:
    - kind: Use exact values like 'Reel', 'Jig', 'Strathspey', 'Hornpipe', 'Waltz', 'March'
    - metaform_contains: Use patterns like 'Longwise 3 3C', 'Longwise 4 3C', 'Circle 3C', 'Square 3C', 'Longwise 2 2C'
      (NOTE: For 3 couples longwise, use 'Longwise 3 3C' or 'Longwise 4 3C', NOT 'Longwise 3C')
    - formation_token: Use specific tokens like 'POUSS;3C;', 'ALLMND;3C;', 'HR;3P;', 'R&L;3C;', 'REEL;ACROSS;R3;'
      (These are technical formation codes - usually better to use metaform_contains instead)
    
    Args:
        name_contains: Substring to search for in dance name (case-insensitive)
        kind: Dance type - EXACT VALUES: 'Jig', 'Reel', 'Strathspey', 'Hornpipe', 'Waltz', 'March', etc.
        metaform_contains: Formation pattern - EXAMPLES: 'Longwise 3 3C', 'Longwise 4 3C', 'Circle 3C', 'Square 3C'
        max_bars: Maximum number of bars (per repeat) - common values: 32, 48, 64
        formation_token: Technical formation code - EXAMPLES: 'POUSS;3C;', 'ALLMND;3C;', 'HR;3P;' (advanced use)
        official_rscds_dances: FILTER BY PUBLICATION - True=only official RSCDS published dances, False=only community/non-RSCDS dances, None=all dances
        random_variety: If True, randomize results for variety instead of alphabetical order. Recommended for diverse suggestions!
        limit: Maximum number of results (1-200, default 25)
    
    Returns:
        List of dance dictionaries with id, name, kind, metaform, bars, progression
    """
    await mcp_client.setup()
    
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
    if random_variety is not None:
        arguments["random_variety"] = random_variety
    
    print(f"DEBUG: Calling find_dances with arguments: {arguments}", file=sys.stderr)
    result = await mcp_client.call_tool("find_dances", arguments)
    print(f"DEBUG: find_dances returned {len(result)} results", file=sys.stderr)
    
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
    await mcp_client.setup()
    
    result = await mcp_client.call_tool("dance_detail", {"dance_id": dance_id})
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
    await mcp_client.setup()
    
    return await mcp_client.call_tool("search_cribs", {"query": query, "limit": limit})


async def create_dance_agent():
    """Create the LangGraph agent with access to SCDDB tools."""
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OpenAI API key not found. Please set OPENAI_API_KEY environment variable.\n"
            "Example: export OPENAI_API_KEY='your-key-here'"
        )
    
    # Initialize OpenAI model
    llm = ChatOpenAI(
        model="gpt-5-mini",  # Use the more cost-effective model
        temperature=0
    )
    
    # Create the agent with our SCDDB tools
    tools = [find_dances, get_dance_detail, search_cribs]
    agent = create_react_agent(llm, tools)
    
    return agent


async def main():
    """Main interactive loop."""
    
    # Load environment variables from .env file
    load_dotenv()
    
    try:
        print("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scottish Country Dance Assistant")
        print("=" * 50)
        print("Setting up agent with SCDDB access...")
        
        agent = await create_dance_agent()
        
        # Ensure MCP client is set up
        await mcp_client.setup()
        
        print("✅ Agent ready! Ask me about Scottish Country Dances.")
        print("Examples:")
        print("- 'Find me some 32-bar reels'")
        print("- 'What dances have poussette moves?'")
        print("- 'Tell me about dance ID 100'")
        print("- 'Find longwise dances for 3 couples'")
        print("\nType 'quit' to exit.\n")
        
        while True:
            try:
                user_input = input("🤔 Your question: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                print("\n🤖 Thinking...")
                
                # Create messages with system prompt
                messages = [
                    HumanMessage(content=(
                        "You are a Scottish Country Dance expert assistant with access to the Scottish Country Dance Database (SCDDB). "
                        "You can help users find dances, get detailed information about specific dances, and search through dance cribs. "
                        "When helping users:\n"
                        "1. Use find_dances to search for dances by type, formation, or other criteria\n"
                        "2. Use get_dance_detail to get full information about a specific dance\n"
                        "3. Use search_cribs to search for specific moves or terms in dance instructions\n"
                        "Always be helpful and provide clear, well-structured responses. "
                        "When presenting dance information, include relevant details like the dance name, type, formation, and key moves.\n\n"
                        f"User question: {user_input}"
                    ))
                ]
                
                # Process the query through the agent
                response = await agent.ainvoke({"messages": messages})
                
                # Extract the final message
                final_message = response["messages"][-1]
                print(f"\n📚 {final_message.content}\n")
                print("-" * 50)
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
                
    except Exception as e:
        print(f"Failed to start agent: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
