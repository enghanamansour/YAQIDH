"""The merge gate.

The rule is fixed and written in plain code. The language model never takes
part in this decision: same input, same answer.

A pull request may merge only when, for the phase being checked:
  1. a scan exists for the exact commit that is about to merge, and
  2. that scan has no open findings.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .evidence import EvidenceLog
from .models import Finding, Scan


@dataclass
class _State:
    commit: str = ""
    open: dict[str, Finding] = field(default_factory=dict)


@dataclass
class ScanResult:
    opened: list[Finding]
    still_open: list[Finding]
    closed: list[str]  # fingerprints that disappeared in this scan

    @property
    def all_open(self) -> list[Finding]:
        return self.opened + self.still_open


@dataclass
class Decision:
    allowed: bool
    reason: str
    open_count: int = 0


class Gate:
    def __init__(self, evidence: EvidenceLog):
        self._states: dict[tuple[str, int, str], _State] = {}
        self._evidence = evidence

    def record_scan(self, scan: Scan) -> ScanResult:
        key = (scan.repo, scan.pr, scan.phase)
        state = self._states.setdefault(key, _State())
        previous = dict(state.open)
        current = {f.fingerprint: f for f in scan.findings}

        opened = [f for fp, f in current.items() if fp not in previous]
        still_open = [f for fp, f in current.items() if fp in previous]
        closed = [fp for fp in previous if fp not in current]

        state.commit = scan.commit
        state.open = current

        log = dict(repo=scan.repo, pr=scan.pr, commit=scan.commit, phase=scan.phase)
        self._evidence.append(
            **log,
            event="scan_recorded",
            data={"open": sorted(current), "opened": sorted(f.fingerprint for f in opened), "closed": sorted(closed)},
        )
        return ScanResult(opened=opened, still_open=still_open, closed=closed)

    def check(self, repo: str, pr: int, phase: str, commit: str) -> Decision:
        state = self._states.get((repo, pr, phase))
        if state is None:
            decision = Decision(False, "no_scan")
        elif state.commit != commit:
            decision = Decision(False, "stale_scan", len(state.open))
        elif state.open:
            decision = Decision(False, "open_findings", len(state.open))
        else:
            decision = Decision(True, "clean")
        self._evidence.append(
            repo=repo, pr=pr, commit=commit, phase=phase, event="gate_checked",
            data={"allowed": decision.allowed, "reason": decision.reason, "open_count": decision.open_count},
        )
        return decision
