"""The operations the agent may use, as plain code. The MCP server is only a thin wrapper around this.

The agent can: start a scan, read findings and evidence, ask for a re-scan check, ask the policy engine
for a decision, and add explanation text. It cannot: choose tools or targets, set a finding's status,
write a closure, record an exception, or record a human decision.
"""

import threading
from contextlib import contextmanager
from pathlib import Path

from src.phases.status import ReleaseStatus, release_status
from src.history import HistoryLog
from src.policy import evaluate_policy, load_policy
from src.scanning import CURRENT_RELEASE, NoRunner, Runner, ScanResult
from src.schema import (
    Decision,
    Evidence,
    Explanation,
    ExceptionRecord,
    Finding,
    FindingStatus,
    HumanDecision,
    PendingScan,
    StageName,
    utcnow,
)
from src.storage import EvidenceStore
from src.verifier import Verification, verify

MAX_EXPLANATION = 4000

# Security may only be scanned once QA passed and a QA reviewer approved. Checked here, not only in the
# workflow, so the agent cannot skip a stage by calling the tool directly.
BEFORE_SECURITY = {
    ReleaseStatus.NOT_STARTED,
    ReleaseStatus.QA_BLOCKED,
    ReleaseStatus.AWAITING_QA_APPROVAL,
    ReleaseStatus.QA_REJECTED,
}


class ServiceError(Exception):
    """The request is not allowed or makes no sense. Never turned into a silent success."""


