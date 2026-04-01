#!/usr/bin/env python3
"""
Canonical concept resolution for technical Scottish Country Dance terms.

This module resolves user query phrases to exact canonical formations and
steps from the local SQLite database. It intentionally prefers exact alias
matching and simple constraints over semantic guessing.
"""

from __future__ import annotations

import asyncio
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Literal


_NUMBER_WORDS = {
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
}
_WORD_TO_DIGIT = {word: digit for digit, word in _NUMBER_WORDS.items()}

_TECHNICAL_PATTERNS = [
    re.compile(r"\bhow (?:do i|to|should i|would you)\b"),
    re.compile(r"\bteach(?:ing)?\b"),
    re.compile(r"\bwhere (?:are|is)\b"),
    re.compile(r"\bbar(?:s)? \d+\b"),
    re.compile(r"\bwhich (?:foot|hand|side)\b"),
    re.compile(r"\bwhat (?:foot|hand|happens in)\b"),
    re.compile(r"\bpoints? to observe\b"),
    re.compile(r"\bteaching points?\b"),
    re.compile(r"\bposition(?:s|ing)?\b"),
    re.compile(r"\bfacing\b"),
    re.compile(r"\bexplain\b"),
    re.compile(r"\bdescribe\b"),
]


def normalize_text(text: str) -> str:
    """Normalize free text for exact alias matching."""
    text = text.lower()
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = text.replace("-", " ")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _phrase_in_query(query_text: str, alias: str) -> bool:
    """Check whether a normalized alias appears as a phrase in the query."""
    padded_query = f" {query_text} "
    padded_alias = f" {alias} "
    return padded_alias in padded_query


def _replace_number_words(alias: str) -> set[str]:
    """Add digit/word variations for a normalized alias."""
    variants = {alias}
    tokens = alias.split()
    for index, token in enumerate(tokens):
        if token in _WORD_TO_DIGIT:
            updated = tokens[:]
            updated[index] = _WORD_TO_DIGIT[token]
            variants.add(" ".join(updated))
        elif token in _NUMBER_WORDS:
            updated = tokens[:]
            updated[index] = _NUMBER_WORDS[token]
            variants.add(" ".join(updated))
    return variants


@dataclass(frozen=True)
class CanonicalConcept:
    concept_type: Literal["formation", "step"]
    concept_id: int
    canonical_name: str
    canonical_alias: str
    token: str | None = None
    shortname: str | None = None


@dataclass(frozen=True)
class ResolvedConcept:
    concept: CanonicalConcept
    matched_alias: str
    match_kind: Literal["exact", "family"]


@dataclass(frozen=True)
class ConceptResolution:
    query: str
    normalized_query: str
    exact_matches: tuple[ResolvedConcept, ...]
    ambiguous_matches: tuple[CanonicalConcept, ...]
    is_technical_question: bool

    @property
    def has_exact_match(self) -> bool:
        return bool(self.exact_matches)


@dataclass(frozen=True)
class GroundingDecision:
    route: Literal["dance_planner", "grounding_handler"]
    grounding_context: str = ""
    response: str = ""


