import json
import shutil
from pathlib import Path

import pytest

from src.schema import Severity
from src.tools.base import ToolError
from src.tools.security.trivy import TrivyTool, parse_output

FIXTURES = Path(__file__).parent / "fixtures"
FAKE_TOKEN = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789"


def vuln(id="CVE-2018-1000656", pkg="flask", version="0.12.2", severity="HIGH"):
    return {"VulnerabilityID": id, "PkgName": pkg, "InstalledVersion": version, "Severity": severity}


def secret(rule="github-pat", line=2, severity="CRITICAL", match='GITHUB_TOKEN = "****"'):
    return {"RuleID": rule, "StartLine": line, "Severity": severity, "Match": match}


def output(vulns=(), secrets=(), target="requirements.txt"):
    return {"Results": [{"Target": target, "Vulnerabilities": list(vulns), "Secrets": list(secrets)}]}


# --- parsing (no Trivy needed) ---

def test_vulnerability_fields():
    [f] = parse_output(output([vuln()]))
    assert (f.tool, f.rule, f.location, f.severity) == ("trivy", "CVE-2018-1000656", "requirements.txt", Severity.HIGH)


def test_secret_fields():
    [f] = parse_output(output(secrets=[secret()], target="config.py"))
    assert (f.rule, f.location, f.severity) == ("github-pat", "config.py:2", Severity.HIGH)


@pytest.mark.parametrize(
    "raw,ours",
    [("CRITICAL", Severity.HIGH), ("HIGH", Severity.HIGH), ("MEDIUM", Severity.LOW), ("LOW", Severity.LOW),
     ("UNKNOWN", Severity.HIGH), ("SOMETHING_NEW", Severity.HIGH)],
)
def test_severity_mapping(raw, ours):
    [f] = parse_output(output([vuln(severity=raw)]))
    assert f.severity == ours


def test_empty_results():
    assert parse_output({}) == []
    assert parse_output({"Results": None}) == []


def test_same_cve_in_two_packages_is_two_findings():
    fs = parse_output(output([vuln(pkg="flask"), vuln(pkg="other")]))
    assert len({f.id for f in fs}) == 2


def test_duplicates_collapse():
    assert len(parse_output(output([vuln(), vuln()]))) == 1


def test_id_is_stable_and_changes_with_the_package_version():
    a = parse_output(output([vuln(version="0.12.2")]))[0].id
    assert a == parse_output(output([vuln(version="0.12.2")]))[0].id
    assert a != parse_output(output([vuln(version="0.12.1")]))[0].id


def test_secret_id_survives_a_line_shift():
    a = parse_output(output(secrets=[secret(line=2)]))[0].id
    b = parse_output(output(secrets=[secret(line=9)]))[0].id
    assert a == b


def test_order_does_not_depend_on_trivy_output_order():
    vs = [vuln("CVE-1", "a"), vuln("CVE-2", "b"), vuln("CVE-3", "c")]
    assert parse_output(output(vs)) == parse_output(output(list(reversed(vs))))


# --- running the tool ---

def test_missing_target_is_an_error(tmp_path):
    with pytest.raises(ToolError):
        TrivyTool().run(tmp_path / "nope")


def test_missing_trivy_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(ToolError, match="not installed"):
        TrivyTool().run(tmp_path)


def test_missing_db_is_an_error(monkeypatch, tmp_path):
    tool = TrivyTool()
    monkeypatch.setattr(tool, "_run", lambda args: type("P", (), {"stdout": json.dumps({"Version": "0"}), "stderr": "", "returncode": 0})())
    with pytest.raises(ToolError, match="DB not found"):
        tool.run(tmp_path)


# --- real scan (skipped when Trivy or its DB is not there) ---

def _ready() -> bool:
    if shutil.which("trivy") is None:
        return False
    try:
        TrivyTool().versions()
    except ToolError:
        return False
    return True


needs_trivy = pytest.mark.skipif(not _ready(), reason="trivy or its DB is not available")


@pytest.fixture(scope="module")
def vulnerable_findings():
    return TrivyTool().run(FIXTURES / "trivy_vulnerable")


@needs_trivy
def test_real_scan_finds_the_old_dependency(vulnerable_findings):
    hits = [f for f in vulnerable_findings if f.rule == "CVE-2018-1000656"]
    assert len(hits) == 1
    assert hits[0].location == "requirements.txt"
    assert hits[0].severity == Severity.HIGH


@needs_trivy
def test_real_scan_finds_the_planted_secret(vulnerable_findings):
    secrets = [f for f in vulnerable_findings if f.location.startswith("config.py")]
    assert {f.rule for f in secrets} >= {"github-pat", "aws-access-key-id"}
    assert all(f.severity == Severity.HIGH for f in secrets)


@needs_trivy
def test_real_scan_never_keeps_the_secret_value(vulnerable_findings):
    assert FAKE_TOKEN not in json.dumps([f.model_dump(mode="json") for f in vulnerable_findings])


@needs_trivy
def test_real_scan_is_repeatable():
    a = TrivyTool().run(FIXTURES / "trivy_vulnerable")
    b = TrivyTool().run(FIXTURES / "trivy_vulnerable")
    assert a == b


@needs_trivy
def test_clean_project_has_no_findings():
    assert TrivyTool().run(FIXTURES / "trivy_clean") == []


@needs_trivy
def test_versions_are_recorded():
    v = TrivyTool().versions()
    assert set(v) == {"trivy", "trivy-db"} and all(v.values())
