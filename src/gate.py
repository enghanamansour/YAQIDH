"""The merge gate: may this exact commit merge? Plain code that only reads the evidence.

It decides nothing itself. It asks the release status (policy decisions + human approvals) and adds one
check: the scans must be of the commit that is about to merge. A scan or approval for an older commit
never opens a gate, so pushing new code after an approval closes the gate until it is checked again.
"""

from typing import Literal

from pydantic import BaseModel

from src.phases.status import release_status
from src.schema import Evidence, StageName

Target = Literal["staging", "main"]


class GateResult(BaseModel):
    allowed: bool
    reason: str  # a short code: clean, no_release, no_commit, stale_commit, stale_scan, blocked
    detail: list[str] = []
    status: str = ""


def check_gate(evidence: Evidence | None, commit: str, target: Target) -> GateResult:
    if evidence is None:
        return GateResult(allowed=False, reason="no_release", detail=["no evidence exists for this release"])
    if not commit:
        return GateResult(allowed=False, reason="no_commit", detail=["the commit to merge was not given"])
    if not evidence.head_commit:
        return GateResult(allowed=False, reason="no_commit", detail=["the release has no commit recorded yet"])
    if commit != evidence.head_commit:
        return GateResult(
            allowed=False,
            reason="stale_commit",
            detail=[f"the newest commit is {evidence.head_commit[:8]}, not {commit[:8]}"],
        )
    needed = [StageName.QA] if target == "staging" else [StageName.QA, StageName.SECURITY]
    old = [s.value for s in needed if evidence.stage(s).scanned_commit != commit]
    status = release_status(evidence)
    if old:
        return GateResult(
            allowed=False, reason="stale_scan", status=status.status.value,
            detail=[f"{', '.join(old)} was not scanned on commit {commit[:8]}"],
        )
    allowed = status.can_merge_to_staging if target == "staging" else status.can_merge_to_main
    if allowed:
        return GateResult(allowed=True, reason="clean", status=status.status.value, detail=status.reasons)
    return GateResult(allowed=False, reason="blocked", status=status.status.value, detail=status.reasons)
