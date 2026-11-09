"""The developer's report on one release: what was found, how serious, and how long each finding took to close.

Everything here is plain code over two records that already exist: the evidence file (the current state) and
the history log (what happened, with times). Nothing is estimated and no model is involved. The numbers answer
the questions the business asks: how many findings, how many rounds, how long until they were closed, how long
people waited for approvals.

How the times are worked out:
  * first seen: the time of the stage's first scan (for a finding of the first scan) or of the re-scan that found it;
  * closed at: the time of the re-scan that proved it gone;
  * time to close: the difference. It is elapsed time between scans, so it includes waiting and weekends, and its
    precision is the scan frequency. It is not the developer's working time.
A finding that appeared only because the vulnerability database got newer ("new_from_db_update") is marked, so it is
not counted as something the developer introduced.
"""

from datetime import datetime

from src.gate import check_gate
from src.phases.status import release_status
from src.schema import Evidence, Finding, FindingStatus, Severity, StageName

TIMELINE_EVENTS = {"commit_received", "scan", "rescan", "policy_decision", "human_decision", "exception", "scan_not_run",
                   "security_waiting", "github_published"}
NOTES = ["elapsed_time", "scan_resolution", "db_origin", "low_awareness", "severity_source",
         "owasp_source"]  # the dashboard turns these codes into sentences

# OWASP Top 10 (2021) category by CWE. A fixed table of the common ones, not a guess: a finding without a known CWE
# has no category, except a library finding (it has a component), which is "Vulnerable and Outdated Components".
OWASP_BY_CWE = {
    "CWE-89": "A03 Injection", "CWE-79": "A03 Injection", "CWE-798": "A07 Identification and Authentication Failures",
    "CWE-287": "A07 Identification and Authentication Failures", "CWE-209": "A04 Insecure Design",
    "CWE-352": "A01 Broken Access Control", "CWE-22": "A01 Broken Access Control", "CWE-200": "A01 Broken Access Control",
    "CWE-1104": "A06 Vulnerable and Outdated Components",
}


def _owasp(f: Finding) -> str:
    if f.cwe.upper() in OWASP_BY_CWE:
        return OWASP_BY_CWE[f.cwe.upper()]
    return "A06 Vulnerable and Outdated Components" if f.component else ""


def _count(rows: list[dict], key: str) -> dict:
    out: dict[str, int] = {}
    for r in rows:
        name = (r[key] or "unknown").lower() if isinstance(r[key], str) else "unknown"
        out[name] = out.get(name, 0) + 1
    return out


