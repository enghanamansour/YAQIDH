import pytest
from fastapi.testclient import TestClient

TOKEN = {"X-API-Token": "dev-token"}
F = {"rule_id": "R1", "title": "Problem", "severity": "high", "file": "a.py", "line": 3, "description": "d"}


def body(findings, commit="abc1234", phase="security", lang="en"):
    return {"repo": "o/r", "pr": 1, "commit": commit, "phase": phase, "findings": findings, "lang": lang}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "dev-token")
    monkeypatch.setenv("EVIDENCE_PATH", str(tmp_path / "e.jsonl"))
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    from app import main
    for fn in (main.get_evidence, main.get_gate, main.get_agent):
        fn.cache_clear()
    return TestClient(main.app)


def test_requests_without_a_token_are_rejected(client):
    assert client.post("/scans", json=body([])).status_code == 401
    assert client.get("/gate", params={"repo": "o/r", "pr": 1, "phase": "qa", "commit": "abc1234"}).status_code == 401


def test_without_configured_token_everything_is_refused(client, monkeypatch):
    monkeypatch.delenv("API_TOKEN")
    assert client.post("/scans", json=body([]), headers=TOKEN).status_code == 503


def test_full_flow_blocked_then_allowed(client):
    r = client.post("/scans", json=body([F]), headers=TOKEN).json()
    assert r["allowed"] is False and len(r["open"]) == 1
    assert "blocked" in r["comment"] and r["open"][0]["fingerprint"] in r["comment"]

    gate = client.get("/gate", params={"repo": "o/r", "pr": 1, "phase": "security", "commit": "abc1234"}, headers=TOKEN)
    assert gate.json()["allowed"] is False

    r2 = client.post("/scans", json=body([], commit="def5678"), headers=TOKEN).json()
    assert r2["allowed"] is True and r2["closed"] == [r["open"][0]["fingerprint"]]

    gate = client.get("/gate", params={"repo": "o/r", "pr": 1, "phase": "security", "commit": "def5678"}, headers=TOKEN)
    assert gate.json() == {"allowed": True, "reason": "clean", "open_count": 0}


def test_evidence_is_recorded_and_intact(client):
    client.post("/scans", json=body([F]), headers=TOKEN)
    entries = client.get("/evidence", params={"repo": "o/r", "pr": 1}, headers=TOKEN).json()["entries"]
    assert any(e["event"] == "scan_recorded" for e in entries)
    assert client.get("/evidence/verify", headers=TOKEN).json()["valid"] is True


def test_bad_input_is_rejected(client):
    bad = body([F]); bad["repo"] = "not a repo"
    assert client.post("/scans", json=bad, headers=TOKEN).status_code == 422
