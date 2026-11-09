from datetime import timedelta
from pathlib import Path

import pytest

from src.phases.status import ReleaseStatus as S
from src.phases.status import release_status
from src.phases.workflow import Workflow, WorkflowError
from src.scanning import ScanResult
from src.schema import Finding, Severity, StageName
from src.service import ReleaseService, ServiceError
from src.storage import EvidenceStore

POLICY = Path(__file__).resolve().parents[1] / "config" / "policy.yaml"


class Scanner:
    """A fake stage runner. Change `findings` between calls to simulate the developer's fix."""

    def __init__(self, tool, findings=()):
        self.tool, self.findings, self.calls = tool, list(findings), 0

    def __call__(self, target):
        self.calls += 1
        return ScanResult(list(self.findings), {self.tool: "1"}, {self.tool})


def f(fp, tool, reported_as="high", severity=Severity.HIGH):
    return Finding(fingerprint=fp, tool=tool, severity=severity, reported_as=reported_as, location=f"{fp}.py:1")


@pytest.fixture
def qa():
    return Scanner("playwright")


@pytest.fixture
def sec():
    return Scanner("semgrep")


@pytest.fixture
def wf(tmp_path, qa, sec):
    svc = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY, {StageName.QA: qa, StageName.SECURITY: sec}, tmp_path)
    return Workflow(svc)


# --- the happy path ---

def test_clean_release_goes_through_both_approvals_to_main(wf):
    assert wf.submit("r").status == S.AWAITING_QA_APPROVAL
    r = wf.approve("r", "qa", "Noura")
    assert r.status == S.AWAITING_SECURITY_APPROVAL and r.can_merge_to_staging and not r.can_merge_to_main
    r = wf.approve("r", "security", "Omar")
    assert r.status == S.READY_TO_MERGE and r.can_merge_to_main


def test_nothing_can_be_merged_before_anyone_approves(wf):
    r = wf.submit("r")
    assert not r.can_merge_to_staging and not r.can_merge_to_main


# --- QA blocks ---

def test_failing_qa_blocks_and_cannot_be_approved(wf, qa):
    qa.findings = [f("Q1", "playwright")]
    assert wf.submit("r").status == S.QA_BLOCKED
    with pytest.raises(WorkflowError, match="qa_blocked"):
        wf.approve("r", "qa", "Noura")


def test_security_does_not_start_until_qa_is_approved(wf, sec):
    wf.submit("r")
    assert sec.calls == 0
    wf.approve("r", "qa", "Noura")
    assert sec.calls == 1


# --- the fix loop ---

def test_security_fix_reruns_qa_then_security_and_only_security_needs_a_new_approval(wf, qa, sec):
    wf.submit("r")
    sec.findings = [f("S1", "semgrep")]
    assert wf.approve("r", "qa", "Noura").status == S.SECURITY_BLOCKED

    sec.findings = []  # the developer fixes it in the same PR
    r = wf.push("r")
    assert qa.calls == 2  # QA re-ran by itself
    assert r.status == S.AWAITING_SECURITY_APPROVAL  # not QA again: QA's approval still stands
    assert wf.status("r").can_merge_to_staging

    assert wf.approve("r", "security", "Omar").status == S.READY_TO_MERGE
    finding = wf.service.store.get("r").stage(StageName.SECURITY).findings[0]
    assert finding.closure.result == "closed"  # closed by the verifier's re-scan, nobody claimed it


def test_a_fix_that_breaks_qa_goes_back_to_the_developer_and_security_does_not_run(wf, qa, sec):
    wf.submit("r")
    sec.findings = [f("S1", "semgrep")]
    wf.approve("r", "qa", "Noura")
    sec.findings = []
    qa.findings = [f("Q1", "playwright")]  # the fix broke a QA check
    r = wf.push("r")
    assert r.status == S.QA_BLOCKED and not r.can_merge_to_staging
    assert sec.calls == 1  # security was not re-scanned


