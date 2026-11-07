import shutil
import sys
from pathlib import Path

import pytest

from src.schema import Severity
from src.tools.base import ToolError
from src.tools.security.semgrep import SemgrepTool, _rule_id, parse_output

FIXTURES = Path(__file__).parent / "fixtures"
RULES_DIR = Path(__file__).resolve().parents[3] / "config" / "semgrep-rules"
SQLI = "python.flask.security.injection.tainted-sql-string"
DEBUG = "python.flask.security.audit.debug-enabled"


def fake_result(tmp_path, check_id=SQLI, severity="ERROR", line=3):
    f = tmp_path / "app.py"
    f.write_text("a = 1\nb = 2\nquery = 'x' + name\n")
    return {
        "check_id": check_id,
        "path": str(f),
        "start": {"line": line},
        "end": {"line": line},
        "extra": {"severity": severity, "lines": "requires login"},
    }


def test_parse_maps_fields(tmp_path):
    [f] = parse_output({"results": [fake_result(tmp_path)], "errors": []}, tmp_path)
    assert f.tool == "semgrep"
    assert f.rule == SQLI
    assert f.location == "app.py:3"
    assert f.severity == Severity.HIGH


@pytest.mark.parametrize(
    "check_id",
    [SQLI, f"config.semgrep-rules.{SQLI}", f"Users.someone.project.config.semgrep-rules.{SQLI}"],
)
def test_rule_id_does_not_depend_on_where_the_rules_are_stored(check_id):
    assert _rule_id(check_id) == SQLI


@pytest.mark.parametrize("semgrep,ours", [("ERROR", Severity.HIGH), ("WARNING", Severity.LOW), ("INFO", Severity.LOW), ("SOMETHING_NEW", Severity.HIGH)])
def test_severity_mapping(tmp_path, semgrep, ours):
    [f] = parse_output({"results": [fake_result(tmp_path, severity=semgrep)], "errors": []}, tmp_path)
    assert f.severity == ours


def test_id_survives_a_line_shift(tmp_path):
    result = fake_result(tmp_path)
    first = parse_output({"results": [result], "errors": []}, tmp_path)[0]
    (tmp_path / "app.py").write_text("# new comment\na = 1\nb = 2\nquery = 'x' + name\n")
    shifted = {**result, "start": {"line": 4}, "end": {"line": 4}}
    second = parse_output({"results": [shifted], "errors": []}, tmp_path)[0]
    assert first.location != second.location
    assert first.id == second.id


def test_duplicate_results_collapse_to_one_finding(tmp_path):
    r = fake_result(tmp_path)
    assert len(parse_output({"results": [r, r], "errors": []}, tmp_path)) == 1


def test_semgrep_errors_are_raised_not_hidden(tmp_path):
    with pytest.raises(ToolError):
        parse_output({"results": [], "errors": [{"message": "bad rule"}]}, tmp_path)


def test_missing_target_raises(tmp_path):
    with pytest.raises(ToolError):
        SemgrepTool(RULES_DIR).run(tmp_path / "nope")


def test_missing_rules_raise_a_helpful_error(tmp_path):
    with pytest.raises(ToolError, match="fetch_semgrep_rules"):
        SemgrepTool(tmp_path / "no-rules").run(tmp_path)


def test_rules_version_is_unknown_when_rules_are_missing(tmp_path):
    assert SemgrepTool(tmp_path).rules_version() == "unknown"


have_semgrep = shutil.which("semgrep") is not None or (Path(sys.executable).parent / "semgrep").exists()
have_rules = (RULES_DIR / "python").is_dir()
needs_real_scan = pytest.mark.skipif(
    not (have_semgrep and have_rules),
    reason="needs semgrep and the official rules (run scripts/fetch_semgrep_rules.sh)",
)


@pytest.fixture(scope="module")
def tool():
    return SemgrepTool(RULES_DIR)


@pytest.fixture(scope="module")
def vulnerable_findings(tool):
    # One real scan is shared by the tests below: loading the official rules takes about 10 seconds.
    return tool.run(FIXTURES / "vulnerable")


@needs_real_scan
def test_real_scan_finds_planted_vulnerabilities(vulnerable_findings):
    rules = {f.rule for f in vulnerable_findings}
    assert SQLI in rules
    assert DEBUG in rules


@needs_real_scan
def test_real_scan_severities(vulnerable_findings):
    by_rule = {f.rule: f.severity for f in vulnerable_findings}
    assert by_rule[SQLI] == Severity.HIGH
    assert by_rule[DEBUG] == Severity.LOW


@needs_real_scan
def test_real_scan_of_clean_code_finds_nothing(tool):
    assert tool.run(FIXTURES / "clean") == []


@needs_real_scan
def test_real_scan_is_deterministic(tool, vulnerable_findings):
    assert tool.run(FIXTURES / "vulnerable") == vulnerable_findings


@needs_real_scan
def test_rules_version_is_the_pinned_commit(tool):
    assert len(tool.rules_version()) == 40
