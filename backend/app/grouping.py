"""Merges findings that are really the same problem.

Several rules can fire on one line (for example three rules for one SQL
injection). The developer should see one problem and one explanation, not
three. Each fingerprint is still tracked separately by the gate, so merging
here only changes what is shown, never what blocks or passes.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import SEVERITY_ORDER, Finding


@dataclass
class Group:
    findings: list[Finding]

    @property
    def representative(self) -> Finding:
        return sorted(self.findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.rule_id))[0]

    @property
    def severity(self) -> str:
        return "high" if any(f.severity == "high" for f in self.findings) else "low"

    @property
    def fingerprints(self) -> list[str]:
        return sorted(f.fingerprint for f in self.findings)

    @property
    def rules(self) -> list[str]:
        return sorted({f.rule_id for f in self.findings})

    @property
    def low_confidence(self) -> bool:
        """True only when every finding in the group says the tool is unsure."""
        return all(f.confidence == "low" for f in self.findings)


def _key(f: Finding) -> tuple:
    # A finding with no line number (like a vulnerable library) is never merged:
    # many different problems share the same file there.
    if f.line is None:
        return ("single", f.fingerprint)
    return (f.file, f.line, (f.cwe or "").strip().lower())


def group_findings(findings: list[Finding]) -> list[Group]:
    buckets: dict[tuple, list[Finding]] = {}
    for f in findings:
        buckets.setdefault(_key(f), []).append(f)
    groups = [Group(items) for items in buckets.values()]
    return sorted(groups, key=lambda g: (SEVERITY_ORDER[g.severity], g.representative.file,
                                         g.representative.line or 0))
