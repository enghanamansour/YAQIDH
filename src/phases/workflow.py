"""The release flow: QA first, then security, with a human approval after each. Plain code, no agent.

  PR opened   -> submit(): QA scan + policy.        pass -> wait for the QA reviewer, fail -> back to the developer.
  QA approved -> security scan + policy.            pass -> wait for the security reviewer, fail -> back to the developer.
  Dev pushes  -> push(): QA re-runs by itself; if it still passes (and QA was already approved) security
                 re-scans and the verifier decides what closed. Only the security reviewer approves again.
The agent can scan and explain through the MCP server but never calls this: approvals are for humans.
"""

from src.phases.status import ReleaseStatus, StatusReport, release_status
from src.schema import StageName
from src.service import ReleaseService, ServiceError
from src.tools.base import ToolError

QA, SECURITY = "qa", "security"


class WorkflowError(ServiceError):
    """The step is not allowed in the release's current status."""


class Workflow:
    def __init__(self, service: ReleaseService):
        self.service = service

    def status(self, release_id: str) -> StatusReport:
        return release_status(self.service.store.get(release_id))

    # --- developer side ---

    def submit(self, release_id: str) -> StatusReport:
        """A PR was opened: first QA scan."""
        self.service.run_scan(release_id, QA)
        self.service.evaluate_policy(release_id, QA)
        return self.status(release_id)

    def push(self, release_id: str) -> StatusReport:
        """The developer pushed new code to the same PR. Re-runs what is needed, in order."""
        if not self.service.store.exists(release_id):
            return self.submit(release_id)
        if not self.service.store.get(release_id).stage(StageName.QA).tool_versions:
            return self.submit(release_id)
        self.service.verify_fix(release_id, QA)
        self.service.evaluate_policy(release_id, QA)
        status = self.status(release_id)
        if status.can_merge_to_staging:  # QA passes and was already approved: security follows by itself
            self._security_step(release_id)
        return self.status(release_id)

    # --- human side ---

    def approve(self, release_id: str, stage: str, by: str, reason: str = "") -> StatusReport:
        self._require(release_id, stage, "approve")
        self.service.add_human_decision(release_id, stage, "approve", by, reason)
        if stage == QA:
            try:
                self._security_step(release_id)  # merge to staging is now allowed, security starts
            except ToolError as e:
                # SCAN_SOURCE=ci and the CI results have not arrived yet. The approval stands; security starts by
                # itself when they arrive (apply_security_results). Before, this answered the reviewer with a 500.
                self.service._log(release_id, "security_waiting", "system", reason=str(e)[:300])
        return self.status(release_id)

    def reject(self, release_id: str, stage: str, by: str, reason: str) -> StatusReport:
        self._require(release_id, stage, "reject")
        self.service.add_human_decision(release_id, stage, "reject", by, reason)
        return self.status(release_id)

    def grant_exception(
        self, release_id: str, stage: str, fingerprint: str, justification: str, approved_by: str
    ) -> StatusReport:
        self.service.grant_exception(release_id, stage, fingerprint, justification, approved_by)
        return self.status(release_id)

    def apply_qa_results(self, release_id: str) -> StatusReport:
        """QA results arrived (from CI): scan, or re-scan with the verifier, and ask the policy. Security is not started here:
        it starts by itself when its own results arrive or when the QA reviewer approves."""
        if self.service.store.get(release_id).stage(StageName.QA).tool_versions:
            self.service.verify_fix(release_id, QA)
        else:
            self.service.run_scan(release_id, QA)
        self.service.evaluate_policy(release_id, QA)
        return self.status(release_id)

    def apply_security_results(self, release_id: str) -> StatusReport:
        """Security results arrived (from CI). If it is security's turn, scan or re-scan with them and ask the policy."""
        if self.status(release_id).status in (
            ReleaseStatus.AWAITING_SECURITY_SCAN, ReleaseStatus.SECURITY_BLOCKED, ReleaseStatus.AWAITING_SECURITY_APPROVAL,
            ReleaseStatus.SECURITY_REJECTED, ReleaseStatus.READY_TO_MERGE,
        ):
            self._security_step(release_id)
        return self.status(release_id)

    # --- internals ---

    def _security_step(self, release_id: str) -> None:
        if self.service.store.get(release_id).stage(StageName.SECURITY).tool_versions:
            self.service.verify_fix(release_id, SECURITY)
        else:
            self.service.run_scan(release_id, SECURITY)
        self.service.evaluate_policy(release_id, SECURITY)

    def _require(self, release_id: str, stage: str, action: str) -> None:
        waiting = {QA: ReleaseStatus.AWAITING_QA_APPROVAL, SECURITY: ReleaseStatus.AWAITING_SECURITY_APPROVAL}
        if stage not in waiting:
            raise WorkflowError(f"unknown stage {stage!r}")
        current = self.status(release_id).status
        if current != waiting[stage]:
            raise WorkflowError(f"cannot {action} {stage}: the release is '{current.value}', not '{waiting[stage].value}'")

