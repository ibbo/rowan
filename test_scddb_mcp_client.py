#!/usr/bin/env python3
"""
Simple MCP client to verify the scddb server starts and responds.
- Spawns the server over stdio
- Lists available tools
- Calls one tool and prints the result

Requirements: `mcp` Python package (already declared in pyproject.toml)
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    # Use the actual database with full schema, not a temporary test file
    db_path = os.environ.get("SCDDB_SQLITE", "data/scddb/scddb.sqlite")
    db_path = str(Path(db_path).resolve())
    
    # Ensure the database exists
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}. Run refresh_scddb.py first.", file=sys.stderr)
        raise SystemExit(1)

    # Resolve server script path relative to this file
    server_script = str((Path(__file__).parent / "mcp_scddb_server.py").resolve())
    if not Path(server_script).exists():
        print(f"Server script not found: {server_script}", file=sys.stderr)
        raise SystemExit(1)

    # Prepare stdio server launch parameters
    params = StdioServerParameters(
        command=sys.executable,  # launch using current Python
        args=[server_script],
        env={
            # Ensure the server can find (or create) the DB file in a safe temp location
            "SCDDB_SQLITE": db_path,
            # Keep logging reasonable; it's written to stderr and won't break stdio JSON
            "SCDDB_LOG_LEVEL": os.environ.get("SCDDB_LOG_LEVEL", "INFO"),
        },
    )

    # Connect to the server over stdio and open a ClientSession with read/write streams
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize handshake
            await session.initialize()
            print("Initialized session with scddb server\n")

            # List tools
            tools_result = await session.list_tools()
            print("Available tools:")
            for tool in tools_result.tools:
                print(f"- {tool.name}: {tool.description}")
            print()

            # Try to call one tool; this may return an error payload if the DB lacks schema,
            # which is fine for verifying that the server receives and handles calls.
            try:
                call = await session.call_tool(
                    name="search_cribs",
                    arguments={"query": "reel OR jig", "limit": 2},
                )
                print("search_cribs result content:")
                for block in call.content:
                    # Expecting TextContent typically
                    kind = getattr(block, "type", type(block).__name__)
                    payload = getattr(block, "text", None)
                    # Fall back to JSON dump for any other content-like objects
                    if payload is None:
                        try:
                            payload = json.dumps(block)
                        except Exception:
                            payload = str(block)
                    print(f"- [{kind}] {payload}")
            except Exception as e:
                print(f"Error calling tool: {e}")


if __name__ == "__main__":
    asyncio.run(main())
