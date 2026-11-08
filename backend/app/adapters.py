"""Turns findings from the team's checking tools into our own `Finding`.

This only reads their output. It never changes how the tools work.

Two shapes are accepted: the current one (`fingerprint`) and the first one
(`id`), so an older sample still works.
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


def _fingerprint(item: dict) -> str:
    value = item.get("fingerprint") or item.get("id")
    if not value:
        raise ValueError("a finding needs a 'fingerprint' (or the older 'id')")
    return str(value)


def _title(item: dict, rule: str) -> str:
    if item.get("title"):
        return item["title"]
    if item.get("component"):  # a vulnerable library: say which one
        return f"{rule} in {item['component']}"
    return _title_from_rule(rule)


def _description(item: dict) -> str:
    parts = [item.get("message", "")]
    if item.get("component"):
        parts.append(f"Affected component: {item['component']}.")
    if item.get("reported_as"):
        parts.append(f"The tool itself reported it as: {item['reported_as']}.")
    return " ".join(p.strip() for p in parts if p and p.strip())


def _verified_closed(item: dict) -> bool:
    """Only a finding the team's verifier proved closed leaves the list."""
    closure = item.get("closure") or {}
    return item.get("status") == "fixed" and closure.get("result") == "closed"


def from_team_finding(item: dict) -> Finding:
    """Accepts one finding in the shape the team's tools produce.

    Required: fingerprint (or id), rule, location, severity.
    Optional: title, message, snippet, cwe, confidence, component, reported_as.
    The fingerprint they give is kept as ours, so there is one id everywhere.
    """
    file, line = _split_location(item["location"])
    rule = item["rule"]
    return Finding(
        rule_id=rule,
        title=_title(item, rule),
        severity=item["severity"],
        file=file,
        line=line,
        description=_description(item),
        snippet=item.get("snippet", ""),
        external_id=_fingerprint(item),
        cwe=item.get("cwe"),
        confidence=item.get("confidence"),
    )


def from_team_findings(items: list[dict]) -> list[Finding]:
    """Everything still counts except what the verifier proved closed.

    A finding marked 'fixed' without a verified closure, or 'excepted', stays in
    the list. Whether an exception is valid is the team's policy engine's call,
    so this adapter never lets one through by itself (it fails closed).
    """
    return [from_team_finding(i) for i in items if not _verified_closed(i)]
