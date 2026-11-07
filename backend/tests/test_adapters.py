import json
from pathlib import Path

from app.adapters import from_team_finding, from_team_findings
from app.evidence import EvidenceLog
from app.gate import Gate
from app.models import Scan

SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "team_findings_sample.json").read_text(encoding="utf-8"))


def test_the_sample_converts_and_keeps_the_teams_ids():
    findings = from_team_findings(SAMPLE)
    assert [f.fingerprint for f in findings] == ["F-363d42d8b6", "F-95b1ec17e4", "F-fd9402f7e1", "F-6c518b5a46"]
    first = findings[0]
    assert (first.file, first.line, first.severity) == ("app.py", 12, "high")
    assert first.rule_id == "python.flask.security.injection.tainted-sql-string"
    assert first.title == "tainted sql string (flask)"
    assert findings[3].severity == "low" and findings[3].line == 17


def test_a_location_without_a_line_number_is_kept():
    item = dict(SAMPLE[0], location="requirements.txt")
    f = from_team_finding(item)
    assert f.file == "requirements.txt" and f.line is None


def test_only_a_verified_closure_removes_a_finding():
    closed = dict(SAMPLE[0], status="fixed", closure={"verified_by": "rescan", "result": "closed"})
    fixed_but_unverified = dict(SAMPLE[1], status="fixed")
    still_open = dict(SAMPLE[2], status="fixed", closure={"verified_by": "rescan", "result": "still_open"})
    excepted = dict(SAMPLE[3], status="excepted")
    kept = [f.fingerprint for f in from_team_findings([closed, fixed_but_unverified, still_open, excepted])]
    # fails closed: an exception is the team's policy to judge, never ours
    assert kept == ["F-95b1ec17e4", "F-fd9402f7e1", "F-6c518b5a46"]


# ---- the current shape of the team's findings ('fingerprint', component, reported_as) ----
CURRENT = json.loads((Path(__file__).parent / "fixtures" / "team_findings_current_shape.json").read_text(encoding="utf-8"))


def test_the_current_shape_is_read_and_the_verified_closed_one_is_dropped():
    findings = from_team_findings(CURRENT)
    assert [f.fingerprint for f in findings] == ["F-aaaaaaaaaa", "F-bbbbbbbbbb", "F-cccccccccc"]


def test_a_library_finding_says_which_package_and_what_the_tool_called_it():
    lib = from_team_finding(CURRENT[1])
    assert lib.title == "CVE-2018-1000656 in flask==0.12.2"
    assert "flask==0.12.2" in lib.description and "reported it as: medium" in lib.description
    assert lib.file == "requirements.txt" and lib.line is None and lib.severity == "high"


def test_the_fingerprint_wins_over_the_old_id_and_either_works():
    assert from_team_finding(dict(CURRENT[0], id="OLD")).fingerprint == "F-aaaaaaaaaa"
    legacy = {k: v for k, v in CURRENT[0].items() if k != "fingerprint"}
    assert from_team_finding(dict(legacy, id="F-legacy")).fingerprint == "F-legacy"


def test_a_finding_with_no_fingerprint_is_refused():
    import pytest
    bare = {k: v for k, v in CURRENT[0].items() if k != "fingerprint"}
    with pytest.raises(ValueError):
        from_team_finding(bare)


def test_the_current_shape_goes_through_the_gate(tmp_path):
    gate = Gate(EvidenceLog(tmp_path / "e.jsonl"))
    gate.record_scan(Scan(repo="o/r", pr=1, commit="abc1234", phase="security", findings=from_team_findings(CURRENT)))
    d = gate.check("o/r", 1, "security", "abc1234")
    assert not d.allowed and d.open_count == 2 and d.low_open == 1  # semgrep high + the medium library, one low


def test_the_sample_blocks_then_passes_once_the_high_ones_are_fixed(tmp_path):
    gate = Gate(EvidenceLog(tmp_path / "e.jsonl"))
    scan = lambda items, commit: Scan(repo="o/r", pr=1, commit=commit, phase="security",
                                     findings=from_team_findings(items))
    gate.record_scan(scan(SAMPLE, "abc1234"))
    d = gate.check("o/r", 1, "security", "abc1234")
    assert not d.allowed and d.open_count == 3 and d.low_open == 1

    only_low = [i for i in SAMPLE if i["severity"] == "low"]
    res = gate.record_scan(scan(only_low, "def5678"))
    assert sorted(res.closed) == ["F-363d42d8b6", "F-95b1ec17e4", "F-fd9402f7e1"]
    d = gate.check("o/r", 1, "security", "def5678")
    assert d.allowed and d.low_open == 1