class ReleaseService:
    def __init__(
        self, store: EvidenceStore, policy_path: Path, runners: dict[StageName, Runner], target: Path,
        history: HistoryLog | None = None,
    ):
        self.store = store
        self.history = history
        self.policy_path = Path(policy_path)
        self.runners = runners
        self.target = Path(target)
        self._lock = threading.Lock()  # one writer at a time, so two calls never overwrite each other

    @contextmanager
    def _locked(self, release_id: str):
        """One writer at a time for this release: across threads here, and across processes through the store's file lock."""
        with self._lock, self.store.locked(release_id):
            yield

    def _log(self, release_id: str, event: str, actor: str, **data) -> None:
        if self.history is not None:
            self.history.append(release_id, event, actor, data)

    def _run(self, runner: Runner, release_id: str) -> ScanResult:
        token = CURRENT_RELEASE.set(release_id)
        try:
            return runner(self.target)
        finally:
            CURRENT_RELEASE.reset(token)

    def _runner(self, stage: StageName) -> Runner:
        runner = self.runners.get(stage)
        if runner is None:
            raise NoRunner(f"no tools are registered for stage '{stage.value}', nothing was scanned")
        return runner

    @staticmethod
    def _stage(name: str) -> StageName:
        try:
            return StageName(name)
        except ValueError as e:
            raise ServiceError(f"unknown stage {name!r}, use 'qa' or 'security'") from e

    def run_scan(self, release_id: str, stage: str) -> dict:
        """First scan of a stage. A second scan would overwrite history, so it is refused (use verify_fix)."""
        name = self._stage(stage)
        runner = self._runner(name)
        with self._locked(release_id):
            evidence = self.store.get(release_id) if self.store.exists(release_id) else self.store.create(release_id)
            self._check_order(evidence, name)
            record = evidence.stage(name)
            if record.tool_versions:
                raise ServiceError(f"stage '{stage}' of {release_id} was already scanned, use verify_fix to re-scan")
            result: ScanResult = self._run(runner, release_id)
            record.findings = result.findings
            record.tool_versions = result.versions
            record.components = sorted(result.components)
            record.flaky_tests = sorted(result.flaky)
            record.scanned_at = utcnow()
            record.scanned_commit = evidence.head_commit
            record.decision = None
            self.store.save(evidence)
        self._log(release_id, "scan", "agent", stage=stage, commit=record.scanned_commit, findings=len(result.findings),
                  tool_versions=result.versions, flaky_tests=record.flaky_tests)
        return {"release_id": release_id, "stage": stage, "findings": len(result.findings), "tool_versions": result.versions}

    def verify_fix(self, release_id: str, stage: str) -> dict:
        """Re-scan and let the verifier compare with the earlier scan. Only the verifier writes closures."""
        name = self._stage(stage)
        runner = self._runner(name)
        with self._locked(release_id):
            evidence = self.store.get(release_id)
            self._check_order(evidence, name)
            record = evidence.stage(name)
            if not record.tool_versions:
                raise ServiceError(f"stage '{stage}' of {release_id} was never scanned, use run_scan first")
            result = self._run(runner, release_id)
            verification: Verification = verify(
                record.findings,
                result.findings,
                tools_run=result.tools_run,
                previous_versions=record.tool_versions,
                current_versions=result.versions,
                components_before=set(record.components) if record.components else None,
            )
            record.findings = verification.findings
            record.tool_versions = result.versions
            record.components = sorted(result.components)
            record.flaky_tests = sorted(result.flaky)
            record.scanned_at = utcnow()
            record.scanned_commit = evidence.head_commit
            record.decision = None  # the old decision is stale after a re-scan, it must be asked for again
            self.store.save(evidence)
        out = verification.model_dump(mode="json", exclude={"findings"})
        self._log(release_id, "rescan", "agent", stage=stage, commit=record.scanned_commit, **out)
        return {"release_id": release_id, "stage": stage, **out}

    def get_findings(self, release_id: str, stage: str) -> list[dict]:
        name = self._stage(stage)
        findings = self.store.get(release_id).stage(name).findings
        return [f.model_dump(mode="json") for f in findings]

    def evaluate_policy(self, release_id: str, stage: str) -> dict:
        name = self._stage(stage)
        policy = load_policy(self.policy_path)  # read on every call, so an edited policy takes effect at once
        with self._locked(release_id):
            evidence = self.store.get(release_id)
            record = evidence.stage(name)
            if not record.tool_versions:
                raise ServiceError(f"stage '{stage}' of {release_id} was never scanned, no decision can be made")
            decision: Decision = evaluate_policy(record.findings, policy)
            record.decision = decision
            self.store.save(evidence)
        self._log(release_id, "policy_decision", "policy_engine", stage=stage, result=decision.result, reasons=decision.reasons)
        return decision.model_dump(mode="json")

    def append_evidence(self, release_id: str, stage: str, fingerprint: str, text: str) -> dict:
        """The one write the agent has: explanation text on a finding, always labelled source 'Yaqidh'."""
        name = self._stage(stage)
        text = text.strip()
        if not text:
            raise ServiceError("explanation text is empty")
        if len(text) > MAX_EXPLANATION:
            raise ServiceError(f"explanation is longer than {MAX_EXPLANATION} characters")
        with self._locked(release_id):
            evidence = self.store.get(release_id)
            finding = self._find(evidence, name, fingerprint)
            finding.explanation = Explanation(text=text)
            self.store.save(evidence)
        self._log(release_id, "explanation", "agent", stage=stage, fingerprint=fingerprint, source="Yaqidh", text=text)
        return {"release_id": release_id, "stage": stage, "fingerprint": fingerprint, "source": "Yaqidh"}

    @staticmethod
    def _check_order(evidence: Evidence, name: StageName) -> None:
        if name == StageName.SECURITY:
            status = release_status(evidence).status
            if status in BEFORE_SECURITY:
                raise ServiceError(f"security cannot be scanned yet: the release is '{status.value}', QA must pass and be approved first")

    @staticmethod
    def _find(evidence: Evidence, name: StageName, fingerprint: str) -> Finding:
        for f in evidence.stage(name).findings:
            if f.fingerprint == fingerprint:
                return f
        raise ServiceError(f"no finding {fingerprint} in stage '{name.value}'")

    def get_evidence(self, release_id: str) -> dict:
        return self.store.get(release_id).model_dump(mode="json")

    # --- Writes that belong to humans. They are NOT exposed through the MCP server. ---

    def add_human_decision(self, release_id: str, stage: str, decision: str, by: str, reason: str) -> dict:
        name = self._stage(stage)
        if decision not in ("approve", "reject"):
            raise ServiceError("decision must be 'approve' or 'reject'")
        if not by.strip():
            raise ServiceError("a human decision needs the name of the person who made it")
        if decision == "reject" and not reason.strip():
            raise ServiceError("a rejection needs a reason, so the developer knows what to fix")
        with self._locked(release_id):
            evidence = self.store.get(release_id)
            evidence.human_decisions.append(
                HumanDecision(stage=name, decision=decision, by=by.strip(), reason=reason.strip(), commit=evidence.head_commit)
            )
            self.store.save(evidence)
        self._log(release_id, "human_decision", by.strip(), stage=stage, decision=decision, reason=reason.strip(),
                  commit=evidence.head_commit)
        return {"release_id": release_id, "stage": stage, "decision": decision, "by": by.strip()}

    def grant_exception(
        self, release_id: str, stage: str, fingerprint: str, justification: str, approved_by: str
    ) -> dict:
        """Record a human-approved exception. The policy engine still decides whether it counts."""
        name = self._stage(stage)
        if not justification.strip() or not approved_by.strip():
            raise ServiceError("an exception needs a justification and the name of the approving person")
        with self._locked(release_id):
            evidence = self.store.get(release_id)
            finding = self._find(evidence, name, fingerprint)
            if finding.status != FindingStatus.OPEN:
                raise ServiceError(f"{fingerprint} is {finding.status.value}, only an open finding can get an exception")
            finding.status = FindingStatus.EXCEPTED
            finding.exception = ExceptionRecord(justification=justification.strip(), approved_by=approved_by.strip())
            self.store.save(evidence)
        self._log(release_id, "exception", approved_by.strip(), stage=stage, fingerprint=fingerprint,
                  justification=justification.strip())
        return self.evaluate_policy(release_id, stage)

    def set_pull_request(self, release_id: str, repo: str, pr_number: int, author: str = "", branch: str = "") -> None:
        with self._locked(release_id):
            evidence = self.store.get(release_id) if self.store.exists(release_id) else self.store.create(release_id)
            evidence.repo, evidence.pr_number = repo, pr_number
            evidence.author, evidence.branch = author[:100], branch[:200]
            self.store.save(evidence)

    def set_head_commit(self, release_id: str, commit: str) -> dict:
        """The system (not the agent) records the newest commit of the pull request. It starts the release if new."""
        commit = commit.strip()
        if not commit or len(commit) > 64:
            raise ServiceError("a commit id is required")
        with self._locked(release_id):
            evidence = self.store.get(release_id) if self.store.exists(release_id) else self.store.create(release_id)
            changed = evidence.head_commit != commit
            evidence.head_commit = commit
            self.store.save(evidence)
        if changed:
            self._log(release_id, "commit_received", "system", commit=commit)
        return {"release_id": release_id, "head_commit": commit, "changed": changed}

    def submit_scan_results(
        self, release_id: str, commit: str, findings: list[Finding], versions: dict[str, str],
        tools_run: list[str], components: list[str], by: str = "ci",
    ) -> dict:
        """Store the security results a CI job sent for the newest commit. They are used when the stage's turn comes."""
        missing = {"semgrep", "trivy"} - set(tools_run)
        if missing:
            raise ServiceError(f"the results must come from both tools; missing: {', '.join(sorted(missing))}")
        if not {"semgrep-rules", "trivy", "trivy-db"} <= versions.keys():
            raise ServiceError("the results must include the versions semgrep-rules, trivy and trivy-db")
        clean = [
            f.model_copy(update={"status": FindingStatus.OPEN, "explanation": None, "closure": None, "exception": None,
                                 "origin": "initial"})
            for f in findings
        ]
        with self._locked(release_id):
            if not self.store.exists(release_id):
                raise ServiceError(f"no release {release_id}: the pull request event must arrive first")
            evidence = self.store.get(release_id)
            if commit != evidence.head_commit:
                raise ServiceError(f"these results are for {commit[:8]}, but the newest commit is {evidence.head_commit[:8]}")
            evidence.pending_scan = PendingScan(commit=commit, findings=clean, versions=versions,
                                                tools_run=sorted(tools_run), components=sorted(components))
            self.store.save(evidence)
        self._log(release_id, "scan_results_received", by, commit=commit, findings=len(clean), tool_versions=versions)
        return {"release_id": release_id, "commit": commit, "findings": len(clean)}
