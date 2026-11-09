"""Three problems found by walking a pull request through the whole loop with the real language model.

1. a model left to choose did not re-scan after a push (6 of 6 tries), so the gate stayed closed;
2. the model call blocked the server's event loop (a trivial request waited up to 20 s);
3. approving QA before the CI results arrived answered 500 although the approval was saved.
"""
import threading

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.history import HistoryLog
from src.scanning import submitted_runner
from src.schema import Severity, StageName
from src.service import ReleaseService
from src.storage import EvidenceStore
from tests.test_loop import ScriptedChat, drive, say, service as loop_service, skills  # noqa: F401  (fixtures)
from tests.test_service import POLICY, FakeScanner, finding

pytestmark = pytest.mark.anyio

H = {"X-API-Token": "secret"}
C1, C2 = "aaaa1111", "bbbb2222"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def token(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "secret")


async def lazy_agent(release_id, event):
    """A model that decides not to scan anything and just stops (what the real one did after a push)."""
    return {"stopped": "done", "steps": 1, "calls": []}


def events(history, release="r1"):
    return [e["event"] for e in history.entries(release)]


# --- 1. a commit is scanned by code, not by the model's choice ---

async def test_a_new_pull_request_is_scanned_even_if_the_agent_does_nothing(tmp_path):
    qa = FakeScanner([finding("Q-1", Severity.HIGH)], {"playwright": "1"})
    history = HistoryLog(tmp_path / "h")
    svc = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY, {StageName.QA: qa, StageName.SECURITY: FakeScanner([])}, tmp_path, history)
    client = TestClient(create_app(svc, history, lazy_agent))

    assert client.post("/releases/r1/events", headers=H, json={"event": "pull_request_opened", "commit": C1}).status_code == 202
    assert qa.calls == 1
    assert client.get("/releases/r1/status", headers=H).json()["status"] == "qa_blocked"
    assert "scan" in events(history) and "policy_decision" in events(history)


async def test_a_push_re_scans_and_closes_what_was_fixed_even_if_the_agent_does_nothing(tmp_path):
    qa = FakeScanner([finding("Q-1", Severity.HIGH)], {"playwright": "1"})
    history = HistoryLog(tmp_path / "h")
    svc = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY, {StageName.QA: qa, StageName.SECURITY: FakeScanner([])}, tmp_path, history)
    client = TestClient(create_app(svc, history, lazy_agent))
    client.post("/releases/r1/events", headers=H, json={"event": "pull_request_opened", "commit": C1})

    qa.findings = []  # the developer fixed it
    client.post("/releases/r1/events", headers=H, json={"event": "push", "commit": C2})

    assert qa.calls == 2
    rescan = [e for e in history.entries("r1") if e["event"] == "rescan"][-1]["data"]
    assert (rescan["stage"], rescan["commit"], rescan["closed"]) == ("qa", C2, ["Q-1"])
    assert client.get("/releases/r1/status", headers=H).json()["status"] == "awaiting_qa_approval"
    # the gate sees QA scanned on exactly the newest commit
    gate = client.get("/gate", headers=H, params={"release_id": "r1", "commit": C2, "target": "staging"}).json()
    assert gate["reason"] != "stale_scan"


async def test_a_scan_that_fails_is_recorded_and_the_gate_stays_closed(tmp_path):
    def broken(_target):
        raise RuntimeError("the browser crashed")

    history = HistoryLog(tmp_path / "h")
    svc = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY, {StageName.QA: broken, StageName.SECURITY: FakeScanner([])}, tmp_path, history)
    client = TestClient(create_app(svc, history, lazy_agent))

    assert client.post("/releases/r1/events", headers=H, json={"event": "pull_request_opened", "commit": C1}).status_code == 202
    assert "scan_not_run" in events(history)
    assert client.get("/gate", headers=H, params={"release_id": "r1", "commit": C1, "target": "staging"}).json()["allowed"] is False


# --- 2. the model call must not run on the server's event loop ---

async def test_the_model_call_runs_in_a_worker_thread(loop_service, skills):  # noqa: F811
    seen = []

    class Chat(ScriptedChat):
        def complete(self, messages, tools):
            seen.append(threading.get_ident())
            return super().complete(messages, tools)

    await drive(loop_service, skills, Chat(say("nothing to do")))
    assert seen and seen[0] != threading.get_ident()


# --- 3. approving QA before the CI results arrive ---

async def test_qa_approval_before_the_ci_results_is_kept_and_does_not_error(tmp_path):
    history = HistoryLog(tmp_path / "h")
    store = EvidenceStore(tmp_path / "d")
    qa = FakeScanner([], {"playwright": "1"})
    svc = ReleaseService(store, POLICY, {StageName.QA: qa, StageName.SECURITY: submitted_runner(store)}, tmp_path, history)
    client = TestClient(create_app(svc, history, lazy_agent), raise_server_exceptions=False)
    client.post("/releases/r1/events", headers=H, json={"event": "pull_request_opened", "commit": C1})

    resp = client.post("/releases/r1/stages/qa/approve", headers=H, json={"by": "Sara", "reason": "ok"})

    assert resp.status_code == 200, resp.text  # it was a 500 before
    assert resp.json()["status"] == "awaiting_security_scan"
    assert "security_waiting" in events(history)

    scan = {"commit": C1, "findings": [], "versions": {"semgrep-rules": "r", "trivy": "1", "trivy-db": "d"},
            "tools_run": ["semgrep", "trivy"]}
    out = client.post("/releases/r1/scan-results", headers=H, json=scan).json()
    assert out["applied"] is True  # security starts by itself when the results arrive
    assert client.get("/releases/r1/status", headers=H).json()["status"] == "awaiting_security_approval"