class CanonicalConceptResolver:
    """Resolve technical dance terms to exact canonical concepts."""

    def __init__(self) -> None:
        self._loaded = False
        self._load_lock = asyncio.Lock()
        self._exact_aliases: Dict[str, list[CanonicalConcept]] = {}
        self._family_aliases: Dict[str, list[CanonicalConcept]] = {}

    async def load(self) -> None:
        """Load formations and steps from the database once."""
        if self._loaded:
            return

        async with self._load_lock:
            if self._loaded:
                return

            formations, steps = await asyncio.to_thread(self._fetch_rows)

            for row in formations:
                concept = CanonicalConcept(
                    concept_type="formation",
                    concept_id=row["id"],
                    canonical_name=row["name"],
                    canonical_alias=normalize_text(row["name"]),
                    token=row["searchid"],
                )
                self._register_concept(concept, self._formation_exact_aliases(row["name"]))
                self._register_family_aliases(concept, self._formation_family_aliases(row["name"]))

            for row in steps:
                concept = CanonicalConcept(
                    concept_type="step",
                    concept_id=row["id"],
                    canonical_name=row["name"],
                    canonical_alias=normalize_text(row["name"]),
                    shortname=row["shortname"],
                )
                self._register_concept(concept, self._step_exact_aliases(row["name"], row["shortname"]))

            self._loaded = True

    def _fetch_rows(self) -> tuple[list[dict], list[dict]]:
        db_path = os.environ.get("SCDDB_SQLITE", "data/scddb/scddb.sqlite")
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            formations = [
                dict(row)
                for row in conn.execute(
                    "SELECT id, name, searchid FROM formation ORDER BY name"
                ).fetchall()
            ]
            steps = [
                dict(row)
                for row in conn.execute(
                    "SELECT id, name, shortname FROM step WHERE lower(name) != 'other' ORDER BY name"
                ).fetchall()
            ]
        return formations, steps

    def _register_concept(self, concept: CanonicalConcept, aliases: Iterable[str]) -> None:
        for alias in aliases:
            self._exact_aliases.setdefault(alias, []).append(concept)

    def _register_family_aliases(self, concept: CanonicalConcept, aliases: Iterable[str]) -> None:
        for alias in aliases:
            self._family_aliases.setdefault(alias, []).append(concept)

    def _formation_exact_aliases(self, name: str) -> set[str]:
        normalized = normalize_text(name)
        aliases = set(_replace_number_words(normalized))

        match = re.match(r"^(?P<base>.+?) for (?P<count>\d+) couples?(?P<rest>.*)$", normalized)
        if match:
            base = match.group("base").strip()
            count = match.group("count")
            rest = match.group("rest").strip()
            number_words = {count, _NUMBER_WORDS.get(count, count)}
            for variant in number_words:
                if not rest:
                    aliases.add(f"{variant} couple {base}".strip())
                    aliases.add(f"{variant} couples {base}".strip())
                else:
                    aliases.add(f"{variant} couple {base} {rest}".strip())
                    aliases.add(f"{variant} couples {base} {rest}".strip())

        if normalized.endswith(" of three"):
            aliases.add(normalized[:-len("three")] + "3")
        if normalized.endswith(" of four"):
            aliases.add(normalized[:-len("four")] + "4")
        if normalized.endswith(" of five"):
            aliases.add(normalized[:-len("five")] + "5")
        if normalized.endswith(" of six"):
            aliases.add(normalized[:-len("six")] + "6")
        if normalized.endswith(" of eight"):
            aliases.add(normalized[:-len("eight")] + "8")

        return {alias.strip() for alias in aliases if alias.strip()}

    def _formation_family_aliases(self, name: str) -> set[str]:
        normalized = normalize_text(name)
        aliases: set[str] = set()
        lowered = name.lower()

        match = re.match(r"^(?P<base>.+?) for \d+ couples?.*$", normalized)
        if match:
            aliases.add(match.group("base").strip())

        for separator in (" - ", " (", ", "):
            if separator in lowered:
                aliases.add(normalize_text(lowered.split(separator, 1)[0]))

        return {alias for alias in aliases if alias}

    def _step_exact_aliases(self, name: str, shortname: str | None) -> set[str]:
        normalized = normalize_text(name)
        aliases = {normalized}

        if normalized.endswith(" of step"):
            aliases.add(normalized[:-len(" of step")].strip())

        aliases.update(_replace_number_words(normalized))

        if shortname:
            aliases.add(normalize_text(shortname))

        return {alias for alias in aliases if alias}

    async def resolve(self, query_text: str) -> ConceptResolution:
        await self.load()

        normalized_query = normalize_text(query_text)
        technical_question = is_technical_question(query_text)

        exact_matches: list[ResolvedConcept] = []
        for alias, concepts in sorted(
            self._exact_aliases.items(),
            key=lambda item: len(item[0].split()),
            reverse=True,
        ):
            if not _phrase_in_query(normalized_query, alias):
                continue
            if len(concepts) == 1:
                exact_matches.append(
                    ResolvedConcept(
                        concept=concepts[0],
                        matched_alias=alias,
                        match_kind="exact",
                    )
                )

        exact_matches = _dedupe_resolved(exact_matches)
        if exact_matches:
            return ConceptResolution(
                query=query_text,
                normalized_query=normalized_query,
                exact_matches=tuple(exact_matches),
                ambiguous_matches=tuple(),
                is_technical_question=technical_question,
            )

        ambiguous: list[CanonicalConcept] = []
        for alias, concepts in sorted(
            self._family_aliases.items(),
            key=lambda item: len(item[0].split()),
            reverse=True,
        ):
            if not _phrase_in_query(normalized_query, alias):
                continue
            if len(concepts) == 1:
                exact_matches.append(
                    ResolvedConcept(
                        concept=concepts[0],
                        matched_alias=alias,
                        match_kind="family",
                    )
                )
            else:
                ambiguous.extend(concepts)

        return ConceptResolution(
            query=query_text,
            normalized_query=normalized_query,
            exact_matches=tuple(_dedupe_resolved(exact_matches)),
            ambiguous_matches=tuple(_dedupe_concepts(ambiguous)),
            is_technical_question=technical_question,
        )


