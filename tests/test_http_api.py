import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.history import HistoryLog
from src.schema import Severity, StageName
from src.service import ReleaseService
from src.storage import EvidenceStore
from tests.test_service import POLICY, FakeScanner, finding

H = {"X-API-Token": "secret"}
C1, C2 = "aaaa1111", "bbbb2222"


@pytest.fixture(autouse=True)
def token(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "secret")


class Stack:
    def __init__(self, tmp_path, security=None):
        self.qa = FakeScanner([], {"playwright": "1"})
        self.qa.versions = {"playwright": "1"}
        self.sec = FakeScanner(security if security is not None else [finding("F-1", Severity.HIGH)])
        self.history = HistoryLog(tmp_path / "h")
        self.service = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY,
                                      {StageName.QA: self.qa, StageName.SECURITY: self.sec}, tmp_path, self.history)
        self.runs = []

    async def agent(self, release_id, event):
        """Stands in for the real agent: does what the model would do, through the same service."""
        self.runs.append((release_id, event))
        ev = self.service.store.get(release_id)
        for stage in ("qa", "security"):
            record = ev.stage(StageName(stage))
            try:
                if not record.tool_versions:
                    self.service.run_scan(release_id, stage)
                elif record.scanned_commit != ev.head_commit:
                    self.service.verify_fix(release_id, stage)
                else:
                    continue
                self.service.evaluate_policy(release_id, stage)
            except Exception:
                pass
        return {"stopped": "done", "steps": 3, "calls": [{"tool": "run_scan"}]}


@pytest.fixture
def stack(tmp_path):
    return Stack(tmp_path)


@pytest.fixture
def client(stack):
    return TestClient(create_app(stack.service, stack.history, stack.agent))


def open_pr(client, commit=C1, release="r1"):
    return client.post(f"/releases/{release}/events", headers=H, json={"event": "pull_request_opened", "commit": commit})


# --- the door is locked ---

def test_health_is_open_but_everything_else_needs_the_token(client):
    assert client.get("/health").status_code == 200
    assert client.get("/releases").status_code == 401
    assert client.get("/releases", headers={"X-API-Token": "wrong"}).status_code == 401
    assert client.get("/releases", headers=H).status_code == 200


def test_with_no_token_configured_nothing_is_allowed(client, monkeypatch):
    monkeypatch.delenv("API_TOKEN")
    assert client.get("/releases", headers=H).status_code == 503


# --- GitHub events start the agent ---

def test_an_event_records_the_commit_starts_the_agent_and_logs_it(client, stack):
    r = open_pr(client)
    assert r.status_code == 202 and r.json()["head_commit"] == C1
    assert stack.runs == [("r1", "pull_request_opened")]
    events = [e["event"] for e in stack.history.entries("r1")]
    assert events[:2] == ["commit_received", "event"] and "agent_run" in events
    assert client.get("/releases/r1/status", headers=H).json()["status"] == "awaiting_qa_approval"


def test_a_crashing_agent_does_not_take_the_api_down(tmp_path):
    async def boom(release_id, event):
        raise RuntimeError("model down")

    s = Stack(tmp_path)
    client = TestClient(create_app(s.service, s.history, boom))
    assert open_pr(client).status_code == 202
    run = [e for e in s.history.entries("r1") if e["event"] == "agent_run"][0]
    assert run["data"]["stopped"] == "error" and "model down" in run["data"]["error"]
    assert client.get("/health").status_code == 200


def test_bad_events_are_refused(client):
    assert client.post("/releases/r1/events", headers=H, json={"event": "push", "commit": "x"}).status_code == 422
    assert client.post("/releases/r1/events", headers=H, json={"event": "deploy", "commit": C1}).status_code == 422
    assert client.post("/releases/..%2Fx/events", headers=H, json={"event": "push", "commit": C1}).status_code in (404, 422)


# --- people decide ---

def test_the_whole_path_from_pr_to_ready_to_merge(client, stack):
    open_pr(client)
    stack.sec.findings = []  # the developer's code is clean
    # QA passes, a QA reviewer approves, and the security scan starts by itself
    r = client.post("/releases/r1/stages/qa/approve", headers=H, json={"by": "Sara", "reason": "looks fine"})
    assert r.status_code == 200 and r.json()["can_merge_to_staging"]
    assert client.get("/gate", headers=H, params={"release_id": "r1", "commit": C1, "target": "staging"}).json()["allowed"]
    assert not client.get("/gate", headers=H, params={"release_id": "r1", "commit": C1, "target": "main"}).json()["allowed"]
    r = client.post("/releases/r1/stages/security/approve", headers=H, json={"by": "Omar", "reason": ""})
    assert r.json()["status"] == "ready_to_merge"
    g = client.get("/gate", headers=H, params={"release_id": "r1", "commit": C1, "target": "main"}).json()
    assert g["allowed"] and g["reason"] == "clean"
    assert client.get("/releases/r1/history/verify", headers=H).json()["ok"]


