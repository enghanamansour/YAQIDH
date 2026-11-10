"""The developer's report is plain code over the evidence and the history: no model, no estimates."""
import time

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.history import HistoryLog
from src.report import build_report
from src.schema import Evidence, Severity, StageName
from src.service import ReleaseService
from src.storage import EvidenceStore
from tests.test_service import POLICY, FakeScanner, finding

H = {"X-API-Token": "t"}
TICK = 0.04  # longer than the Windows clock tick, so every step gets its own time


def _run_release(tmp_path):
    """A real service: found 2 things, the developer fixed one, QA passed and was approved."""
    qa = FakeScanner([finding("F-1", Severity.HIGH, location="a.py:1"), finding("F-2", Severity.LOW, location="b.py:2")])
    history = HistoryLog(tmp_path / "h")
    svc = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY, {StageName.QA: qa, StageName.SECURITY: FakeScanner([])},
                         tmp_path, history)
    svc.set_head_commit("r1", "aaaa1111")
    svc.run_scan("r1", "qa"); svc.evaluate_policy("r1", "qa")
    time.sleep(TICK)
    qa.findings = [finding("F-2", Severity.LOW, location="b.py:2")]  # the developer fixed F-1
    svc.set_head_commit("r1", "bbbb2222")
    svc.verify_fix("r1", "qa"); svc.evaluate_policy("r1", "qa")
    time.sleep(TICK)
    svc.add_human_decision("r1", "qa", "approve", "Sara", "looks good")
    return svc, history


def test_the_report_says_what_closed_how_fast_and_what_is_still_open(tmp_path):
    svc, history = _run_release(tmp_path)
    report = build_report(svc.store.get("r1"), history.entries("r1"))

    by_fp = {r["fingerprint"]: r for r in report["findings"]}
    closed, still_open = by_fp["F-1"], by_fp["F-2"]
    assert closed["status"] == "fixed" and closed["closed_at"] and closed["first_seen"]
    assert closed["seconds_to_close"] is not None and closed["seconds_to_close"] >= 0
    assert closed["rounds"] == 2                      # the first scan and the re-scan that proved it closed
    assert still_open["status"] == "open" and still_open["closed_at"] is None
    assert still_open["seconds_open"] is not None and still_open["rounds"] == 2

    s = report["summary"]
    assert (s["findings"], s["closed"], s["open_blocking"], s["open_low"]) == (2, 1, 0, 1)
    assert s["rounds"] == {"qa": 2, "security": 0}
    assert s["time_to_close"]["count"] == 1 and s["time_to_close"]["average_seconds"] == closed["seconds_to_close"]
    assert [w["stage"] for w in s["approval_waits"]] == ["qa"] and s["approval_waits"][0]["seconds"] >= 0


def test_open_findings_come_first_and_blocking_ones_before_low(tmp_path):
    svc, history = _run_release(tmp_path)
    order = [r["fingerprint"] for r in build_report(svc.store.get("r1"), history.entries("r1"))["findings"]]
    assert order == ["F-2", "F-1"]  # the open one, then the closed one


def test_the_report_carries_the_decisions_the_gate_and_a_timeline(tmp_path):
    svc, history = _run_release(tmp_path)
    report = build_report(svc.store.get("r1"), history.entries("r1"))
    assert [(a["stage"], a["decision"], a["by"]) for a in report["approvals"]] == [("qa", "approve", "Sara")]
    assert report["status"]["status"] == "awaiting_security_scan" and report["head_commit"] == "bbbb2222"
    assert set(report["gates"]) == {"staging", "main"} and report["gates"]["main"]["allowed"] is False
    events = [e["event"] for e in report["timeline"]]
    assert events.index("scan") < events.index("rescan") < events.index("human_decision")
    assert report["notes"][:3] == ["elapsed_time", "scan_resolution", "db_origin"] and "low_awareness" in report["notes"]


def test_a_release_with_no_history_still_gives_a_report():
    report = build_report(Evidence(release_id="empty"), [])
    assert report["summary"]["findings"] == 0 and report["findings"] == [] and report["gates"] == {}
    assert report["summary"]["time_to_close"] == {"count": 0, "average_seconds": None, "max_seconds": None}


def test_the_report_is_served_by_the_api(tmp_path, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "t")
    svc, history = _run_release(tmp_path)

    async def agent(release_id, event):
        return {"stopped": "done", "steps": 0, "calls": []}

    client = TestClient(create_app(svc, history, agent))
    ok = client.get("/releases/r1/report", headers=H)
    assert ok.status_code == 200 and ok.json()["summary"]["closed"] == 1
    assert client.get("/releases/nope/report", headers=H).status_code == 404
    assert client.get("/releases/r1/report").status_code == 401  # the door is locked like every other route


def test_the_report_counts_by_the_level_the_tool_gave_and_by_owasp_category():
    from src.report import OWASP_BY_CWE, _count

    assert _count([{"reported_as": "HIGH"}, {"reported_as": "high"}, {"reported_as": ""}], "reported_as") == {"high": 2, "unknown": 1}
    assert OWASP_BY_CWE["CWE-89"].startswith("A03") and OWASP_BY_CWE["CWE-798"].startswith("A07")


def test_a_finding_row_carries_its_explanation_and_the_exception_that_let_it_through(tmp_path):
    from src.schema import ExceptionRecord, Explanation, Finding, Severity, StageName

    svc, history = _run_release(tmp_path)
    ev = svc.store.get("r1")
    ev.stage(StageName.QA).findings.append(Finding(
        fingerprint="F-x", tool="semgrep", severity=Severity.HIGH, reported_as="medium", location="a.py:1",
        explanation=Explanation(text="plain words"), exception=ExceptionRecord(justification="reviewed", approved_by="Sara")))
    row = next(r for r in build_report(ev, history.entries("r1"))["findings"] if r["fingerprint"] == "F-x")
    assert row["explanation"] == "plain words"
    assert row["exception"]["approved_by"] == "Sara" and row["exception"]["justification"] == "reviewed" and row["exception"]["at"]
