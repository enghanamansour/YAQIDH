import pytest
from pydantic import ValidationError

from src.schema import (
    Decision,
    Evidence,
    Explanation,
    Finding,
    FindingStatus,
    Severity,
    StageName,
)


def make_finding(**kw):
    base = dict(fingerprint="F-001", tool="semgrep", severity=Severity.HIGH, location="app/db.py:42")
    return Finding(**{**base, **kw})


def test_finding_defaults_to_open_without_explanation():
    f = make_finding()
    assert f.status == FindingStatus.OPEN
    assert f.explanation is None and f.closure is None


def test_explanation_source_is_always_yaqidh():
    assert Explanation(text="x").source == "Yaqidh"
    with pytest.raises(ValidationError):
        Explanation(text="x", source="code")


def test_decision_is_only_by_policy_engine():
    with pytest.raises(ValidationError):
        Decision(result="pass", decided_by="ai")


def test_invalid_severity_rejected():
    with pytest.raises(ValidationError):
        make_finding(severity="catastrophic")


def test_stage_is_created_once():
    ev = Evidence(release_id="rel-001")
    a = ev.stage(StageName.QA)
    b = ev.stage(StageName.QA)
    assert a is b and len(ev.stages) == 1


def test_json_roundtrip_matches_brief_shape():
    ev = Evidence(release_id="rel-001")
    ev.stage(StageName.QA).findings.append(make_finding())
    ev.stage(StageName.QA).decision = Decision(result="fail", reasons=["1 high open"])
    data = ev.model_dump(mode="json")
    assert data["stages"][0]["name"] == "qa"
    assert data["stages"][0]["decision"]["decided_by"] == "policy_engine"
    assert Evidence.model_validate(data) == ev


def test_stage_records_tool_versions():
    from src.schema import Evidence, StageName

    ev = Evidence(release_id="r1")
    ev.stage(StageName.SECURITY).tool_versions = {"trivy": "0.76.2", "trivy-db": "2026-11-07T12:52:01Z"}
    again = Evidence.model_validate_json(ev.model_dump_json())
    assert again.stage(StageName.SECURITY).tool_versions["trivy"] == "0.76.2"
