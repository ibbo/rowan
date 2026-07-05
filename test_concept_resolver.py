#!/usr/bin/env python3
"""Focused tests for canonical concept grounding."""

import unittest

from concept_resolver import CanonicalConceptResolver, build_grounding_decision


class CanonicalConceptResolverTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.resolver = CanonicalConceptResolver()

    async def test_resolves_two_couple_allemande_from_alias(self) -> None:
        resolution = await self.resolver.resolve(
            "Where are the first couple in bar 2 of the 2 couple allemande?"
        )

        self.assertTrue(resolution.is_technical_question)
        self.assertEqual(len(resolution.exact_matches), 1)

        concept = resolution.exact_matches[0].concept
        self.assertEqual(concept.concept_type, "formation")
        self.assertEqual(concept.canonical_name, "Allemande for 2 couples")
        self.assertEqual(concept.token, "ALLMND;2C;")

    async def test_resolves_skip_change_step_alias(self) -> None:
        resolution = await self.resolver.resolve("How do I teach skip change?")

        self.assertTrue(resolution.is_technical_question)
        self.assertEqual(len(resolution.exact_matches), 1)

        concept = resolution.exact_matches[0].concept
        self.assertEqual(concept.concept_type, "step")
        self.assertEqual(concept.canonical_name, "Skip-Change")
        self.assertEqual(concept.shortname, "SkCh")

    async def test_ambiguous_allemande_requires_disambiguation(self) -> None:
        resolution = await self.resolver.resolve("How do I teach allemande?")

        self.assertFalse(resolution.exact_matches)
        ambiguous_names = {concept.canonical_name for concept in resolution.ambiguous_matches}
        self.assertIn("Allemande for 2 couples", ambiguous_names)
        self.assertIn("Allemande for 3 couples", ambiguous_names)

        decision = build_grounding_decision(resolution, manual_available=False)
        self.assertEqual(decision.route, "grounding_handler")
        self.assertIn("Please clarify", decision.response)

    async def test_nontechnical_reel_of_three_flows_to_planner_with_grounding(self) -> None:
        resolution = await self.resolver.resolve("Find dances with a reel of 3")

        self.assertFalse(resolution.is_technical_question)
        self.assertEqual(len(resolution.exact_matches), 1)

        concept = resolution.exact_matches[0].concept
        self.assertEqual(concept.canonical_name, "Reel of three")
        self.assertEqual(concept.token, "REEL;R3;")

        decision = build_grounding_decision(resolution, manual_available=False)
        self.assertEqual(decision.route, "dance_planner")
        self.assertIn("Reel of three", decision.grounding_context)
        self.assertIn("REEL;R3;", decision.grounding_context)

    async def test_technical_question_with_no_match_gets_no_improvise_context(self) -> None:
        resolution = await self.resolver.resolve(
            "What is the footwork in the birl and twirl?"
        )

        self.assertTrue(resolution.is_technical_question)
        self.assertFalse(resolution.exact_matches)
        self.assertFalse(resolution.ambiguous_matches)

        decision = build_grounding_decision(resolution, manual_available=True)
        self.assertEqual(decision.route, "dance_planner")
        self.assertIn("Do not improvise", decision.grounding_context)
        self.assertIn("search_manual", decision.grounding_context)

    async def test_technical_exact_match_blocks_without_manual_grounding(self) -> None:
        resolution = await self.resolver.resolve(
            "Where are the first couple in bar 2 of the 2 couple allemande?"
        )

        decision = build_grounding_decision(resolution, manual_available=False)
        self.assertEqual(decision.route, "grounding_handler")
        self.assertIn("Allemande for 2 couples", decision.response)
        self.assertIn("ALLMND;2C;", decision.response)


if __name__ == "__main__":
    unittest.main()
