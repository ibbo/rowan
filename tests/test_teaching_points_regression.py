#!/usr/bin/env python3
"""
Regression tests for lesson_tools.get_teaching_points_for_dance.

Specifically guards against:
  NameError: name 'func_start' is not defined

Fixed in commit 3fb2f3d — func_start must be assigned at the top of the
function body before the timing calculation (func_end = time.perf_counter())
that runs on the happy-path return.

All tests use monkeypatching so no real database or manual KB files are needed.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Minimal stub factories
# ---------------------------------------------------------------------------

def _dance_row(kind="Strathspey"):
    """Minimal dance-info dict that mirrors a v_metaform row."""
    return {
        "id": 42,
        "name": "Test Dance",
        "kind": kind,
        "bars": 32,
        "couples": 3,
        "metaform": "3C set",
    }


def _crib_row(text=""):
    """Minimal crib dict that mirrors a v_crib_best row."""
    return {
        "reliability": "good",
        "last_modified": "2024-01-01",
        "text": text,
    }


def _mock_kb(sections=None):
    """Return a MagicMock that looks like a loaded ManualKnowledgeBase."""
    kb = MagicMock()
    kb._loaded = True
    kb.lookup.side_effect = lambda key: (sections or {}).get(key.lower())
    return kb


# NOTE: We use pytest-asyncio for async tests; no manual event loop handling.


# ---------------------------------------------------------------------------
# REGRESSION: func_start NameError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestFuncStartRegression:
    """
    Before commit 3fb2f3d the function used func_end = time.perf_counter() at
    the bottom but never defined func_start, so any call that reached the
    return statement raised:

        NameError: name 'func_start' is not defined

    Every test in this class drives the function all the way to its normal
    return, verifying no NameError is raised.
    """

    async def test_no_nameerror_empty_crib(self, monkeypatch):
        """Happy path with an empty crib must reach the timing code without error."""
        import lesson_tools

        monkeypatch.setattr(
            lesson_tools,
            "query_one",
            AsyncMock(side_effect=[_dance_row(), _crib_row("")]),
        )
        monkeypatch.setattr(lesson_tools, "_get_manual_kb", lambda: _mock_kb())

        # Would raise NameError here if func_start were missing
        result = await lesson_tools.get_teaching_points_for_dance.ainvoke({"dance_id": 42})
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert result["dance_id"] == 42
        assert result["formations_found"] == []
        assert result["teaching_points"] == []

    async def test_no_nameerror_with_matching_formation(self, monkeypatch):
        """Happy path with a matching formation still reaches the timing code."""
        import lesson_tools

        section = {
            "section": "5.1",
            "title": "Allemande",
            "page": 91,
            "content": "Travelling steps for the allemande hold.",
        }

        monkeypatch.setattr(
            lesson_tools,
            "query_one",
            AsyncMock(side_effect=[
                _dance_row(),
                _crib_row("1s and 2s do an allemande; then reel of three across"),
            ]),
        )
        monkeypatch.setattr(
            lesson_tools,
            "_get_manual_kb",
            lambda: _mock_kb({"allemande": section}),
        )

        result = await lesson_tools.get_teaching_points_for_dance.ainvoke({"dance_id": 42})
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "allemande" in result["formations_found"]
        assert "reel of three" in result["formations_found"]
        tp_names = [tp["formation"] for tp in result["teaching_points"]]
        assert "allemande" in tp_names

    async def test_no_nameerror_all_formations_missing_from_kb(self, monkeypatch):
        """Formations found in crib but absent from KB: function must still complete."""
        import lesson_tools

        monkeypatch.setattr(
            lesson_tools,
            "query_one",
            AsyncMock(side_effect=[
                _dance_row(),
                _crib_row("cast off, grand chain, figure of eight"),
            ]),
        )
        # Empty KB — no section data returned for any formation
        monkeypatch.setattr(lesson_tools, "_get_manual_kb", lambda: _mock_kb({}))

        result = await lesson_tools.get_teaching_points_for_dance.ainvoke({"dance_id": 42})
        assert "error" not in result
        assert len(result["formations_found"]) >= 2   # cast off, grand chain, figure of eight
        assert result["teaching_points"] == []


# ---------------------------------------------------------------------------
# Behaviour: early-exit paths (do NOT reach timing code)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEarlyExitPaths:
    """Tests for branches that return before the timing calculation."""

    async def test_dance_not_found(self, monkeypatch):
        import lesson_tools

        monkeypatch.setattr(lesson_tools, "query_one", AsyncMock(return_value=None))

        result = await lesson_tools.get_teaching_points_for_dance.ainvoke({"dance_id": 9999})

        assert "error" in result
        assert "9999" in result["error"]

    async def test_kb_is_none(self, monkeypatch):
        import lesson_tools

        monkeypatch.setattr(
            lesson_tools,
            "query_one",
            AsyncMock(return_value=_dance_row()),
        )
        monkeypatch.setattr(lesson_tools, "_get_manual_kb", lambda: None)

        result = await lesson_tools.get_teaching_points_for_dance.ainvoke({"dance_id": 42})
        assert "error" in result
        assert result.get("name") == "Test Dance"

    async def test_kb_not_loaded(self, monkeypatch):
        import lesson_tools

        kb = MagicMock()
        kb._loaded = False

        monkeypatch.setattr(
            lesson_tools,
            "query_one",
            AsyncMock(return_value=_dance_row()),
        )
        monkeypatch.setattr(lesson_tools, "_get_manual_kb", lambda: kb)

        result = await lesson_tools.get_teaching_points_for_dance.ainvoke({"dance_id": 42})
        assert "error" in result


# ---------------------------------------------------------------------------
# Behaviour: tempo-specific formation lookup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestTempoSpecificFormations:
    """Verify that Strathspey vs Reel/Jig resolves to the right KB section."""

    async def test_poussette_strathspey(self, monkeypatch):
        import lesson_tools

        section = {
            "section": "7.1",
            "title": "Poussette (Strathspey time)",
            "page": 105,
            "content": "Four bars in strathspey time.",
        }

        monkeypatch.setattr(
            lesson_tools,
            "query_one",
            AsyncMock(side_effect=[
                _dance_row(kind="Strathspey"),
                _crib_row("1s and 2s poussette"),
            ]),
        )
        monkeypatch.setattr(
            lesson_tools,
            "_get_manual_kb",
            lambda: _mock_kb({"poussette (in strathspey time)": section}),
        )

        result = await lesson_tools.get_teaching_points_for_dance.ainvoke({"dance_id": 42})
        assert "poussette" in result["formations_found"]
        assert len(result["teaching_points"]) == 1
        assert result["teaching_points"][0]["manual_term"] == "poussette (in strathspey time)"

    async def test_poussette_reel(self, monkeypatch):
        import lesson_tools

        section = {
            "section": "7.2",
            "title": "Poussette (Reel and Jig time)",
            "page": 106,
            "content": "Two bars in reel time.",
        }

        monkeypatch.setattr(
            lesson_tools,
            "query_one",
            AsyncMock(side_effect=[
                _dance_row(kind="Reel"),
                _crib_row("1s and 2s poussette"),
            ]),
        )
        monkeypatch.setattr(
            lesson_tools,
            "_get_manual_kb",
            lambda: _mock_kb({"poussette (in reel and jig time)": section}),
        )

        result = await lesson_tools.get_teaching_points_for_dance.ainvoke({"dance_id": 42})
        assert result["teaching_points"][0]["manual_term"] == "poussette (in reel and jig time)"

    async def test_poussette_jig(self, monkeypatch):
        import lesson_tools

        section = {
            "section": "7.2",
            "title": "Poussette (Reel and Jig time)",
            "page": 106,
            "content": "Two bars in jig time.",
        }

        monkeypatch.setattr(
            lesson_tools,
            "query_one",
            AsyncMock(side_effect=[
                _dance_row(kind="Jig"),
                _crib_row("1s and 2s poussette"),
            ]),
        )
        monkeypatch.setattr(
            lesson_tools,
            "_get_manual_kb",
            lambda: _mock_kb({"poussette (in reel and jig time)": section}),
        )

        result = await lesson_tools.get_teaching_points_for_dance.ainvoke({"dance_id": 42})
        assert result["teaching_points"][0]["manual_term"] == "poussette (in reel and jig time)"

    async def test_hands_round_strathspey(self, monkeypatch):
        import lesson_tools

        section = {
            "section": "4.5",
            "title": "Hands Round (Strathspey time)",
            "page": 60,
            "content": "Eight hands-round steps.",
        }

        monkeypatch.setattr(
            lesson_tools,
            "query_one",
            AsyncMock(side_effect=[
                _dance_row(kind="Strathspey"),
                _crib_row("all hands round and back"),
            ]),
        )
        monkeypatch.setattr(
            lesson_tools,
            "_get_manual_kb",
            lambda: _mock_kb({"hands round (in strathspey time)": section}),
        )

        result = await lesson_tools.get_teaching_points_for_dance.ainvoke({"dance_id": 42})
        assert "hands round" in result["formations_found"]
        assert result["teaching_points"][0]["manual_term"] == "hands round (in strathspey time)"


# ---------------------------------------------------------------------------
# Behaviour: crib with None value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestNullCrib:

    async def test_none_crib_yields_empty_formations(self, monkeypatch):
        """A None crib row should produce no formations and complete normally."""
        import lesson_tools

        monkeypatch.setattr(
            lesson_tools,
            "query_one",
            # First call → dance row; second call → None (no crib row)
            AsyncMock(side_effect=[_dance_row(), None]),
        )
        monkeypatch.setattr(lesson_tools, "_get_manual_kb", lambda: _mock_kb())

        result = await lesson_tools.get_teaching_points_for_dance.ainvoke({"dance_id": 42})
        assert "error" not in result
        assert result["formations_found"] == []
        assert result["teaching_points"] == []
