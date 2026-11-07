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


def test_only_open_findings_are_taken():
    items = [dict(SAMPLE[0], status="fixed"), dict(SAMPLE[1], status="excepted"), SAMPLE[2]]
    assert [f.fingerprint for f in from_team_findings(items)] == ["F-fd9402f7e1"]


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