def test_approving_when_it_is_not_that_stage_s_turn_is_refused(client):
    open_pr(client)
    r = client.post("/releases/r1/stages/security/approve", headers=H, json={"by": "Omar", "reason": ""})
    assert r.status_code == 409


def test_a_rejection_needs_a_reason_and_a_name(client):
    open_pr(client)
    assert client.post("/releases/r1/stages/qa/reject", headers=H, json={"by": "Sara", "reason": ""}).status_code == 409
    assert client.post("/releases/r1/stages/qa/reject", headers=H, json={"by": "", "reason": "x"}).status_code == 422
    r = client.post("/releases/r1/stages/qa/reject", headers=H, json={"by": "Sara", "reason": "bad"})
    assert r.json()["status"] == "qa_rejected"


def test_a_push_after_approval_closes_the_gate_until_the_new_commit_is_scanned(client, stack):
    open_pr(client)
    stack.sec.findings = []
    client.post("/releases/r1/stages/qa/approve", headers=H, json={"by": "Sara", "reason": ""})
    client.post("/releases/r1/stages/security/approve", headers=H, json={"by": "Omar", "reason": ""})
    gate = lambda c: client.get("/gate", headers=H, params={"release_id": "r1", "commit": c, "target": "main"}).json()
    assert gate(C1)["allowed"]
    client.post("/releases/r1/events", headers=H, json={"event": "push", "commit": C2})
    assert gate(C1)["reason"] == "stale_commit"  # the old commit is no longer the newest
    assert gate(C2)["allowed"] is False  # the agent re-scanned, but nobody approved this security result yet


def test_exceptions_need_justification_and_only_medium_counts(client, stack):
    stack.sec.findings = [finding("F-1", Severity.HIGH).model_copy(update={"reported_as": "medium"})]
    open_pr(client)
    client.post("/releases/r1/stages/qa/approve", headers=H, json={"by": "Sara", "reason": ""})
    bad = client.post("/releases/r1/stages/security/exceptions", headers=H,
                      json={"fingerprint": "F-1", "justification": " ", "approved_by": "Omar"})
    assert bad.status_code == 409
    ok = client.post("/releases/r1/stages/security/exceptions", headers=H,
                     json={"fingerprint": "F-1", "justification": "legacy, fix planned", "approved_by": "Omar"})
    assert ok.status_code == 200 and ok.json()["status"] == "awaiting_security_approval"
    events = [e["event"] for e in stack.history.entries("r1")]
    assert "exception" in events


# --- reading ---

def test_reading_endpoints(client, stack):
    assert client.get("/releases/nope/status", headers=H).status_code == 404
    open_pr(client)
    assert client.get("/releases", headers=H).json()[0]["release_id"] == "r1"
    assert client.get("/releases/r1", headers=H).json()["evidence"]["head_commit"] == C1
    assert client.get("/releases/r1/findings", headers=H, params={"stage": "qa"}).json() == []
    assert client.get("/releases/r1/findings", headers=H, params={"stage": "deploy"}).status_code == 422
    assert [e["seq"] for e in client.get("/releases/r1/history", headers=H).json()] == list(range(1, len(stack.history.entries("r1")) + 1))


def test_the_gate_for_an_unknown_release_is_closed(client):
    g = client.get("/gate", headers=H, params={"release_id": "ghost", "commit": C1, "target": "main"})
    assert g.status_code == 200 and g.json()["allowed"] is False and g.json()["reason"] == "no_release"


# --- a reviewer's answer to a developer's request (exception or more time), recorded by a person ---

def review_body(commit=C1, **over):
    return {"request_id": "t1", "commit": commit, "finding": "F-1", "kind": "deadline", "status": "approved", "by": "Omar",
            "reason": "needs more time", "original": "2026-11-10", "requested": "2026-11-12", "approved_deadline": "2026-11-12", **over}


def test_a_review_request_answer_is_recorded_with_the_name_and_logged(client, stack):
    open_pr(client)
    r = client.post("/releases/r1/review-requests", headers=H, json=review_body())
    assert r.status_code == 200 and r.json()["status"] == "approved"
    saved = stack.service.store.get("r1").review_request_decisions
    assert [(d.by, d.kind, d.status) for d in saved] == [("Omar", "deadline", "approved")]
    assert "review_request" in [e["event"] for e in stack.history.entries("r1")]


def test_an_answer_for_an_old_commit_or_without_a_name_is_refused(client, stack):
    open_pr(client)
    assert client.post("/releases/r1/review-requests", headers=H, json=review_body(commit="old11111")).status_code == 409
    assert client.post("/releases/r1/review-requests", headers=H, json=review_body(by=" ")).status_code == 409
    assert client.post("/releases/r1/review-requests", headers=H, json=review_body(kind="merge")).status_code == 422
    assert client.post("/releases/nope/review-requests", headers=H, json=review_body()).status_code == 404
    assert client.post("/releases/r1/review-requests", json=review_body()).status_code == 401
    assert stack.service.store.get("r1").review_request_decisions == []
