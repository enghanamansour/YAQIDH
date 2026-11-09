"""Verifier: plain code that decides whether a finding was closed. It never imports from agent/ and never calls an LLM.

It compares the previous scan with a re-scan by fingerprint:
  fingerprint gone            -> closed
  fingerprint still there     -> still_open
  fingerprint not seen before -> new (or new_from_db_update, see below)
Same input always gives the same result. If it cannot be sure, it refuses (VerifierError)
instead of guessing, because a wrong "closed" is the worst mistake it can make.
"""

from pydantic import BaseModel, Field

from src.schema import Closure, Finding, FindingStatus


class VerifierError(Exception):
    """The re-scan cannot be trusted to decide anything. Never turned into 'closed'."""


class Verification(BaseModel):
    findings: list[Finding]  # the full updated list, sorted
    closed: list[str] = Field(default_factory=list)
    still_open: list[str] = Field(default_factory=list)
    new: list[str] = Field(default_factory=list)
    new_from_db_update: list[str] = Field(default_factory=list)
    reopened: list[str] = Field(default_factory=list)  # was closed before, found again
    warnings: list[str] = Field(default_factory=list)


def _is_closed(finding: Finding) -> bool:
    return finding.closure is not None and finding.closure.result == "closed"


def verify(
    previous: list[Finding],
    current: list[Finding],
    *,
    tools_run: set[str],
    previous_versions: dict[str, str] | None = None,
    current_versions: dict[str, str] | None = None,
    components_before: set[str] | None = None,
) -> Verification:
    """previous: findings from the earlier scan. current: findings from the re-scan.

    tools_run: the tools that really ran in the re-scan. A tool that did not run must not
    make its findings look closed, so this is required.
    components_before: every package the earlier scan saw (not only vulnerable ones). Used to tell a
    new Trivy finding caused by a newer vulnerability DB from one caused by a changed dependency.
    """
    previous_versions = previous_versions or {}
    current_versions = current_versions or {}

    if not tools_run:
        raise VerifierError("no tool ran in the re-scan, nothing to verify against")
    if len({f.fingerprint for f in previous}) != len(previous):
        raise VerifierError("duplicate fingerprints in the previous findings")
    if len({f.fingerprint for f in current}) != len(current):
        raise VerifierError("duplicate fingerprints in the re-scan")
    for f in previous:
        if f.tool not in tools_run and not _is_closed(f):
            raise VerifierError(f"{f.tool} did not run in the re-scan, cannot verify {f.fingerprint}")
    for f in current:
        if f.tool not in tools_run:
            raise VerifierError(f"finding {f.fingerprint} comes from {f.tool}, which is not in tools_run")
    old_rules, new_rules = previous_versions.get("semgrep-rules"), current_versions.get("semgrep-rules")
    if old_rules and new_rules and old_rules != new_rules:
        raise VerifierError(f"semgrep rules changed ({old_rules} -> {new_rules}), a re-scan cannot prove closure")

    result = Verification(findings=[])
    warnings = result.warnings
    now = {f.fingerprint: f for f in current}
    before = {f.fingerprint for f in previous}
    out: list[Finding] = []

    for p in previous:
        fp = p.fingerprint
        if fp in now:
            if _is_closed(p):
                # It had been closed and is back: a regression, so it starts again as an open finding.
                out.append(now[fp].model_copy(update={"origin": "new"}))
                result.reopened.append(fp)
            else:
                # A claim of "fixed" is disproved by the re-scan, so the status goes back to open.
                status = FindingStatus.OPEN if p.status == FindingStatus.FIXED else p.status
                out.append(p.model_copy(update={"status": status, "closure": Closure(result="still_open")}))
                result.still_open.append(fp)
        elif _is_closed(p):
            out.append(p)  # already closed earlier, keep as is
        else:
            out.append(p.model_copy(update={"status": FindingStatus.FIXED, "closure": Closure(result="closed")}))
            result.closed.append(fp)

    db_changed = (
        "trivy-db" in previous_versions
        and "trivy-db" in current_versions
        and previous_versions["trivy-db"] != current_versions["trivy-db"]
    )
    if db_changed and components_before is None:
        warnings.append("trivy DB changed but the earlier packages are unknown, new findings are not separated")
    if db_changed and result.closed:
        warnings.append("trivy DB changed, some closures may come from the DB and not from a fix")

    for fp, f in now.items():
        if fp in before:
            continue
        # Same package and version as before, but a newer DB: the code did not change, the DB learned more.
        from_db = (
            db_changed
            and f.tool == "trivy"
            and bool(f.component)
            and components_before is not None
            and f.component in components_before
        )
        origin = "new_from_db_update" if from_db else "new"
        out.append(f.model_copy(update={"origin": origin}))
        (result.new_from_db_update if from_db else result.new).append(fp)

    result.findings = sorted(out, key=lambda f: (f.location, f.fingerprint))
    for names in (result.closed, result.still_open, result.new, result.new_from_db_update, result.reopened):
        names.sort()
    return result
