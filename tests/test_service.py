from pathlib import Path

import pytest

from src.scanning import NoRunner, ScanResult, dedupe
from src.schema import Finding, FindingStatus, Severity, StageName
from src.service import ReleaseService, ServiceError
from src.storage import EvidenceStore

POLICY = Path(__file__).resolve().parents[1] / "config" / "policy.yaml"


def finding(fp, severity=Severity.HIGH, tool="semgrep", location="a.py:1"):
    return Finding(fingerprint=fp, tool=tool, severity=severity, location=location)


class FakeScanner:
    """Stands in for the real tools. `findings` can be changed between calls to simulate a fix."""

    def __init__(self, findings, versions=None):
        self.findings = findings
        self.versions = versions or {"semgrep-rules": "r1", "trivy": "1", "trivy-db": "d1"}
        self.calls = 0

    def __call__(self, target):
        self.calls += 1
        return ScanResult(list(self.findings), dict(self.versions), {"semgrep", "trivy"}, {"flask==0.12.2"})


@pytest.fixture
def scanner():
    return FakeScanner([finding("F-1"), finding("F-2", Severity.LOW)])


@pytest.fixture
def service(tmp_path, scanner):
    return ReleaseService(EvidenceStore(tmp_path / "data"), POLICY, {StageName.SECURITY: scanner}, tmp_path)


# --- run_scan ---

def test_run_scan_stores_findings_versions_and_components(service):
    out = service.run_scan("r1", "security")
    assert out["findings"] == 2
    stage = service.store.get("r1").stage(StageName.SECURITY)
    assert [f.fingerprint for f in stage.findings] == ["F-1", "F-2"]
    assert stage.tool_versions["trivy-db"] == "d1"
    assert stage.components == ["flask==0.12.2"]


def test_run_scan_twice_is_refused_so_history_is_not_overwritten(service):
    service.run_scan("r1", "security")
    with pytest.raises(ServiceError, match="already scanned"):
        service.run_scan("r1", "security")


def test_stage_without_tools_fails_loudly_and_writes_nothing(service):
    with pytest.raises(NoRunner, match="no tools are registered for stage 'qa'"):
        service.run_scan("r1", "qa")
    assert not service.store.exists("r1")


def test_unknown_stage_is_rejected(service):
    with pytest.raises(ServiceError, match="unknown stage"):
        service.run_scan("r1", "deploy")


def test_duplicate_fingerprints_in_a_scan_become_one_finding():
    a, b = finding("F-1", location="a.py:5"), finding("F-1", location="a.py:9")
    assert [f.location for f in dedupe([b, a])] == ["a.py:5"]


# --- policy ---

def test_evaluate_policy_stores_the_decision(service):
    service.run_scan("r1", "security")
    d = service.evaluate_policy("r1", "security")
    assert d["result"] == "fail" and d["decided_by"] == "policy_engine"
    assert service.store.get("r1").stage(StageName.SECURITY).decision.result == "fail"


def test_evaluate_policy_before_any_scan_is_refused(service):
    service.store.create("r1")
    with pytest.raises(ServiceError, match="never scanned"):
        service.evaluate_policy("r1", "security")


# --- verify_fix ---

def test_verify_fix_closes_a_finding_that_disappeared(service, scanner):
    service.run_scan("r1", "security")
    service.evaluate_policy("r1", "security")
    scanner.findings = [finding("F-2", Severity.LOW)]
    out = service.verify_fix("r1", "security")
    assert out["closed"] == ["F-1"] and "findings" not in out
    stage = service.store.get("r1").stage(StageName.SECURITY)
    f1 = next(f for f in stage.findings if f.fingerprint == "F-1")
    assert f1.status == FindingStatus.FIXED and f1.closure.result == "closed"
    assert stage.decision is None  # the old decision is stale and must be asked for again
    assert service.evaluate_policy("r1", "security")["result"] == "pass"


def test_verify_fix_keeps_a_finding_open_when_it_is_still_there(service):
    service.run_scan("r1", "security")
    assert service.verify_fix("r1", "security")["still_open"] == ["F-1", "F-2"]
    assert service.evaluate_policy("r1", "security")["result"] == "fail"


def test_verify_fix_reports_new_findings(service, scanner):
    service.run_scan("r1", "security")
    scanner.findings = scanner.findings + [finding("F-9")]
    assert service.verify_fix("r1", "security")["new"] == ["F-9"]


def test_verify_fix_without_a_first_scan_is_refused(service):
    service.store.create("r1")
    with pytest.raises(ServiceError, match="never scanned"):
        service.verify_fix("r1", "security")


def test_verify_fix_refuses_when_semgrep_rules_changed(service, scanner):
    from src.verifier import VerifierError

    service.run_scan("r1", "security")
    scanner.findings = []
    scanner.versions = {**scanner.versions, "semgrep-rules": "r2"}
    with pytest.raises(VerifierError):
        service.verify_fix("r1", "security")
    # nothing was written: the findings are still open
    assert service.store.get("r1").stage(StageName.SECURITY).findings[0].status == FindingStatus.OPEN


# --- the agent's only write ---

def test_append_evidence_labels_the_text_as_yaqidh(service):
    service.run_scan("r1", "security")
    out = service.append_evidence("r1", "security", "F-1", "  SQL is built from user input.  ")
    assert out["source"] == "Yaqidh"
    f = service.store.get("r1").stage(StageName.SECURITY).findings[0]
    assert f.explanation.text == "SQL is built from user input." and f.explanation.source == "Yaqidh"
    assert f.status == FindingStatus.OPEN and f.closure is None  # nothing but the text changed


@pytest.mark.parametrize("text", ["", "   ", "x" * 4001])
def test_append_evidence_rejects_empty_or_huge_text(service, text):
    service.run_scan("r1", "security")
    with pytest.raises(ServiceError):
        service.append_evidence("r1", "security", "F-1", text)


def test_append_evidence_for_an_unknown_finding_is_refused(service):
    service.run_scan("r1", "security")
    with pytest.raises(ServiceError, match="no finding F-404"):
        service.append_evidence("r1", "security", "F-404", "text")


# --- reading ---

def test_get_findings_and_get_evidence(service):
    service.run_scan("r1", "security")
    assert [f["fingerprint"] for f in service.get_findings("r1", "security")] == ["F-1", "F-2"]
    assert service.get_evidence("r1")["release_id"] == "r1"


def test_bad_release_id_cannot_escape_the_data_folder(service):
    with pytest.raises(ValueError):
        service.get_evidence("../secret")


# --- the qa stage ---

def test_qa_scan_stores_flaky_tests_and_the_tool_detail(tmp_path):
    def qa(target):
        f = finding("F-q", tool="playwright", location="qa_checks/x.py::c")
        f = f.model_copy(update={"detail": "expected X, got Y"})
        return ScanResult([f], {"playwright": "1"}, {"playwright"}, flaky=["wobbly", "also_wobbly"])

    svc = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY, {StageName.QA: qa}, tmp_path)
    svc.run_scan("r1", "qa")
    stage = svc.store.get("r1").stage(StageName.QA)
    assert stage.flaky_tests == ["also_wobbly", "wobbly"]
    assert stage.findings[0].detail == "expected X, got Y"
    assert svc.evaluate_policy("r1", "qa")["result"] == "fail"
