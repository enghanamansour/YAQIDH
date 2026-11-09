import json

from src.history import GENESIS, HistoryLog
from src.schema import StageName
from src.service import ReleaseService
from src.storage import EvidenceStore
from tests.test_service import POLICY, FakeScanner, finding, seed_approved_qa


def test_entries_are_chained_and_verify_passes(tmp_path):
    log = HistoryLog(tmp_path)
    a = log.append("r1", "scan", "agent", {"findings": 5})
    b = log.append("r1", "scan", "agent", {"findings": 2})
    assert a["prev_hash"] == GENESIS and b["prev_hash"] == a["hash"] and b["seq"] == 2
    assert log.verify("r1") == {"ok": True, "entries": 2}


def test_a_changed_line_is_detected_at_the_right_place(tmp_path):
    log = HistoryLog(tmp_path)
    for n in (5, 4, 2):
        log.append("r1", "scan", "agent", {"findings": n})
    path = tmp_path / "r1.jsonl"
    lines = path.read_text().splitlines()
    edited = json.loads(lines[1])
    edited["data"]["findings"] = 0  # someone makes the history look better
    lines[1] = json.dumps(edited)
    path.write_text("\n".join(lines) + "\n")
    assert log.verify("r1") == {"ok": False, "broken_at": 2, "reason": "this line was changed"}


def test_a_removed_line_is_detected(tmp_path):
    log = HistoryLog(tmp_path)
    for n in (5, 4, 2):
        log.append("r1", "scan", "agent", {"findings": n})
    path = tmp_path / "r1.jsonl"
    lines = path.read_text().splitlines()
    path.write_text(lines[0] + "\n" + lines[2] + "\n")
    assert log.verify("r1")["ok"] is False and log.verify("r1")["broken_at"] == 2


def test_releases_have_separate_logs_and_bad_ids_are_refused(tmp_path):
    log = HistoryLog(tmp_path)
    log.append("r1", "x", "system")
    assert log.entries("r2") == [] and log.verify("r2") == {"ok": True, "entries": 0}
    import pytest
    with pytest.raises(ValueError):
        log.append("../x", "x", "system")


def test_the_service_writes_the_story_of_a_release(tmp_path):
    scanner = FakeScanner([finding("F-1"), finding("F-2")])
    log = HistoryLog(tmp_path / "h")
    svc = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY, {StageName.SECURITY: scanner}, tmp_path, history=log)
    seed_approved_qa(svc.store)
    svc.set_head_commit("r1", "abc1234")
    svc.run_scan("r1", "security")
    svc.evaluate_policy("r1", "security")
    svc.append_evidence("r1", "security", "F-1", "explained")
    scanner.findings = [finding("F-2")]
    svc.verify_fix("r1", "security")
    svc.add_human_decision("r1", "security", "reject", "Sara", "fix F-2")
    events = [(e["event"], e["actor"]) for e in log.entries("r1")]
    assert events == [("commit_received", "system"), ("scan", "agent"), ("policy_decision", "policy_engine"),
                      ("explanation", "agent"), ("rescan", "agent"), ("human_decision", "Sara")]
    scans = [e for e in log.entries("r1") if e["event"] in ("scan", "rescan")]
    assert scans[0]["data"]["findings"] == 2 and scans[1]["data"]["closed"] == ["F-1"]  # scan 1 found 2, then F-1 closed
    assert all(e["data"].get("commit") == "abc1234" for e in scans)
    assert log.verify("r1")["ok"]
