#!/usr/bin/env python3
"""Dance-name search must cope with SCDDB's rotated articles ("Diplomat, The")."""

import unittest

from dance_tools import _name_pattern, find_dances, get_dance_detail, resolve_dance


class NamePatternTests(unittest.TestCase):
    def test_leading_article_is_dropped(self):
        self.assertEqual(_name_pattern("The Diplomat"), "%Diplomat%")
        self.assertEqual(_name_pattern("the reel of the 51st division"), "%reel of the 51st division%")
        self.assertEqual(_name_pattern("A Trip to Bavaria"), "%Trip to Bavaria%")

    def test_no_article_unchanged(self):
        self.assertEqual(_name_pattern("Mairi's Wedding"), "%Mairi's Wedding%")

    def test_article_only_query_falls_back(self):
        self.assertEqual(_name_pattern("The"), "%The%")


class FindDancesByNameTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_diplomat_is_found(self):
        rows = await find_dances.ainvoke({"name_contains": "The Diplomat", "random_variety": False})
        self.assertIn("Diplomat, The", [r["name"] for r in rows])

    async def test_reel_of_51st_with_and_without_article(self):
        for query in ("The Reel of the 51st Division", "Reel of the 51st Division"):
            rows = await find_dances.ainvoke({"name_contains": query, "random_variety": False})
            self.assertIn("Reel of the 51st Division, The", [r["name"] for r in rows], query)


class ResolveDanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_title_with_leading_article(self):
        resolved = await resolve_dance("The Reel of the 51st Division")
        self.assertEqual(resolved["dance"]["name"], "Reel of the 51st Division, The")

    async def test_stored_form_matches_exactly(self):
        resolved = await resolve_dance("Diplomat, The")
        self.assertEqual(resolved["dance"]["id"], 17880)

    async def test_ambiguous_name_returns_candidates(self):
        resolved = await resolve_dance("Reel of the")
        self.assertIn("candidates", resolved)
        self.assertGreater(len(resolved["candidates"]), 1)

    async def test_unknown_name_returns_error(self):
        resolved = await resolve_dance("Zzyzx Nonexistent Strathspey")
        self.assertIn("error", resolved)

    async def test_get_dance_detail_by_name_returns_crib(self):
        detail = await get_dance_detail.ainvoke({"dance_name": "The Reel of the 51st Division"})
        self.assertEqual(detail["dance"]["id"], 5525)
        self.assertIn("cast off two places", detail["crib"]["text"].lower())

    async def test_get_dance_detail_rejects_guessed_ids(self):
        self.assertIn("error", await get_dance_detail.ainvoke({"dance_id": 0}))
        self.assertIn("error", await get_dance_detail.ainvoke({"dance_id": 99999999}))


if __name__ == "__main__":
    unittest.main()