def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _seconds(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    return max(0, int((end - start).total_seconds()))


def _finding_row(f: Finding, stage: str, first_scan: datetime | None, rescans: list[tuple[datetime, dict]], now: datetime) -> dict:
    first = first_scan if f.origin == "initial" else next(
        (t for t, d in rescans if f.fingerprint in d.get("new", []) + d.get("new_from_db_update", []) + d.get("reopened", [])), None)
    closed_at = None
    if f.closure is not None and f.closure.result == "closed":
        closed_at = next((t for t, d in rescans if f.fingerprint in d.get("closed", [])), f.closure.timestamp)
    end = closed_at or now
    rounds = (1 if first is not None else 0) + sum(1 for t, _ in rescans if first is not None and t > first and t <= end)
    return {
        "fingerprint": f.fingerprint, "stage": stage, "tool": f.tool, "rule": f.rule, "location": f.location,
        "severity": f.severity.value, "reported_as": f.reported_as, "component": f.component, "fixed_version": f.fixed_version,
        "cwe": f.cwe, "confidence": f.confidence, "status": f.status.value, "origin": f.origin,
        "first_seen": first.isoformat() if first else None,
        "closed_at": closed_at.isoformat() if closed_at else None,
        "seconds_to_close": _seconds(first, closed_at),
        "seconds_open": _seconds(first, end) if closed_at is None else None,
        "rounds": rounds,
        "explained": bool(f.explanation), "owasp": _owasp(f),
    }


def build_report(evidence: Evidence, history: list[dict]) -> dict:
    events = sorted(((_time(e["time"]), e) for e in history), key=lambda pair: pair[0])
    now = events[-1][0] if events else datetime.now().astimezone()

    first_scan: dict[str, datetime] = {}
    rescans: dict[str, list[tuple[datetime, dict]]] = {s.value: [] for s in StageName}
    for t, e in events:
        stage = (e.get("data") or {}).get("stage")
        if e["event"] == "scan" and stage and stage not in first_scan:
            first_scan[stage] = t
        elif e["event"] == "rescan" and stage in rescans:
            rescans[stage].append((t, e["data"]))

    findings = []
    for record in evidence.stages:
        s = record.name.value
        findings += [_finding_row(f, s, first_scan.get(s), rescans[s], now) for f in record.findings]
    findings.sort(key=lambda r: (r["status"] != "open", r["severity"] != "high", r["stage"], r["location"]))

    closed_times = [r["seconds_to_close"] for r in findings if r["seconds_to_close"] is not None]
    approvals = [{"stage": d.stage.value, "decision": d.decision, "by": d.by, "reason": d.reason,
                  "at": d.timestamp.isoformat(), "commit": d.commit} for d in evidence.human_decisions]

    waits = []  # how long a passing stage waited for its reviewer
    for stage in (s.value for s in StageName):
        passed = next((t for t, e in events if e["event"] == "policy_decision" and e["data"].get("stage") == stage
                       and e["data"].get("result") == "pass"), None)
        decided = next((t for t, e in events if passed and t > passed and e["event"] == "human_decision"
                        and e["data"].get("stage") == stage), None)
        if passed and decided:
            waits.append({"stage": stage, "seconds": _seconds(passed, decided)})

    status = release_status(evidence)
    gates = {target: check_gate(evidence, evidence.head_commit, target).model_dump() for target in ("staging", "main")} \
        if evidence.head_commit else {}
    open_ = [r for r in findings if r["status"] == FindingStatus.OPEN.value]
    return {
        "release_id": evidence.release_id, "repo": evidence.repo, "pr": evidence.pr_number, "branch": evidence.branch,
        "author": evidence.author, "head_commit": evidence.head_commit,
        "status": status.model_dump(mode="json"), "gates": gates,
        "summary": {
            "findings": len(findings),
            "by_reported": _count(findings, "reported_as"),  # the level the TOOL gave (critical, high, medium, low)
            "by_tool": _count(findings, "tool"),
            "by_owasp": _count([{**r, "owasp": r["owasp"] or "none"} for r in findings], "owasp"),
            "closed_percent": round(100 * sum(r["closed_at"] is not None for r in findings) / len(findings)) if findings else None,
            "open_blocking": sum(r["severity"] == Severity.HIGH.value for r in open_),
            "open_low": sum(r["severity"] == Severity.LOW.value for r in open_),
            "closed": sum(r["closed_at"] is not None for r in findings),
            "excepted": sum(r["status"] == FindingStatus.EXCEPTED.value for r in findings),
            "from_db_update": sum(r["origin"] == "new_from_db_update" for r in findings),
            "rounds": {s: (1 if s in first_scan else 0) + len(rescans[s]) for s in rescans},
            "time_to_close": {"count": len(closed_times),
                              "average_seconds": int(sum(closed_times) / len(closed_times)) if closed_times else None,
                              "max_seconds": max(closed_times) if closed_times else None},
            "longest_open_seconds": max((r["seconds_open"] for r in open_ if r["seconds_open"] is not None), default=None),
            "approval_waits": waits,
            "flaky_tests": sorted({t for record in evidence.stages for t in record.flaky_tests}),
        },
        "findings": findings,
        "approvals": approvals,
        "timeline": [{"at": t.isoformat(), "event": e["event"], "actor": e["actor"], "stage": (e.get("data") or {}).get("stage"),
                      "commit": (e.get("data") or {}).get("commit", "")[:8]}
                     for t, e in events if e["event"] in TIMELINE_EVENTS][-200:],
        "notes": NOTES,
    }
