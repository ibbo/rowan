"""Tests for the RSCDS teaching guide KB and get_teaching_guidance tool.

Requires data/teaching_guide/teaching_guide.json (run
extract_teaching_guide.py). Guards concept isolation: each step's
guidance must come only from that step's own sections of the guide.
"""

import asyncio
import json
import unittest
from pathlib import Path

from dance_tools import get_teaching_guidance, TEACHING_GUIDE_PATH


def call(topic: str) -> str:
    return asyncio.run(get_teaching_guidance.ainvoke({"topic": topic}))


@unittest.skipUnless(TEACHING_GUIDE_PATH.exists(), "teaching guide KB not extracted")
class TeachingGuideDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guide = json.loads(Path(TEACHING_GUIDE_PATH).read_text(encoding="utf-8"))

    def test_all_expected_steps_present(self):
        self.assertEqual(
            sorted(self.guide["steps"]),
            ["pas de basque", "skip change of step", "slip step",
             "strathspey setting", "strathspey travelling step"],
        )

    def test_steps_have_faults_and_points(self):
        for key, step in self.guide["steps"].items():
            self.assertTrue(step.get("common_faults"), key)
            self.assertTrue(step.get("teaching_points"), key)

    def test_step_content_not_cross_contaminated(self):
        for key, step in self.guide["steps"].items():
            blob = (step.get("teaching_points", "") + step.get("common_faults", "")).lower()
            for other in self.guide["steps"]:
                if other != key:
                    self.assertNotIn(other, blob, f"{key} mentions {other}")


@unittest.skipUnless(TEACHING_GUIDE_PATH.exists(), "teaching guide KB not extracted")
class GetTeachingGuidanceToolTests(unittest.TestCase):
    def test_skip_change_bundle(self):
        out = call("skip change of step")
        self.assertIn("Hop Step Close Step", out)
        self.assertIn("Lack of hop", out)
        self.assertIn("Sample lesson plan", out)
        self.assertNotIn("pas de basque", out.lower())

    def test_alias_resolution(self):
        self.assertIn("Hop Step Close Step", call("skip change"))
        self.assertIn("jeté", call("pdb"))

    def test_pas_de_basque_is_not_skip_change(self):
        out = call("pas de basque")
        self.assertNotIn("skip change", out.lower())

    def test_general_topic(self):
        out = call("class management")
        self.assertIn("class management", out.lower())

    def test_formation_lesson_plan(self):
        out = call("rights and lefts")
        self.assertIn("Sample lesson plan", out)

    def test_substring_fallback(self):
        out = call("teaching guidance for the slip step please")
        self.assertIn("Slip Step", out)

    def test_unknown_topic_lists_available(self):
        out = call("quantum mechanics")
        self.assertIn("Available topics", out)
        self.assertIn("skip change of step", out)


if __name__ == "__main__":
    unittest.main()
