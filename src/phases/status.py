"""Where a release stands, worked out from its evidence alone. Plain code, no agent, no stored state.

The same evidence always gives the same status, and the merge gates come from that status, so nothing
can open a gate by writing a status: the only way to open one is passing policy decisions plus human approval.
"""

from enum import Enum

from pydantic import BaseModel

from src.schema import Evidence, HumanDecision, StageName, StageRecord


class ReleaseStatus(str, Enum):
    NOT_STARTED = "not_started"
    QA_BLOCKED = "qa_blocked"  # policy says fail: back to the developer
    AWAITING_QA_APPROVAL = "awaiting_qa_approval"
    QA_REJECTED = "qa_rejected"  # a human rejected: back to the developer
    AWAITING_SECURITY_SCAN = "awaiting_security_scan"  # QA approved, security has not run yet
    SECURITY_BLOCKED = "security_blocked"
    AWAITING_SECURITY_APPROVAL = "awaiting_security_approval"
    SECURITY_REJECTED = "security_rejected"
    READY_TO_MERGE = "ready_to_merge"


class StatusReport(BaseModel):
    status: ReleaseStatus
    can_merge_to_staging: bool = False
    can_merge_to_main: bool = False
    reasons: list[str] = []


def _latest(evidence: Evidence, stage: StageName) -> HumanDecision | None:
    for d in reversed(evidence.human_decisions):
        if d.stage == stage:
            return d
    return None


def _passed(record: StageRecord) -> bool:
    return record.decision is not None and record.decision.result == "pass" and record.decision.decided_by == "policy_engine"


def _after_scan(decision: HumanDecision, record: StageRecord) -> bool:
    """A human decision only covers the results it was made on, so it must come after the latest scan."""
    return record.scanned_at is not None and decision.timestamp >= record.scanned_at


def release_status(evidence: Evidence) -> StatusReport:
    qa = evidence.stage(StageName.QA)
    sec = evidence.stage(StageName.SECURITY)

    if qa.scanned_at is None:
        return StatusReport(status=ReleaseStatus.NOT_STARTED, reasons=["qa has not been scanned"])
    if not _passed(qa):
        why = qa.decision.reasons if qa.decision else ["no policy decision yet"]
        return StatusReport(status=ReleaseStatus.QA_BLOCKED, reasons=why)

    qa_human = _latest(evidence, StageName.QA)
    if qa_human is not None and qa_human.decision == "reject" and _after_scan(qa_human, qa):
        return StatusReport(status=ReleaseStatus.QA_REJECTED, reasons=[qa_human.reason])
    # An approval stays valid after a QA re-run that still passes (the QA human does not approve twice).
    if qa_human is None or qa_human.decision != "approve":
        return StatusReport(status=ReleaseStatus.AWAITING_QA_APPROVAL, reasons=["qa passed, waiting for the QA reviewer"])

    staging = {"can_merge_to_staging": True}
    if sec.scanned_at is None:
        return StatusReport(status=ReleaseStatus.AWAITING_SECURITY_SCAN, reasons=["security has not been scanned"], **staging)
    if not _passed(sec):
        why = sec.decision.reasons if sec.decision else ["no policy decision yet"]
        return StatusReport(status=ReleaseStatus.SECURITY_BLOCKED, reasons=why, **staging)

    sec_human = _latest(evidence, StageName.SECURITY)
    if sec_human is None or not _after_scan(sec_human, sec):
        return StatusReport(
            status=ReleaseStatus.AWAITING_SECURITY_APPROVAL,
            reasons=["security passed, waiting for the security reviewer"],
            **staging,
        )
    if sec_human.decision == "reject":
        return StatusReport(status=ReleaseStatus.SECURITY_REJECTED, reasons=[sec_human.reason], **staging)
    return StatusReport(status=ReleaseStatus.READY_TO_MERGE, can_merge_to_main=True, reasons=["all checks passed and approved"], **staging)
