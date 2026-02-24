"""Pytest configuration.

This repo is not packaged as an installable module; tests import from the repo
root (e.g. `import lesson_tools`). When tests live under `tests/`, some pytest
import modes can omit the project root from `sys.path`.

We explicitly prepend the repo root so imports behave consistently.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
