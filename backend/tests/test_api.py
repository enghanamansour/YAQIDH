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
    assert "blocked" in r["comment"] and r["open"][0]["fingerprints"][0] in r["comment"]

    gate = client.get("/gate", params={"repo": "o/r", "pr": 1, "phase": "security", "commit": "abc1234"}, headers=TOKEN)
    assert gate.json()["allowed"] is False

    r2 = client.post("/scans", json=body([], commit="def5678"), headers=TOKEN).json()
    assert r2["allowed"] is True and r2["closed"] == [r["open"][0]["fingerprints"][0]]

    gate = client.get("/gate", params={"repo": "o/r", "pr": 1, "phase": "security", "commit": "def5678"}, headers=TOKEN)
    assert gate.json() == {"allowed": True, "reason": "clean", "open_count": 0, "low_open": 0}


def test_low_only_scan_passes_and_the_comment_still_shows_it(client):
    low = dict(F, severity="low", title="Minor thing")
    r = client.post("/scans", json=body([low]), headers=TOKEN).json()
    assert r["allowed"] is True and r["blocking_count"] == 0 and r["low_count"] == 1
    assert r["open"][0]["blocking"] is False and "Minor thing" in r["comment"]


def test_critical_is_accepted_and_counted_as_high(client):
    r = client.post("/scans", json=body([dict(F, severity="critical")]), headers=TOKEN).json()
    assert r["allowed"] is False and r["open"][0]["severity"] == "high" and r["blocking_count"] == 1


def test_unknown_or_medium_severity_counts_as_high(client):
    for name in ("urgent", "medium", "info"):
        r = client.post("/scans", json=body([dict(F, severity=name)]), headers=TOKEN).json()
        assert r["allowed"] is False and r["open"][0]["severity"] == "high", name


def test_evidence_is_recorded_and_intact(client):
    client.post("/scans", json=body([F]), headers=TOKEN)
    entries = client.get("/evidence", params={"repo": "o/r", "pr": 1}, headers=TOKEN).json()["entries"]
    assert any(e["event"] == "scan_recorded" for e in entries)
    assert client.get("/evidence/verify", headers=TOKEN).json()["valid"] is True


def test_bad_input_is_rejected(client):
    bad = body([F]); bad["repo"] = "not a repo"
    assert client.post("/scans", json=bad, headers=TOKEN).status_code == 422


# ---- grouping and publishing through the API ----
import json
from pathlib import Path

from app.adapters import from_team_findings

SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "team_findings_sample.json").read_text(encoding="utf-8"))


def team_body(items, commit="abc1234", **extra):
    findings = [f.model_dump() for f in from_team_findings(items)]
    payload = body(findings, commit=commit)
    payload.update(extra)
    return payload


def test_three_rules_on_one_line_become_one_problem_in_the_comment(client):
    r = client.post("/scans", json=team_body(SAMPLE), headers=TOKEN).json()
    assert len(r["open"]) == 2  # the SQL problem (3 rules) and the low debug one
    sql = next(o for o in r["open"] if o["severity"] == "high")
    assert len(sql["fingerprints"]) == 3 and len(sql["rules"]) == 3
    assert r["comment"].count("#### [HIGH]") == 1 and "3 rules" in r["comment"]
    # the gate still counts each fingerprint on its own
    assert r["blocking_count"] == 3 and r["allowed"] is False


def test_a_low_confidence_finding_gets_the_verify_note(client):
    item = dict(SAMPLE[2], confidence="low")
    r = client.post("/scans", json=team_body([item]), headers=TOKEN).json()
    assert "not sure" in r["comment"] and r["open"][0]["low_confidence"] is True


def test_publish_without_a_github_token_is_reported_not_hidden(client):
    r = client.post("/scans", json=team_body(SAMPLE, publish=True), headers=TOKEN).json()
    assert r["github"] == {"error": "GITHUB_TOKEN is not configured"} and r["allowed"] is False


def test_a_github_failure_never_changes_the_decision(client):
    import httpx
    from app import main
    from app.github import GitHubClient

    broken = GitHubClient("tok", client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    main.app.dependency_overrides[main.get_github] = lambda: broken
    try:
        r = client.post("/scans", json=team_body(SAMPLE, publish=True, commit="a" * 40), headers=TOKEN).json()
    finally:
        main.app.dependency_overrides.clear()
    assert r["allowed"] is False and r["reason"] == "open_findings"  # decision untouched
    assert "comment_error" in r["github"] and "status_error" in r["github"]  # and the failure is visible
    entries = client.get("/evidence", params={"repo": "o/r", "pr": 1}, headers=TOKEN).json()["entries"]
    assert any(e["event"] == "published" for e in entries)


def test_publish_posts_the_comment_and_a_failure_status_while_blocked(client):
    import httpx
    from app import main
    from app.github import GitHubClient

    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json=[])
        return httpx.Response(201, json={"id": 9})

    main.app.dependency_overrides[main.get_github] = lambda: GitHubClient("t", client=httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        r = client.post("/scans", json=team_body(SAMPLE, publish=True, commit="b" * 40), headers=TOKEN).json()
    finally:
        main.app.dependency_overrides.clear()
    assert r["github"]["comment"]["action"] == "created" and r["github"]["status"]["state"] == "failure"
    assert ("POST", f"/repos/o/r/statuses/{'b' * 40}") in seen