def test_push_before_qa_approval_only_reruns_qa(wf, qa, sec):
    qa.findings = [f("Q1", "playwright")]
    wf.submit("r")
    qa.findings = []
    assert wf.push("r").status == S.AWAITING_QA_APPROVAL
    assert sec.calls == 0


def test_push_on_a_new_release_acts_like_submit(wf):
    assert wf.push("fresh").status == S.AWAITING_QA_APPROVAL


def test_old_security_approval_does_not_cover_a_later_scan(wf, sec):
    wf.submit("r")
    wf.approve("r", "qa", "Noura")
    wf.approve("r", "security", "Omar")
    assert wf.status("r").can_merge_to_main
    wf.push("r")  # new code: a new scan happened after the approval
    r = wf.status("r")
    assert r.status == S.AWAITING_SECURITY_APPROVAL and not r.can_merge_to_main


# --- rejection ---

def test_rejection_sends_the_release_back_with_the_reason(wf):
    wf.submit("r")
    wf.approve("r", "qa", "Noura")
    r = wf.reject("r", "security", "Omar", "token must be rotated first")
    assert r.status == S.SECURITY_REJECTED and r.reasons == ["token must be rotated first"] and not r.can_merge_to_main


def test_new_push_clears_a_rejection(wf):
    wf.submit("r")
    wf.reject("r", "qa", "Noura", "login flow unclear")
    assert wf.status("r").status == S.QA_REJECTED
    assert wf.push("r").status == S.AWAITING_QA_APPROVAL


def test_rejection_needs_a_reason_and_a_name(wf):
    wf.submit("r")
    with pytest.raises(ServiceError, match="reason"):
        wf.reject("r", "qa", "Noura", "  ")
    with pytest.raises(ServiceError, match="name"):
        wf.approve("r", "qa", " ")


def test_cannot_approve_security_while_waiting_for_qa(wf):
    wf.submit("r")
    with pytest.raises(WorkflowError):
        wf.approve("r", "security", "Omar")


# --- exceptions ---

def test_medium_finding_with_a_human_approved_exception_lets_security_pass(wf, sec):
    wf.submit("r")
    sec.findings = [f("S1", "trivy", reported_as="medium")]
    wf.approve("r", "qa", "Noura")
    assert wf.status("r").status == S.SECURITY_BLOCKED
    r = wf.grant_exception("r", "security", "S1", "upgrade planned next sprint", "Omar")
    assert r.status == S.AWAITING_SECURITY_APPROVAL


def test_high_finding_cannot_be_excepted_the_policy_ignores_it(wf, sec):
    wf.submit("r")
    sec.findings = [f("S1", "semgrep", reported_as="high")]
    wf.approve("r", "qa", "Noura")
    r = wf.grant_exception("r", "security", "S1", "we accept the risk", "Omar")
    assert r.status == S.SECURITY_BLOCKED
    assert any("not allowed for high" in x for x in r.reasons)


def test_exception_without_justification_or_approver_is_refused(wf, sec):
    wf.submit("r")
    sec.findings = [f("S1", "trivy", reported_as="medium")]
    wf.approve("r", "qa", "Noura")
    with pytest.raises(ServiceError):
        wf.grant_exception("r", "security", "S1", "", "Omar")
    with pytest.raises(ServiceError):
        wf.grant_exception("r", "security", "S1", "later", "")


# --- the status is worked out from evidence only ---

def test_status_cannot_be_forged_by_a_decision_that_is_not_from_the_policy_engine(wf):
    wf.submit("r")
    evidence = wf.service.store.get("r")
    assert release_status(evidence).status == S.AWAITING_QA_APPROVAL
    evidence.stage(StageName.QA).decision = None
    assert release_status(evidence).status == S.QA_BLOCKED  # no decision means no pass


def test_approval_older_than_the_scan_is_not_valid_for_security(wf):
    wf.submit("r")
    wf.approve("r", "qa", "Noura")
    wf.approve("r", "security", "Omar")
    evidence = wf.service.store.get("r")
    evidence.stage(StageName.SECURITY).scanned_at += timedelta(seconds=5)
    assert release_status(evidence).status == S.AWAITING_SECURITY_APPROVAL
