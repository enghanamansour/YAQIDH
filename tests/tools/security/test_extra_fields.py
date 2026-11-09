"""The extra detail the tools give (fixed version, CWE, confidence) is kept, and never changes the fingerprint."""

from src.tools.security.semgrep import parse_output as parse_semgrep
from src.tools.security.trivy import parse_output as parse_trivy


def trivy_data(**vuln):
    base = {"VulnerabilityID": "CVE-1", "PkgName": "flask", "InstalledVersion": "0.12.2", "Severity": "HIGH"}
    return {"Results": [{"Target": "requirements.txt", "Vulnerabilities": [{**base, **vuln}]}]}


def semgrep_data(path, **extra):
    return {
        "errors": [],
        "results": [{
            "check_id": "python.flask.security.injection.sql",
            "path": str(path), "start": {"line": 1}, "end": {"line": 1},
            "extra": {"severity": "ERROR", "message": "SQL is built from user input", **extra},
        }],
    }


def test_trivy_keeps_fixed_version_cwe_and_title():
    f = parse_trivy(trivy_data(FixedVersion="0.12.3", CweIDs=["CWE-400"], Title="Denial of Service"))[0]
    assert (f.fixed_version, f.cwe, f.detail) == ("0.12.3", "CWE-400", "Denial of Service")


def test_trivy_without_a_fix_or_cwe_leaves_the_fields_empty():
    f = parse_trivy(trivy_data())[0]
    assert (f.fixed_version, f.cwe) == ("", "")


def test_trivy_extra_fields_do_not_change_the_fingerprint():
    plain = parse_trivy(trivy_data())[0]
    rich = parse_trivy(trivy_data(FixedVersion="0.12.3", CweIDs=["CWE-400"], Title="x"))[0]
    assert plain.fingerprint == rich.fingerprint


def test_semgrep_keeps_cwe_ids_confidence_and_message(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("query = 'x' + name\n")
    meta = {"cwe": ["CWE-89: Improper Neutralization of Special Elements", "CWE-564: Hibernate"], "confidence": "HIGH"}
    f = parse_semgrep(semgrep_data(src, metadata=meta), tmp_path)[0]
    assert (f.cwe, f.confidence) == ("CWE-89, CWE-564", "high")
    assert f.detail == "SQL is built from user input"


def test_semgrep_accepts_a_single_cwe_string_and_missing_metadata(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("x = 1\n")
    one = parse_semgrep(semgrep_data(src, metadata={"cwe": "CWE-78: OS Command Injection"}), tmp_path)[0]
    none = parse_semgrep(semgrep_data(src), tmp_path)[0]
    assert one.cwe == "CWE-78" and (none.cwe, none.confidence) == ("", "")
    assert one.fingerprint == none.fingerprint


# --- several rules on one line become one finding ---

def two_rules(path, sev2="ERROR"):
    def result(rule, sev, cwe):
        return {"check_id": rule, "path": str(path), "start": {"line": 1}, "end": {"line": 1},
                "extra": {"severity": sev, "message": rule, "metadata": {"cwe": [cwe]}}}
    return {"errors": [], "results": [
        result("python.a.sql", "ERROR", "CWE-89: x"),
        result("python.b.sql", sev2, "CWE-564: y"),
        result("python.c.sql", "INFO", "CWE-89: x"),
    ]}


def test_rules_on_the_same_line_become_one_finding_that_names_the_others(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("query = 'x' + name\n")
    found = parse_semgrep(two_rules(src), tmp_path)
    assert len(found) == 1
    assert found[0].rule == "python.a.sql"
    assert "python.b.sql" in found[0].detail and "python.c.sql" in found[0].detail
    assert found[0].cwe == "CWE-564, CWE-89"


def test_merging_keeps_the_most_severe_one(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("x = 1\n")
    data = two_rules(src)
    data["results"][0]["extra"]["severity"] = "INFO"  # the alphabetically first rule is the weakest
    merged = parse_semgrep(data, tmp_path)
    assert merged[0].severity.value == "high" and merged[0].rule == "python.b.sql"
