"""Turns findings from the team's checking tools into our own `Finding`.

This only reads their output. It never changes how the tools work.
"""
from __future__ import annotations

import re

from .models import Finding


def _title_from_rule(rule: str) -> str:
    """'python.flask.security.audit.debug-enabled' -> 'debug enabled (flask)'."""
    parts = rule.split(".")
    name = parts[-1].replace("-", " ").replace("_", " ")
    family = parts[1] if len(parts) > 2 else ""
    return f"{name} ({family})" if family else name


def _split_location(location: str) -> tuple[str, int | None]:
    """'app.py:12' -> ('app.py', 12). A path with no line number is kept as is."""
    m = re.match(r"^(.*):(\d+)$", location.strip())
    if m:
        return m.group(1), int(m.group(2))
    return location.strip(), None


def from_team_finding(item: dict) -> Finding:
    """Accepts one finding in the shape the team's tools produce.

    Required: id, rule, location, severity. Optional: message, snippet. The
    id they give is kept as the fingerprint, so there is one id everywhere.
    """
    file, line = _split_location(item["location"])
    rule = item["rule"]
    return Finding(
        rule_id=rule,
        title=item.get("title") or _title_from_rule(rule),
        severity=item["severity"],
        file=file,
        line=line,
        description=item.get("message", ""),
        snippet=item.get("snippet", ""),
        external_id=item["id"],
    )


def from_team_findings(items: list[dict]) -> list[Finding]:
    """Only findings that are still open count. Fixed or excepted ones are skipped."""
    return [from_team_finding(i) for i in items if i.get("status", "open") == "open"]
