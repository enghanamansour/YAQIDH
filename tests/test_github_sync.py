import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.github_sync import GitHubPublisher, release_id_for, render_comment
from src.history import HistoryLog
from src.schema import Closure, Decision, Explanation, FindingStatus, HumanDecision, Severity, StageName, utcnow
from tests.test_http_api import Stack, finding

SHA = "a" * 40
SECRET = "whsec"


class FakeGitHub:
    def __init__(self, fail=False):
        self.comments, self.statuses, self.fail = {}, [], fail

    def upsert_comment(self, repo, pr, phase, body):
        if self.fail:
            raise RuntimeError("github is down")
        action = "updated" if (repo, pr, phase) in self.comments else "created"
        self.comments[(repo, pr, phase)] = body
        return {"action": action}

    def set_status(self, repo, commit, phase, *, allowed, description):
        self.statuses.append((repo, commit, phase, allowed, description))
        return {"state": "success" if allowed else "failure"}


def evidence_with_findings():
    from src.schema import Evidence
    e = Evidence(release_id="r1", head_commit=SHA, repo="o/n", pr_number=7)
    sec = e.stage(StageName.SECURITY)
    sec.tool_versions, sec.scanned_at, sec.scanned_commit = {"t": "1"}, utcnow(), SHA
    a = finding("F-1", Severity.HIGH).model_copy(update={
        "rule": "CVE-1", "component": "flask==0.12.2", "fixed_version": "0.12.3", "cwe": "CWE-400",
        "explanation": Explanation(text="المشكلة: x\nاتجاه الإصلاح: y")})
    b = finding("F-2", Severity.HIGH).model_copy(update={"confidence": "low", "detail": "tool said so"})
    c = finding("F-3", Severity.HIGH).model_copy(update={"status": FindingStatus.FIXED, "closure": Closure(result="closed")})
    sec.findings = [a, b, c]
    sec.decision = Decision(result="fail", reasons=["2 high open"])
    sec.flaky_tests = ["wobbly"]
    return e


def test_the_comment_shows_status_findings_fix_version_and_marks_the_ai_text():
    text = render_comment(evidence_with_findings())
    assert "CVE-1" in text and "0.12.3" in text and "CWE-400" in text
    assert "شرح يقظ" in text and "مو حقيقة مثبتة" in text
    assert "ثقة منخفضة" in text and "tool said so" in text  # a low-confidence finding says so; no explanation yet shows the tool text
    assert "F-3" in text and "wobbly" in text
    assert "ما يقرر ولا يصلح ولا يدمج" in text


def test_a_huge_comment_is_cut_below_the_github_limit():
    e = evidence_with_findings()
    e.stage(StageName.SECURITY).findings = [finding(f"F-{i}").model_copy(update={"detail": "d" * 500}) for i in range(500)]
    assert len(render_comment(e)) < 65536


def test_release_ids_are_safe_and_stable():
    assert release_id_for("owner/my.repo", 12) == "owner-my-repo-pr12"
    assert len(release_id_for("o" * 200 + "/n", 3)) <= 64
    assert release_id_for("a/b", 1) == release_id_for("a/b", 1)


@pytest.fixture
def stack(tmp_path):
    return Stack(tmp_path)


def test_publishing_updates_one_comment_and_sets_both_statuses(stack):
    gh = FakeGitHub()
    pub = GitHubPublisher(stack.service.store, stack.history, gh)
    e = evidence_with_findings()
    stack.service.store.save(e)
    pub.publish("r1")
    pub.publish("r1")
    assert len(gh.comments) == 1  # edited in place, never a second comment
    assert {s[2] for s in gh.statuses} == {"staging", "main"} and not any(s[3] for s in gh.statuses)
    assert all(s[1] == SHA for s in gh.statuses)
    assert "github_published" in [x["event"] for x in stack.history.entries("r1")]


def test_the_status_is_green_only_when_our_gate_says_so(stack):
    from tests.test_gate import release
    gh = FakeGitHub()
    e = release(commit=SHA, qa_commit=SHA, sec_commit=SHA)
    e.repo, e.pr_number = "o/n", 1
    stack.service.store.save(e)
    GitHubPublisher(stack.service.store, stack.history, gh).publish("r1")
    assert {s[2]: s[3] for s in gh.statuses} == {"staging": True, "main": True}


def test_a_release_without_a_pull_request_is_skipped_and_a_short_commit_gets_no_status(stack):
    gh = FakeGitHub()
    pub = GitHubPublisher(stack.service.store, stack.history, gh)
    stack.service.set_head_commit("r1", "abc12345")
    assert "skipped" in pub.publish("r1") and not gh.comments
    stack.service.set_pull_request("r1", "o/n", 2)
    pub.publish("r1")
    assert gh.comments and gh.statuses == []  # GitHub needs the full 40-character id for a status