def _dedupe_resolved(matches: list[ResolvedConcept]) -> list[ResolvedConcept]:
    seen: set[tuple[str, int]] = set()
    deduped: list[ResolvedConcept] = []
    for match in matches:
        key = (match.concept.concept_type, match.concept.concept_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(match)
    return deduped


def _dedupe_concepts(concepts: list[CanonicalConcept]) -> list[CanonicalConcept]:
    seen: set[tuple[str, int]] = set()
    deduped: list[CanonicalConcept] = []
    for concept in concepts:
        key = (concept.concept_type, concept.concept_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(concept)
    return deduped


def is_technical_question(query_text: str) -> bool:
    normalized = normalize_text(query_text)
    return any(pattern.search(normalized) for pattern in _TECHNICAL_PATTERNS)


def manual_kb_available(base_dir: str = "data/manual") -> bool:
    return (Path(base_dir) / "index.json").exists()


def build_grounding_decision(
    resolution: ConceptResolution,
    manual_available: bool,
) -> GroundingDecision:
    """Decide whether to continue to planning or stop with a grounded response."""
    if resolution.is_technical_question and resolution.ambiguous_matches:
        return GroundingDecision(
            route="grounding_handler",
            response=_build_disambiguation_response(resolution.ambiguous_matches),
        )

    if resolution.is_technical_question and resolution.exact_matches and not manual_available:
        return GroundingDecision(
            route="grounding_handler",
            response=_build_unsupported_response(resolution.exact_matches),
        )

    if resolution.exact_matches:
        return GroundingDecision(
            route="dance_planner",
            grounding_context=_build_grounding_context(
                resolution.exact_matches,
                manual_available,
            ),
        )

    if resolution.is_technical_question and resolution.ambiguous_matches:
        return GroundingDecision(
            route="grounding_handler",
            response=_build_disambiguation_response(resolution.ambiguous_matches),
        )

    return GroundingDecision(route="dance_planner")


def _build_grounding_context(
    matches: tuple[ResolvedConcept, ...],
    manual_available: bool,
) -> str:
    lines = [
        "Canonical concept grounding for the current user query:",
    ]
    for match in matches:
        concept = match.concept
        suffix_parts = []
        if concept.token:
            suffix_parts.append(f"token={concept.token}")
        if concept.shortname:
            suffix_parts.append(f"shortname={concept.shortname}")
        suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
        lines.append(
            f"- {concept.concept_type}: {concept.canonical_name}{suffix}; matched alias='{match.matched_alias}'"
        )
    if not manual_available:
        lines.append(
            "Manual KB status: unavailable. Do not invent technical mechanics, positions, or teaching points that are not grounded in tool results."
        )
    return "\n".join(lines)


def _build_disambiguation_response(concepts: tuple[CanonicalConcept, ...]) -> str:
    lines = [
        "I can only ground that term to a family of canonical concepts, not a single exact one. Please clarify which concept you mean:",
        "",
    ]
    for concept in concepts[:8]:
        details = []
        if concept.token:
            details.append(concept.token)
        if concept.shortname:
            details.append(concept.shortname)
        suffix = f" ({', '.join(details)})" if details else ""
        lines.append(f"- {concept.canonical_name}{suffix}")
    return "\n".join(lines)


def _build_unsupported_response(matches: tuple[ResolvedConcept, ...]) -> str:
    lines = [
        "I can resolve your question to exact canonical concept(s), but I do not have enough grounded reference material in this worktree to answer the technical detail reliably without improvising.",
        "",
        "Resolved concept(s):",
    ]
    for match in matches:
        concept = match.concept
        details = []
        if concept.token:
            details.append(f"token {concept.token}")
        if concept.shortname:
            details.append(f"shortname {concept.shortname}")
        suffix = f" ({', '.join(details)})" if details else ""
        lines.append(f"- {concept.concept_type}: {concept.canonical_name}{suffix}")
    lines.extend(
        [
            "",
            "The local formations and steps tables identify the concept names, but they do not contain authoritative bar-by-bar positions or teaching mechanics. The RSCDS manual KB is also unavailable here, so I should not make that part up.",
        ]
    )
    return "\n".join(lines)
