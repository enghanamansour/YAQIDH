import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.history import HistoryLog
from src.scanning import submitted_runner
from src.schema import Closure, ExceptionRecord, Explanation, FindingStatus, Severity, StageName
from src.service import ReleaseService
from src.storage import EvidenceStore
from tests.test_http_api import H, Stack, finding

C1, C2 = "aaaa1111", "bbbb2222"
VERSIONS = {"semgrep-rules": "r1", "trivy": "1", "trivy-db": "d1"}


@pytest.fixture(autouse=True)
def token(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "secret")


class CiStack(Stack):
    """Like Stack, but security results come from CI instead of a scan on this machine."""

    def __init__(self, tmp_path):
        super().__init__(tmp_path)
        self.service = ReleaseService(EvidenceStore(tmp_path / "d"), self.service.policy_path,
                                      {StageName.QA: self.qa, StageName.SECURITY: submitted_runner(EvidenceStore(tmp_path / "d"))},
                                      tmp_path, self.history)


@pytest.fixture
def stack(tmp_path):
    return CiStack(tmp_path)


@pytest.fixture
def client(stack):
    return TestClient(create_app(stack.service, stack.history, stack.agent))


def body(commit=C1, findings=None, **over):
    fs = [finding("F-1", Severity.HIGH)] if findings is None else findings
    return {"commit": commit, "findings": [f.model_dump(mode="json") for f in fs], "versions": VERSIONS,
            "tools_run": ["semgrep", "trivy"], "components": ["flask==0.12.2"], **over}


def send(client, release="r1", **kw):
    return client.post(f"/releases/{release}/scan-results", headers=H, json=body(**kw))


def open_pr(client, commit=C1):
    client.post("/releases/r1/events", headers=H, json={"event": "pull_request_opened", "commit": commit})


def test_results_arriving_before_security_s_turn_wait_and_are_used_after_the_qa_approval(client, stack):
    open_pr(client)
    r = send(client)
    assert r.status_code == 202 and r.json()["applied"] is False  # QA is not approved yet, so they wait
    assert stack.service.store.get("r1").pending_scan.commit == C1
    assert not stack.service.store.get("r1").stage(StageName.SECURITY).tool_versions
    out = client.post("/releases/r1/stages/qa/approve", headers=H, json={"by": "Sara", "reason": ""})
    assert out.status_code == 200 and out.json()["status"] == "security_blocked"  # the waiting results were used
    assert stack.service.get_findings("r1", "security")[0]["fingerprint"] == "F-1"


def test_results_arriving_when_it_is_security_s_turn_are_used_at_once(client, stack):
    open_pr(client)
    stack.service.add_human_decision("r1", "qa", "approve", "Sara", "")
    r = send(client)
    assert r.json()["applied"] is True
    assert client.get("/releases/r1/status", headers=H).json()["status"] == "security_blocked"


def test_a_new_push_then_new_results_re_scan_and_the_verifier_closes_what_is_gone(client, stack):
    open_pr(client)
    stack.service.add_human_decision("r1", "qa", "approve", "Sara", "")
    send(client)
    client.post("/releases/r1/events", headers=H, json={"event": "push", "commit": C2})
    r = send(client, commit=C2, findings=[])
    assert r.json()["applied"] is True
    f = stack.service.get_findings("r1", "security")[0]
    assert f["status"] == "fixed" and f["closure"]["result"] == "closed"


def test_results_for_an_old_commit_or_an_unknown_release_are_refused(client):
    assert send(client, release="ghost").status_code == 409
    open_pr(client, C2)
    r = send(client, commit=C1)
    assert r.status_code == 409 and "newest commit" in r.json()["detail"]


def test_results_must_come_from_both_tools_with_versions(client):
    open_pr(client)
    assert send(client, tools_run=["semgrep"]).status_code == 409
    assert send(client, versions={"trivy": "1"}).status_code == 409


def test_ci_cannot_smuggle_in_a_closure_an_exception_or_an_explanation(client, stack):
    open_pr(client)
    stack.service.add_human_decision("r1", "qa", "approve", "Sara", "")
    sneaky = finding("F-1", Severity.HIGH).model_copy(update={
        "status": FindingStatus.FIXED, "closure": Closure(result="closed"),
        "exception": ExceptionRecord(justification="x", approved_by="y"), "explanation": Explanation(text="all good")})
    send(client, findings=[sneaky])
    f = stack.service.get_findings("r1", "security")[0]
    assert f["status"] == "open" and f["closure"] is None and f["exception"] is None and f["explanation"] is None
    assert client.get("/releases/r1/status", headers=H).json()["status"] == "security_blocked"


def test_the_endpoint_needs_the_token(client):
    assert client.post("/releases/r1/scan-results", json=body()).status_code == 401


def test_the_scan_tool_says_it_is_waiting_when_no_results_arrived(stack):
    from datetime import timedelta

    from src.schema import Decision, HumanDecision, utcnow

    stack.service.set_head_commit("r1", C1)
    ev = stack.service.store.get("r1")
    qa = ev.stage(StageName.QA)
    qa.tool_versions, qa.scanned_at, qa.scanned_commit = {"p": "1"}, utcnow() - timedelta(seconds=5), C1
    qa.decision = Decision(result="pass")
    ev.human_decisions.append(HumanDecision(stage=StageName.QA, decision="approve", by="S", reason=""))
    stack.service.store.save(ev)
    with pytest.raises(Exception, match="waiting for the CI scan results"):
        stack.service.run_scan("r1", "security")
    assert not stack.service.store.get("r1").stage(StageName.SECURITY).tool_versions
