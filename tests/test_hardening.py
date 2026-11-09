"""Small hardening fixes found while rehearsing the whole loop (see test_pr_loop_fixes.py for the big ones)."""
import hashlib
import hmac
import json
import multiprocessing
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.github_sync import render_comment
from src.history import HistoryLog
from src.lock import InterProcessLock
from src.schema import Evidence, Finding, Severity, StageName, utcnow
from src.service import ReleaseService
from src.storage import EvidenceStore
from tests.test_service import POLICY, FakeScanner, finding

HOSTILE = "see @octocat and [click](http://evil.example) <img src=x onerror=alert(1)> `x`"


# ---- time never repeats, so "after the scan" always has an answer ----
def test_utcnow_never_repeats_or_goes_back():
    stamps = [utcnow() for _ in range(5000)]
    assert all(b > a for a, b in zip(stamps, stamps[1:]))


# ---- text from a tool or the model is made safe before it reaches a public comment ----
def _evidence_with(detail: str, explanation: str | None = None) -> Evidence:
    from src.schema import Explanation

    ev = Evidence(release_id="r1", repo="o/r", pr_number=1, head_commit="a" * 40)
    qa = ev.stage(StageName.QA)
    qa.tool_versions = {"playwright": "1"}
    qa.scanned_at = utcnow() - timedelta(seconds=1)
    qa.findings = [Finding(fingerprint="F-1", tool="playwright", severity=Severity.HIGH, reported_as="high",
                           rule="r`ule", location="GET /x", detail=detail,
                           explanation=Explanation(text=explanation) if explanation else None)]
    return ev


def test_a_scanner_message_cannot_ping_link_or_inject_html_in_the_comment():
    text = render_comment(_evidence_with(HOSTILE))
    assert "@octocat" not in text            # no mention
    assert "](http" not in text              # no markdown link
    assert "<img" not in text and "&lt;img" in text
    assert "http://evil" not in text         # a bare link is not clickable either
    assert "`r`ule`" not in text             # a stray backtick cannot break the code span


def test_the_models_explanation_is_made_safe_too():
    text = render_comment(_evidence_with("d", explanation="المشكلة: @everyone [x](http://evil.example)"))
    assert "@everyone" not in text and "](http" not in text


def test_normal_text_still_reads_normally():
    text = render_comment(_evidence_with("the error page shows a stack trace"))
    assert "the error page shows a stack trace" in text


# ---- a redelivered webhook is handled once ----
def _webhook_client(tmp_path, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "t")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s3cret")
    history = HistoryLog(tmp_path / "h")
    svc = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY,
                         {StageName.QA: FakeScanner([]), StageName.SECURITY: FakeScanner([])}, tmp_path, history)

    async def agent(release_id, event):
        return {"stopped": "done", "steps": 0, "calls": []}

    return TestClient(create_app(svc, history, agent)), history


def _send(client, delivery):
    payload = {"action": "opened", "number": 7, "repository": {"full_name": "o/r"},
               "pull_request": {"head": {"sha": "a" * 40, "ref": "feat"}, "user": {"login": "dev"}}}
    raw = json.dumps(payload).encode()
    headers = {"X-GitHub-Event": "pull_request", "Content-Type": "application/json",
               "X-Hub-Signature-256": "sha256=" + hmac.new(b"s3cret", raw, hashlib.sha256).hexdigest()}
    if delivery:
        headers["X-GitHub-Delivery"] = delivery
    return client.post("/github/webhook", headers=headers, content=raw)


def test_a_redelivered_webhook_is_ignored(tmp_path, monkeypatch):
    client, history = _webhook_client(tmp_path, monkeypatch)
    first = _send(client, "delivery-1")
    n = len(history.entries("o-r-pr7"))
    again = _send(client, "delivery-1")
    assert first.json()["accepted"] is True
    assert again.json() == {"ignored": "duplicate delivery"}
    assert len(history.entries("o-r-pr7")) == n  # nothing was added the second time


def test_a_different_delivery_is_not_mistaken_for_a_retry(tmp_path, monkeypatch):
    client, _ = _webhook_client(tmp_path, monkeypatch)
    assert _send(client, "delivery-1").json()["accepted"] is True
    assert _send(client, "delivery-2").json()["accepted"] is True


# ---- two processes write the same files: the lock must hold between them ----
def _increment(args):
    lock_path, counter_path, times = args
    lock = InterProcessLock(Path(lock_path))
    for _ in range(times):
        with lock:
            n = int(Path(counter_path).read_text())
            Path(counter_path).write_text(str(n + 1))  # a read-modify-write: loses updates without a lock


def test_the_lock_holds_between_processes(tmp_path):
    counter = tmp_path / "counter.txt"
    counter.write_text("0")
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(4) as pool:
        pool.map(_increment, [(str(tmp_path / ".lock"), str(counter), 40)] * 4)
    assert int(counter.read_text()) == 160
