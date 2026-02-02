#!/usr/bin/env python3
"""
Async SQLite database access module for the Scottish Country Dance application.

Provides a connection pool and query helpers for direct database access
without the MCP layer overhead.
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

import aiosqlite

# Configuration
DB_PATH = os.environ.get("SCDDB_SQLITE", "data/scddb/scddb.sqlite")

# Logging
logger = logging.getLogger("scddb.database")


class DatabasePool:
    """Async SQLite connection pool with singleton pattern.

    Manages a small pool of aiosqlite connections for efficient
    concurrent database access.
    """

    _instance: Optional["DatabasePool"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, db_path: str = None, pool_size: int = 3):
        """Initialize the connection pool.

        Args:
            db_path: Path to the SQLite database file
            pool_size: Maximum number of connections to maintain
        """
        self.db_path = db_path or DB_PATH
        self.pool_size = pool_size
        self._pool: List[aiosqlite.Connection] = []
        self._pool_lock = asyncio.Lock()
        self._initialized = False

    @classmethod
    async def get_instance(cls, db_path: str = None) -> "DatabasePool":
        """Get or create the singleton instance.

        Args:
            db_path: Optional path to override the default database path

        Returns:
            The singleton DatabasePool instance
        """
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_path)
            return cls._instance

    async def _create_connection(self) -> aiosqlite.Connection:
        """Create a new database connection with row factory."""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        return conn

    async def acquire(self) -> aiosqlite.Connection:
        """Acquire a connection from the pool.

        Returns:
            An aiosqlite connection
        """
        async with self._pool_lock:
            if self._pool:
                return self._pool.pop()
            return await self._create_connection()

    async def release(self, conn: aiosqlite.Connection):
        """Return a connection to the pool.

        Args:
            conn: The connection to return
        """
        async with self._pool_lock:
            if len(self._pool) < self.pool_size:
                self._pool.append(conn)
            else:
                await conn.close()

    async def close_all(self):
        """Close all connections in the pool."""
        async with self._pool_lock:
            for conn in self._pool:
                try:
                    await conn.close()
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")
            self._pool.clear()
            logger.info("All database connections closed")


async def get_pool() -> DatabasePool:
    """Get the database pool singleton.

    Returns:
        The DatabasePool instance
    """
    return await DatabasePool.get_instance()


async def query(sql: str, args: tuple = ()) -> List[Dict[str, Any]]:
    """Execute a query and return all rows as dictionaries.

    Args:
        sql: The SQL query to execute
        args: Parameters for the query

    Returns:
        List of dictionaries, one per row
    """
    start_time = time.perf_counter()

    pool = await get_pool()
    conn = await pool.acquire()

    try:
        query_start = time.perf_counter()
        cursor = await conn.execute(sql, args)
        fetch_start = time.perf_counter()
        rows = await cursor.fetchall()
        results = [dict(row) for row in rows]
        end_time = time.perf_counter()

        # Log timing
        total_time = (end_time - start_time) * 1000
        query_time = (fetch_start - query_start) * 1000
        fetch_time = (end_time - fetch_start) * 1000

        logger.debug(
            f"QUERY: {total_time:.2f}ms (query={query_time:.2f}ms, fetch={fetch_time:.2f}ms), "
            f"rows={len(results)}"
        )

        return results

    finally:
        await pool.release(conn)


async def query_one(sql: str, args: tuple = ()) -> Optional[Dict[str, Any]]:
    """Execute a query and return the first row as a dictionary.

    Args:
        sql: The SQL query to execute
        args: Parameters for the query

    Returns:
        Dictionary of the first row, or None if no results
    """
    start_time = time.perf_counter()

    pool = await get_pool()
    conn = await pool.acquire()

    try:
        query_start = time.perf_counter()
        cursor = await conn.execute(sql, args)
        fetch_start = time.perf_counter()
        row = await cursor.fetchone()
        result = dict(row) if row else None
        end_time = time.perf_counter()

        # Log timing
        total_time = (end_time - start_time) * 1000
        query_time = (fetch_start - query_start) * 1000
        fetch_time = (end_time - fetch_start) * 1000

        logger.debug(
            f"QUERY_ONE: {total_time:.2f}ms (query={query_time:.2f}ms, fetch={fetch_time:.2f}ms), "
            f"found={result is not None}"
        )

        return result

    finally:
        await pool.release(conn)
