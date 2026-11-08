"""The one place that reads the local `.env` file (shared by src/ and backend/).

Keys live in one file on the developer's machine. The file is in `.gitignore`,
so it is never committed. Real environment variables always win over the file,
and a blank value in the file is ignored (it does not unset anything).

This module never prints or logs a value.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse(text: str) -> dict[str, str]:
    """KEY=VALUE per line. Supports comments, `export KEY=...` and quoted values."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not _KEY.match(key):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()  # trailing comment
        values[key] = value
    return values


def find_env_file() -> Path | None:
    explicit = os.environ.get("ENV_FILE")
    if explicit:
        path = Path(explicit)
        return path if path.is_file() else None
    # the repository root first (where the team keeps it), then where the server runs
    for base in (Path(__file__).resolve().parents[1], Path.cwd()):
        path = base / ".env"
        if path.is_file():
            return path
    return None


def load_env() -> Path | None:
    """Puts the file's values into the environment. Returns the file used, never its contents."""
    if os.environ.get("YAQIDH_NO_DOTENV") == "1":
        return None
    path = find_env_file()
    if path is None:
        return None
    for key, value in parse(path.read_text(encoding="utf-8")).items():
        if value:
            os.environ.setdefault(key, value)
    return path
