"""The raw JSON of Semgrep and Trivy, tested on trimmed copies of real runs."""
import json
from pathlib import Path

import pytest

from app.adapters import (
    from_semgrep_output,
    from_semgrep_result,
    from_tool_output,
    from_trivy_output,
    from_trivy_secret,
)
from app.grouping import group_findings
from app.models import Scan

FIXTURES = Path(__file__).parent / "fixtures"
SEMGREP = json.loads((FIXTURES / "semgrep_raw_sample.json").read_text(encoding="utf-8"))
TRIVY = json.loads((FIXTURES / "trivy_raw_sample.json").read_text(encoding="utf-8"))


# ---- Semgrep ----
def test_semgrep_sample_is_read_completely():
    findings = from_semgrep_output(SEMGREP)
    assert len(findings) == 9
    assert {f.severity for f in findings} == {"high"}  # ERROR and WARNING both count as high
    assert not any("semgrep-rules" in f.rule_id for f in findings)  # the local config prefix is dropped
    assert findings[4].rule_id == "python.flask.security.audit.debug-enabled"
    assert findings[4].line == 170 and findings[4].file == "demo_app/app.py"


def test_the_requires_login_placeholder_never_becomes_data():
    findings = from_semgrep_output(SEMGREP)
    for f in findings:
        assert f.snippet == ""  # not the placeholder
        assert f.external_id is None  # Semgrep's own fingerprint is never used
        assert "requires login" not in f.model_dump_json().lower()


def test_fingerprints_stay_different_for_the_same_rule_in_different_files():
    findings = from_semgrep_output(SEMGREP)
    assert len({f.fingerprint for f in findings}) == 9  # four csrf findings, four different files


def test_cwe_and_confidence_come_through_whatever_their_shape():
    by_rule = {}
    for f in from_semgrep_output(SEMGREP):
        by_rule.setdefault(f.rule_id, f)
    assert by_rule["python.django.security.django-no-csrf-token"].cwe.startswith("CWE-352")  # a plain string
    assert by_rule["python.sqlalchemy.security.sqlalchemy-execute-raw-query"].cwe.startswith("CWE-89")  # a list
    assert by_rule["python.django.security.injection.tainted-sql-string"].confidence == "low"
    assert by_rule["python.flask.security.audit.debug-enabled"].confidence == "high"
    assert "SQL injection" in by_rule["python.django.security.injection.tainted-sql-string"].description


def test_only_info_is_low_in_semgrep():
    base = {"check_id": "x.semgrep-rules.python.a.b.c", "path": "a.py", "start": {"line": 3}, "extra": {"message": "m"}}
    levels = {}
    for level in ("INFO", "WARNING", "ERROR", "SOMETHING_NEW", ""):
        item = {**base, "extra": {**base["extra"], "severity": level}}
        levels[level] = from_semgrep_result(item).severity
    assert levels == {"INFO": "low", "WARNING": "high", "ERROR": "high", "SOMETHING_NEW": "high", "": "high"}


def test_a_semgrep_scan_with_errors_is_refused():
    doc = {**SEMGREP, "errors": [{"level": "error", "message": "could not parse app.py"}]}
    with pytest.raises(ValueError, match="incomplete"):
        from_semgrep_output(doc)
    warning_only = {**SEMGREP, "errors": [{"level": "warn", "message": "slow rule"}]}
    assert len(from_semgrep_output(warning_only)) == 9


# ---- Trivy ----
def test_trivy_sample_is_read_completely():
    findings = from_trivy_output(TRIVY)
    assert len(findings) == 16  # 15 library vulnerabilities and 1 secret
    libs = [f for f in findings if f.file == "requirements.txt"]
    assert len(libs) == 15
    assert all(f.line is None for f in libs)  # a library has no line
    flask = next(f for f in libs if f.rule_id == "CVE-2018-1000656")
    assert flask.title == "CVE-2018-1000656 in flask==0.12.2"
    assert flask.cwe == "CWE-20"
    assert "Fixed in: 0.12.3." in flask.description and "flask==0.12.2" in flask.description
    assert "\n" not in flask.description and len(flask.description) <= 4000


def test_in_trivy_only_low_is_low():
    findings = {f.rule_id: f for f in from_trivy_output(TRIVY)}
    assert findings["CVE-2026-27205"].severity == "low"  # the only LOW in the run
    assert findings["CVE-2020-28493"].severity == "high"  # MEDIUM counts as high
    assert findings["CVE-2018-1000656"].severity == "high"
    assert findings["github-pat"].severity == "high"  # CRITICAL
    assert sum(f.severity == "low" for f in findings.values()) == 1


def test_trivy_vulnerabilities_keep_trivys_own_stable_fingerprint():
    libs = [f for f in from_trivy_output(TRIVY) if f.file == "requirements.txt"]
    assert all(f.fingerprint.startswith("sha256:") for f in libs)
    assert len({f.fingerprint for f in libs}) == 15


def test_a_fix_being_available_is_not_a_proof_of_closure():
    # Trivy marks every one of these "fixed" (a newer version exists). They must all stay open.
    statuses = {v["Status"] for r in TRIVY["Results"] for v in r.get("Vulnerabilities", [])}
    assert statuses == {"fixed"}
    assert len(from_trivy_output(TRIVY)) == 16


def test_the_secret_is_read_from_its_own_line_only():
    secret = next(f for f in from_trivy_output(TRIVY) if f.rule_id == "github-pat")
    assert (secret.file, secret.line) == ("config.py", 9)
    assert "*" in secret.snippet and secret.snippet.startswith("SHIPPING_API_TOKEN")
    # the neighbouring lines of the real report contain other secret-looking values: never copied
    raw = {
        "RuleID": "x", "Title": "T", "Category": "C", "Severity": "HIGH", "StartLine": 9,
        "Match": 'TOKEN = "*****"',
        "Code": {"Lines": [{"Number": 8, "Content": 'SECRET_KEY = "hunter2"', "IsCause": False}]},
    }
    assert "hunter2" not in from_trivy_secret("config.py", raw).model_dump_json()


def test_an_unmasked_secret_is_not_kept():
    raw = {"RuleID": "x", "Title": "T", "Category": "C", "Severity": "HIGH", "StartLine": 9,
           "Match": 'TOKEN = "ghp_realvaluewithoutmask"'}
    assert from_trivy_secret("config.py", raw).snippet == ""


def test_trivy_misconfigurations_are_refused_instead_of_ignored():
    doc = {**TRIVY, "Results": [{"Target": "Dockerfile", "Class": "config", "Misconfigurations": [{"ID": "DS002"}]}]}
    with pytest.raises(ValueError, match="misconfigurations"):
        from_trivy_output(doc)


# ---- both ----
def test_the_tool_is_detected_from_the_json():
    assert len(from_tool_output(SEMGREP)) == 9
    assert len(from_tool_output(TRIVY)) == 16
    with pytest.raises(ValueError):
        from_tool_output({"something": "else"})


def test_the_real_findings_are_accepted_as_one_scan_and_grouped():
    findings = from_tool_output(SEMGREP) + from_tool_output(TRIVY)
    scan = Scan(repo="owner/demo", pr=1, commit="abcdef1", phase="security", findings=findings)
    assert len(scan.findings) == 25
    assert len({f.fingerprint for f in findings}) == 25  # nothing collides across the two tools
    groups = group_findings(findings)
    assert 1 <= len(groups) <= 25
