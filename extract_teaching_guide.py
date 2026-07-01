#!/usr/bin/env python3
"""
Extract the RSCDS "Teaching Scottish Country Dancing" guide (Guidelines
for Tutors, Teachers and Candidates) into a concept-keyed JSON knowledge
base for the get_teaching_guidance tool.

Unlike the manual (reference: what a step IS), this guide is pedagogy
(how to TEACH it): staged build-ups, common faults to observe, and
complete sample lesson plans. Content is keyed by step/topic so the
agent retrieves one self-contained bundle per concept and cannot blend
material from sibling steps.

Output:
- data/teaching_guide/teaching_guide.json
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF

DEFAULT_PDF = (
    "data/raw/02-87-teaching_scottish_country_dancing_"
    "-_guidelines_for_tutors_teachers_and_candidates_2_4.pdf"
)

# Canonical step keys (aligned with the manual's terminology) mapped from
# the headings used in sections 7.1/7.3 and the appendices.
STEP_NAME_MAP = {
    "skip change of step": "skip change of step",
    "strathspey travelling step": "strathspey travelling step",
    "slip step": "slip step",
    "pas de basque": "pas de basque",
    "strathspey setting": "strathspey setting",
    "the common schottische or strathspey setting": "strathspey setting",
}


class TeachingGuideExtractor:
    def __init__(self, pdf_path: str = DEFAULT_PDF, output_dir: str = "data/teaching_guide"):
        self.pdf_path = Path(pdf_path)
        self.output_dir = Path(output_dir)

    def extract(self) -> Dict:
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")

        print(f"📖 Opening {self.pdf_path}")
        doc = fitz.open(self.pdf_path)
        text = "\n".join(doc[p].get_text() for p in range(len(doc)))
        doc.close()
        text = self._clean(text)

        guide = {
            "version": "2.4",
            "source": str(self.pdf_path),
            "title": (
                "Teaching Scottish Country Dancing - Guidelines for "
                "Tutors, Teachers and Candidates (RSCDS)"
            ),
            "topics": self._extract_topics(text),
            "steps": self._extract_steps(text),
            "formations": self._extract_formations(text),
        }

        self._validate(guide)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.output_dir / "teaching_guide.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(guide, f, indent=2, ensure_ascii=False)

        print(f"   ✅ {out_path}")
        print(f"   Topics: {len(guide['topics'])}, steps: {len(guide['steps'])}, "
              f"formations: {len(guide['formations'])}")
        return guide

    @staticmethod
    def _clean(text: str) -> str:
        # Word-generated PDF: non-breaking hyphens and stray page-number lines
        text = text.replace("‐", "-").replace(" ", " ")
        lines = [ln for ln in text.split("\n") if not re.match(r"^\s*\d{1,3}\s*$", ln)]
        return "\n".join(lines)

    @staticmethod
    def _slice(text: str, start_pattern: str, end_pattern: str) -> str:
        """Return text between two ^heading$ regexes (start heading excluded)."""
        start = re.search(rf"^{start_pattern}\s*$", text, re.M)
        if not start:
            raise ValueError(f"Start heading not found: {start_pattern}")
        rest = text[start.end():]
        end = re.search(rf"^{end_pattern}\s*$", rest, re.M)
        content = rest[: end.start()] if end else rest
        return content.strip()

    @staticmethod
    def _tidy(block: str) -> str:
        """Collapse intra-paragraph line breaks while keeping list structure."""
        lines = [ln.rstrip() for ln in block.split("\n")]
        out: List[str] = []
        for ln in lines:
            stripped = ln.strip()
            if not stripped:
                if out and out[-1] != "":
                    out.append("")
                continue
            # New list item / heading starts its own line
            if re.match(r"^(\d+\.|[a-z]\)|•|APPENDIX|Sample lesson plan|[A-Z][^.]*:$)", stripped):
                out.append(stripped)
            elif out and out[-1] and not out[-1].endswith(":"):
                out[-1] = f"{out[-1]} {stripped}"
            else:
                out.append(stripped)
        return "\n".join(out).strip()

    def _extract_topics(self, text: str) -> Dict[str, Dict]:
        sections = {
            "warm-ups and cool downs": (r"3\.0 Warm-ups and Cool Downs", r"4\.0 Teaching - Level 1.*"),
            "how to teach": (r"4\.0 Teaching - Level 1.*", r"5\.0 Teaching Practice.*"),
            "teaching steps and formations": (r"7\.1 Steps and Formations", r"7\.2 Build up of the dance.*"),
            "dance build-up": (r"7\.2 Build up of the dance.*", r"7\.3 Observation"),
            "observation": (r"7\.3 Observation", r"7\.4 Presentation"),
            "presentation": (r"7\.4 Presentation", r"7\.5 Class Management"),
            "class management": (r"7\.5 Class Management", r"7\.6 Use of Music"),
            "use of music": (r"7\.6 Use of Music", r"7\.7 Use of Voice"),
            "use of voice": (r"7\.7 Use of Voice", r"8\.0 Beyond the Teaching Certificate"),
        }
        topics = {}
        for key, (start, end) in sections.items():
            topics[key] = {
                "title": key.title(),
                "content": self._tidy(self._slice(text, start, end)),
            }
        # Full-lesson structure examples
        topics["unit 3 lesson plan"] = {
            "title": "Sample Lesson Plan - Unit 3 (structure of a complete lesson)",
            "content": self._tidy(self._slice(
                text, r"Sample lesson plan – Unit 3", r"APPENDIX 6:")),
        }
        topics["unit 5 lesson plan"] = {
            "title": "Sample Lesson Plan - Unit 5 (structure of a complete lesson)",
            "content": self._tidy(self._lesson_plan_tail(text, "Unit 5")),
        }
        return topics

    @staticmethod
    def _lesson_plan_tail(text: str, name: str) -> str:
        start = re.search(rf"^Sample lesson plan – {name}\s*$", text, re.M)
        if not start:
            raise ValueError(f"Lesson plan not found: {name}")
        rest = text[start.end():]
        end = re.search(r"^APPENDIX \d+:\s*$", rest, re.M)
        return (rest[: end.start()] if end else rest).strip()

    def _numbered_step_blocks(self, block: str) -> Dict[str, str]:
        """Parse '1. Step Name ...' blocks into {canonical_key: content}."""
        result: Dict[str, str] = {}
        matches = list(re.finditer(r"^(\d+)\.\s+(.+?)\s*$", block, re.M))
        for i, m in enumerate(matches):
            heading = re.sub(r"\s*\(.*?\)\s*$", "", m.group(2)).strip().lower()
            key = STEP_NAME_MAP.get(heading)
            if key is None:
                continue
            end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
            result[key] = self._tidy(block[m.end():end])
        return result

    def _extract_steps(self, text: str) -> Dict[str, Dict]:
        # 7.1: main teaching points, split by progression/setting groups
        section_71 = self._slice(text, r"7\.1 Steps and Formations", r"7\.2 Build up of the dance.*")
        teaching_points = self._numbered_step_blocks(section_71)

        # 7.3: main faults to correct, between the list header and the
        # closing guidance paragraph
        section_73 = self._slice(text, r"7\.3 Observation", r"7\.4 Presentation")
        faults_match = re.search(
            r"Main Faults to Correct in Steps:\s*(.*?)(?=Correction of faults must be done)",
            section_73, re.S)
        if not faults_match:
            raise ValueError("Fault list boundaries not found in section 7.3")
        common_faults = self._numbered_step_blocks(faults_match.group(1))

        lesson_plans = {
            "skip change of step": "Skip Change of Step",
            "pas de basque": "Pas de Basque",
            "strathspey travelling step": "Strathspey Travelling Step",
        }

        steps: Dict[str, Dict] = {}
        for key in sorted(set(teaching_points) | set(common_faults)):
            steps[key] = {"title": key.title()}
            if key in teaching_points:
                steps[key]["teaching_points"] = teaching_points[key]
            if key in common_faults:
                steps[key]["common_faults"] = common_faults[key]
            if key in lesson_plans:
                steps[key]["lesson_plan"] = self._tidy(
                    self._lesson_plan_tail(text, lesson_plans[key]))
        return steps

    def _extract_formations(self, text: str) -> Dict[str, Dict]:
        return {
            "rights and lefts": {
                "title": "Rights And Lefts",
                "lesson_plan": self._tidy(self._lesson_plan_tail(text, "Rights and Lefts")),
            }
        }

    @staticmethod
    def _validate(guide: Dict) -> None:
        expected_steps = {
            "skip change of step", "strathspey travelling step", "slip step",
            "pas de basque", "strathspey setting",
        }
        missing = expected_steps - set(guide["steps"])
        if missing:
            raise ValueError(f"Expected steps missing from extraction: {sorted(missing)}")
        for key in ("skip change of step", "pas de basque", "strathspey travelling step"):
            if not guide["steps"][key].get("lesson_plan"):
                raise ValueError(f"Missing lesson plan for {key}")
        for key, step in guide["steps"].items():
            if not step.get("common_faults"):
                raise ValueError(f"Missing common faults for {key}")
        # Cross-contamination guard: each step's fault list must not name
        # a sibling step
        for key, step in guide["steps"].items():
            for other in guide["steps"]:
                if other != key and other in step.get("common_faults", "").lower():
                    raise ValueError(f"Fault list for {key} mentions {other}")


def main():
    print("🏴󠁧󠁢󠁳󠁣󠁴󠁿 RSCDS Teaching Guide Extraction")
    print("=" * 50)
    try:
        TeachingGuideExtractor().extract()
        print("\n✅ Extraction complete!")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