def test_a_github_failure_is_logged_and_never_raised(stack):
    pub = GitHubPublisher(stack.service.store, stack.history, FakeGitHub(fail=True))
    stack.service.store.save(evidence_with_findings())
    assert "error" in pub.publish("r1")
    assert "github_post_failed" in [x["event"] for x in stack.history.entries("r1")]


# --- the webhook ---

def sign(body: bytes, secret=SECRET):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def pr_payload(action="opened", sha=SHA, number=7):
    return {"action": action, "number": number, "repository": {"full_name": "o/n"}, "pull_request": {"head": {"sha": sha}}}


@pytest.fixture
def hook(stack, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    gh = FakeGitHub()
    client = TestClient(create_app(stack.service, stack.history, stack.agent, GitHubPublisher(stack.service.store, stack.history, gh)))

    def send(payload, event="pull_request", secret=SECRET):
        body = json.dumps(payload).encode()
        return client.post("/github/webhook", content=body, headers={"X-GitHub-Event": event, "X-Hub-Signature-256": sign(body, secret),
                                                                  "Content-Type": "application/json"})
    return send, gh, stack


def test_an_unsigned_or_wrongly_signed_event_is_refused_and_starts_nothing(hook, stack, monkeypatch):
    send, gh, st = hook
    assert send(pr_payload(), secret="wrong").status_code == 401
    assert st.runs == []
    client = TestClient(create_app(st.service, st.history, st.agent))
    assert client.post("/github/webhook", json=pr_payload(), headers={"X-GitHub-Event": "pull_request"}).status_code == 401
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET")
    assert send(pr_payload()).status_code == 503  # fail closed with no secret


def test_a_new_pull_request_creates_the_release_runs_the_agent_and_posts_to_github(hook):
    send, gh, st = hook
    r = send(pr_payload())
    assert r.status_code == 200 and r.json() == {"accepted": True, "release_id": "o-n-pr7", "event": "pull_request_opened"}
    assert st.runs == [("o-n-pr7", "pull_request_opened")]
    e = st.service.store.get("o-n-pr7")
    assert (e.repo, e.pr_number, e.head_commit) == ("o/n", 7, SHA)
    assert len(gh.comments) == 1 and {s[2] for s in gh.statuses} == {"staging", "main"}


def test_new_commits_on_the_same_pr_update_the_same_comment_and_run_a_push(hook):
    send, gh, st = hook
    send(pr_payload())
    send(pr_payload("synchronize", sha="b" * 40))
    assert [r[1] for r in st.runs] == ["pull_request_opened", "push"]
    assert st.service.store.get("o-n-pr7").head_commit == "b" * 40
    assert len(gh.comments) == 1


@pytest.mark.parametrize("action", ["closed", "labeled", "edited"])
def test_other_pull_request_actions_are_ignored(hook, action):
    send, gh, st = hook
    assert "ignored" in send(pr_payload(action)).json() and st.runs == []


def test_ping_other_events_and_broken_payloads(hook):
    send, gh, st = hook
    assert send({}, event="ping").json() == {"pong": True}
    assert send({}, event="issues").json() == {"ignored": "issues"}
    assert send({"action": "opened"}).status_code == 422
    assert st.runs == []


def test_the_publisher_works_with_the_real_github_client_against_a_pretend_github(stack):
    """No network: the backend's GitHubClient talks to a fake GitHub that records each request."""
    import httpx

    from src.github_sync import github_client

    seen, existing = [], []

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json=existing)
        if request.url.path.endswith("/comments"):
            existing.append({"id": 5, "body": json.loads(request.content)["body"]})
            return httpx.Response(201, json={"id": 5})
        return httpx.Response(200 if "comments/5" in request.url.path else 201, json={"id": 5})

    client = github_client("tok")
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    stack.service.store.save(evidence_with_findings())
    pub = GitHubPublisher(stack.service.store, stack.history, client)
    pub.publish("r1")
    pub.publish("r1")
    posts = [s for s in seen if s[0] == "POST" and s[1].endswith("/comments")]
    patches = [s for s in seen if s[0] == "PATCH"]
    statuses = [s for s in seen if s[1].startswith(f"/repos/o/n/statuses/{SHA}")]
    assert len(posts) == 1 and len(patches) == 1 and len(statuses) == 4  # one comment, edited once; 2 statuses per publish
