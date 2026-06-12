"""Regression tests for RSCDS manual lookup precision.

Guards against the alias-collision bug where "skip change" resolved to
5.6.1.6 (Slip step to skip change of step) and "pdb" to 5.6.1.4 (Slip
step to pas de basque), so step questions were answered with content
from the wrong step. Requires data/manual/ (run extract_manual_structured.py).
"""

import unittest

from dance_tools import ManualKnowledgeBase


class ManualLookupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = ManualKnowledgeBase()
        if not cls.kb.load():
            raise unittest.SkipTest("data/manual/index.json not available")

    def lookup_section(self, name):
        result = self.kb.lookup(name)
        self.assertIsNotNone(result, f"lookup({name!r}) returned None")
        self.assertFalse(result.get("ambiguous"),
                         f"lookup({name!r}) unexpectedly ambiguous")
        return result

    def test_skip_change_alias_resolves_to_step_section(self):
        self.assertEqual(self.lookup_section("skip change")["section"], "5.4.1")

    def test_skip_change_full_name(self):
        self.assertEqual(self.lookup_section("skip change of step")["section"], "5.4.1")

    def test_pas_de_basque_aliases_resolve_to_step_section(self):
        for name in ("pas de basque", "pas-de-basque", "pdb"):
            self.assertEqual(self.lookup_section(name)["section"], "5.4.2", name)

    def test_skip_change_content_is_not_pas_de_basque(self):
        content = self.lookup_section("skip change")["content"].lower()
        self.assertIn("skip change", content)
        self.assertNotIn("pas de basque to", content)

    def test_transition_sections_still_reachable_by_title(self):
        result = self.lookup_section("slip step to skip change of step")
        self.assertEqual(result["section"], "5.6.1.6")

    def test_family_terms_collapse_to_family_section(self):
        self.assertEqual(self.lookup_section("allemande")["section"], "6.2")
        self.assertEqual(self.lookup_section("petronella")["section"], "6.20")
        self.assertEqual(self.lookup_section("figure 8")["section"], "6.13")

    def test_exact_title_beats_alias_claims(self):
        self.assertEqual(self.lookup_section("grand chain")["section"], "6.7.1")

    def test_genuinely_ambiguous_names_ask_for_disambiguation(self):
        for name in ("poussette", "hands round"):
            result = self.kb.lookup(name)
            self.assertIsNotNone(result, name)
            self.assertTrue(result.get("ambiguous"), name)
            self.assertGreaterEqual(len(result["candidates"]), 2, name)

    def test_lookup_by_section_number(self):
        self.assertEqual(self.lookup_section("5.4.1")["title"], "Skip change of step")


class ManualSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = ManualKnowledgeBase()
        if not cls.kb.load():
            raise unittest.SkipTest("data/manual/index.json not available")

    def test_search_ranks_canonical_step_above_transitions(self):
        results = self.kb.search("how do I teach skip change of step")
        self.assertTrue(results)
        self.assertEqual(results[0]["section"], "5.4.1")

    def test_search_dedupes_sections(self):
        results = self.kb.search("skip change", limit=10)
        sections = [r["section"] for r in results]
        self.assertEqual(len(sections), len(set(sections)))


if __name__ == "__main__":
    unittest.main()
