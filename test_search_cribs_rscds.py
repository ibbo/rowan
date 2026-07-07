#!/usr/bin/env python3
"""Tests for the RSCDS filter on search_cribs (formation-based dance search)."""

import sqlite3
import unittest

from dance_tools import search_cribs

DB_PATH = "data/scddb/scddb.sqlite"


def _rscds_dance_ids(ids):
    """Return the subset of ids that have at least one RSCDS publication."""
    conn = sqlite3.connect(DB_PATH)
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""
        SELECT DISTINCT dpm.dance_id
        FROM dancespublicationsmap dpm
        JOIN publication p ON p.id = dpm.publication_id AND p.rscds = 1
        WHERE dpm.dance_id IN ({placeholders})
        """,
        list(ids),
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}


class SearchCribsRscdsFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_rscds_true_returns_only_rscds_dances(self):
        rows = await search_cribs.ainvoke(
            {"query_text": "tournee", "official_rscds_dances": True, "limit": 30}
        )
        self.assertTrue(rows, "expected some RSCDS dances with a tournee")
        ids = [r["id"] for r in rows]
        self.assertEqual(set(ids), _rscds_dance_ids(ids))

    async def test_rscds_false_returns_no_rscds_dances(self):
        rows = await search_cribs.ainvoke(
            {"query_text": "tournee", "official_rscds_dances": False, "limit": 30}
        )
        self.assertTrue(rows)
        ids = [r["id"] for r in rows]
        self.assertEqual(_rscds_dance_ids(ids), set())

    async def test_unfiltered_still_works(self):
        rows = await search_cribs.ainvoke({"query_text": "poussette", "limit": 5})
        self.assertEqual(len(rows), 5)

    async def test_filter_combines_with_kind(self):
        rows = await search_cribs.ainvoke(
            {
                "query_text": "poussette",
                "kind": "Strathspey",
                "official_rscds_dances": True,
                "limit": 20,
            }
        )
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(r["kind"], "Strathspey")
        ids = [r["id"] for r in rows]
        self.assertEqual(set(ids), _rscds_dance_ids(ids))


if __name__ == "__main__":
    unittest.main()
