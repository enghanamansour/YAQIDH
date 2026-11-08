"""Reads settings from the local `.env` file.

The real code lives in `src/envfile.py`, so the whole project has one reader.
"""
from __future__ import annotations

import sys
from pathlib import Path

# backend/ runs on its own, so the repository root must be importable.
_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.envfile import find_env_file, load_env, parse  # noqa: E402,F401
