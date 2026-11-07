import json

import httpx
import pytest

from app.evidence import EvidenceLog
from app.explainer import LLMExplainer, TemplateExplainer, violates_rules
from app.gate import Gate
from app.models import Explanation, Finding, Scan


def finding(rule="R1", file="a.py", line=10, snippet="x = 1", severity="high", title="Problem"):
    return Finding(rule_id=rule, title=title, severity=severity, file=file, line=line, snippet=snippet,
                   description="d")


def scan(findings, commit="abc1234", phase="security", pr=1):
    return Scan(repo="o/r", pr=pr, commit=commit, phase=phase, findings=findings)


@pytest.fixture
def gate(tmp_path):
    return Gate(EvidenceLog(tmp_path / "e.jsonl"))


# ---- fingerprint ----
def test_fingerprint_ignores_line_number():
    assert finding(line=10).fingerprint == finding(line=99).fingerprint


def test_fingerprint_changes_with_rule_or_file():
    base = finding().fingerprint
    assert finding(rule="R2").fingerprint != base
    assert finding(file="b.py").fingerprint != base


# ---- gate: the rule that matters ----
def test_blocked_when_no_scan_exists(gate):
    d = gate.check("o/r", 1, "security", "abc1234")
    assert not d.allowed and d.reason == "no_scan"


def test_blocked_while_findings_are_open(gate):
    gate.record_scan(scan([finding()]))
    d = gate.check("o/r", 1, "security", "abc1234")
    assert not d.allowed and d.reason == "open_findings" and d.open_count == 1


def test_allowed_only_after_a_rescan_without_the_finding(gate):
    gate.record_scan(scan([finding()]))
    res = gate.record_scan(scan([], commit="def5678"))
    assert res.closed == [finding().fingerprint]
    assert gate.check("o/r", 1, "security", "def5678").allowed


def test_new_commit_is_blocked_until_it_is_scanned(gate):
    gate.record_scan(scan([]))
    assert gate.check("o/r", 1, "security", "abc1234").allowed
    d = gate.check("o/r", 1, "security", "fffffff")
    assert not d.allowed and d.reason == "stale_scan"


def test_fixing_one_of_two_keeps_it_blocked(gate):
    a, b = finding(rule="A"), finding(rule="B")
    gate.record_scan(scan([a, b]))
    gate.record_scan(scan([b], commit="def5678"))
    d = gate.check("o/r", 1, "security", "def5678")
    assert not d.allowed and d.open_count == 1


def test_phases_and_pull_requests_are_independent(gate):
    gate.record_scan(scan([], phase="qa"))
    assert gate.check("o/r", 1, "qa", "abc1234").allowed
    assert not gate.check("o/r", 1, "security", "abc1234").allowed
    assert not gate.check("o/r", 2, "qa", "abc1234").allowed


# ---- evidence log ----
def test_evidence_chain_detects_tampering(tmp_path):
    log = EvidenceLog(tmp_path / "e.jsonl")
    for i in range(3):
        log.append(repo="o/r", pr=1, commit="abc1234", phase="qa", event="x", data={"i": i})
    assert log.verify()["valid"]
    lines = (tmp_path / "e.jsonl").read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[1]); entry["data"]["i"] = 99
    lines[1] = json.dumps(entry)
    (tmp_path / "e.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert log.verify() == {"valid": False, "broken_at": 2}


# ---- explainer rules ----
def test_template_explanation_has_no_code():
    exp = TemplateExplainer().explain(finding(), "ar")
    assert not violates_rules(exp)


def test_backticks_count_as_code():
    assert violates_rules(Explanation(problem="use `eval(x)`", why_dangerous="w", direction="d"))


def _llm(responses):
    calls = iter(responses)

    def handler(request):
        content = next(calls)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return LLMExplainer("http://x", "k", "m", client=httpx.Client(transport=httpx.MockTransport(handler)))


GOOD = json.dumps({"problem": "p", "why_dangerous": "w", "direction": "d"})
CODEY = json.dumps({"problem": "p", "why_dangerous": "w", "direction": "change it to `safe(x)`"})


def test_llm_good_answer_is_used():
    assert _llm([GOOD]).explain(finding(), "en").problem == "p"


def test_llm_code_answer_is_retried_then_accepted():
    assert _llm([CODEY, GOOD]).explain(finding(), "en").problem == "p"


def test_llm_keeps_breaking_rules_then_template_is_used():
    exp = _llm([CODEY, "not json"]).explain(finding(), "en")
    assert "Problem" in exp.problem  # the template starts from the finding title


def test_snippet_is_not_sent_by_default():
    sent = {}

    def handler(request):
        sent["body"] = request.content.decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": GOOD}}]})

    ex = LLMExplainer("http://x", "k", "m", client=httpx.Client(transport=httpx.MockTransport(handler)))
    ex.explain(finding(snippet="SECRET_VALUE"), "en")
    assert "SECRET_VALUE" not in sent["body"]
