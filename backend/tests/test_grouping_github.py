import json
from pathlib import Path

import httpx
import pytest

from app.adapters import from_team_findings
from app.explainer import LLMExplainer, explain_group
from app.github import GitHubClient, GitHubError, marker
from app.grouping import group_findings
from app.models import Finding

SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "team_findings_sample.json").read_text(encoding="utf-8"))


def f(rule="R", file="a.py", line=5, cwe=None, severity="high", confidence=None):
    return Finding(rule_id=rule, title=rule, severity=severity, file=file, line=line, cwe=cwe,
                   confidence=confidence, external_id=f"{rule}-{file}-{line}")


# ---- grouping ----
def test_the_sample_gives_two_groups_and_three_rules_in_the_first():
    groups = group_findings(from_team_findings(SAMPLE))
    assert [len(g.findings) for g in groups] == [3, 1]
    assert groups[0].severity == "high" and groups[1].severity == "low"
    assert len(groups[0].fingerprints) == 3  # every fingerprint is kept


def test_a_group_is_high_if_any_member_is_high():
    g = group_findings([f("A", severity="low"), f("B", severity="high")])[0]
    assert g.severity == "high" and g.representative.rule_id == "B"


def test_different_categories_on_one_line_stay_apart():
    groups = group_findings([f("A", cwe="CWE-89"), f("B", cwe="CWE-798")])
    assert len(groups) == 2


def test_findings_without_a_line_are_never_merged():
    groups = group_findings([f("CVE-1", file="requirements.txt", line=None),
                             f("CVE-2", file="requirements.txt", line=None)])
    assert len(groups) == 2


def test_different_lines_stay_apart():
    assert len(group_findings([f("A", line=1), f("A", line=2)])) == 2


def test_low_confidence_only_when_every_member_is_unsure():
    assert group_findings([f("A", confidence="low")])[0].low_confidence
    assert not group_findings([f("A", confidence="low"), f("B", confidence="high")])[0].low_confidence
    assert not group_findings([f("A", confidence="low"), f("B")])[0].low_confidence


# ---- the explanation covers the whole group ----
def test_the_other_rules_reach_the_model():
    sent = {}

    def handler(request):
        sent["body"] = request.content.decode()
        good = json.dumps({"problem": "p", "why_dangerous": "w", "direction": "d"})
        return httpx.Response(200, json={"choices": [{"message": {"content": good}}]})

    agent = LLMExplainer("http://x", "k", "m", client=httpx.Client(transport=httpx.MockTransport(handler)))
    group = group_findings(from_team_findings(SAMPLE))[0]
    explain_group(agent, group, "en")
    for rule in group.rules:
        assert rule.split(".")[-1] in sent["body"]


def test_the_description_and_category_reach_the_model():
    sent = {}

    def handler(request):
        sent["body"] = request.content.decode()
        good = json.dumps({"problem": "p", "why_dangerous": "w", "direction": "d"})
        return httpx.Response(200, json={"choices": [{"message": {"content": good}}]})

    agent = LLMExplainer("http://x", "k", "m", client=httpx.Client(transport=httpx.MockTransport(handler)))
    item = Finding(rule_id="R", title="t", severity="high", file="a.py", line=1,
                   description="Untrusted input is concatenated into SQL", cwe="CWE-89")
    agent.explain(item, "en")
    assert "Untrusted input is concatenated into SQL" in sent["body"] and "CWE-89" in sent["body"]


# ---- GitHub ----
FULL = "a" * 40


def make_client(handler):
    return GitHubClient("tok", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_the_first_comment_is_created_and_a_later_one_is_updated():
    calls = []
    existing = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json=existing)
        if request.method == "POST":
            existing.append({"id": 7, "body": json.loads(request.content)["body"]})
            return httpx.Response(201, json={"id": 7})
        return httpx.Response(200, json={"id": 7})

    gh = make_client(handler)
    assert gh.upsert_comment("o/r", 3, "security", "hello")["action"] == "created"
    assert gh.upsert_comment("o/r", 3, "security", "hello again")["action"] == "updated"
    assert ("PATCH", "/repos/o/r/issues/comments/7") in calls
    assert sum(1 for m, _ in calls if m == "POST") == 1  # no second comment


def test_each_phase_has_its_own_comment():
    posted = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": 1, "body": marker("qa") + "\nold"}])
        posted.append(request.method)
        return httpx.Response(201, json={"id": 2})

    make_client(handler).upsert_comment("o/r", 3, "security", "x")
    assert posted == ["POST"]  # the qa comment is not touched


def test_status_is_failure_when_blocked_and_success_when_allowed():
    sent = []

    def handler(request):
        sent.append((request.url.path, json.loads(request.content)))
        return httpx.Response(201, json={})

    gh = make_client(handler)
    gh.set_status("o/r", FULL, "security", allowed=False, description="blocked")
    gh.set_status("o/r", FULL, "security", allowed=True, description="ok")
    assert sent[0] == (f"/repos/o/r/statuses/{FULL}",
                       {"state": "failure", "context": "yaqidh/security", "description": "blocked"})
    assert sent[1][1]["state"] == "success"


def test_a_short_commit_id_is_refused_for_the_status():
    gh = make_client(lambda r: httpx.Response(201, json={}))
    with pytest.raises(GitHubError):
        gh.set_status("o/r", "abc1234", "security", allowed=True, description="x")


def test_a_github_error_is_raised_not_swallowed():
    gh = make_client(lambda r: httpx.Response(403, json={"message": "no"}))
    with pytest.raises(GitHubError):
        gh.upsert_comment("o/r", 1, "security", "x")
