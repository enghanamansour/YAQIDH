from datetime import timedelta

import pytest

from src.gate import check_gate
from src.schema import Decision, Evidence, HumanDecision, StageName, utcnow


def release(commit="aaa11111", qa_commit=None, sec_commit=None, qa_ok=True, sec_ok=True, qa_human=True, sec_human=True):
    e = Evidence(release_id="r1", head_commit=commit)
    t0 = utcnow() - timedelta(seconds=10)
    qa = e.stage(StageName.QA)
    qa.tool_versions, qa.scanned_at, qa.scanned_commit = {"p": "1"}, t0, qa_commit or commit
    qa.decision = Decision(result="pass" if qa_ok else "fail")
    if qa_human:
        e.human_decisions.append(HumanDecision(stage=StageName.QA, decision="approve", by="S", reason="", commit=commit))
    if sec_commit is not None or sec_ok is not None:
        sec = e.stage(StageName.SECURITY)
        sec.tool_versions, sec.scanned_at, sec.scanned_commit = {"t": "1"}, t0, sec_commit or commit
        sec.decision = Decision(result="pass" if sec_ok else "fail")
        if sec_human:
            e.human_decisions.append(HumanDecision(stage=StageName.SECURITY, decision="approve", by="S", reason="", commit=commit))
    return e


def test_everything_passed_and_approved_on_this_commit_opens_main():
    r = check_gate(release(), "aaa11111", "main")
    assert r.allowed and r.reason == "clean" and r.status == "ready_to_merge"


def test_staging_only_needs_qa():
    e = release(sec_ok=False, sec_human=False)
    assert check_gate(e, "aaa11111", "staging").allowed
    assert not check_gate(e, "aaa11111", "main").allowed


@pytest.mark.parametrize("evidence,commit,reason", [
    (None, "aaa11111", "no_release"),
    (release(), "", "no_commit"),
    (release(commit=""), "aaa11111", "no_commit"),
])
def test_missing_pieces_close_the_gate(evidence, commit, reason):
    assert check_gate(evidence, commit, "main").reason == reason


def test_a_newer_commit_closes_the_gate_for_the_old_one():
    r = check_gate(release(commit="bbb22222"), "aaa11111", "main")
    assert not r.allowed and r.reason == "stale_commit"


def test_a_push_after_the_approval_closes_the_gate_until_it_is_scanned_again():
    e = release(commit="bbb22222", qa_commit="aaa11111", sec_commit="aaa11111")  # scans are of the old commit
    r = check_gate(e, "bbb22222", "main")
    assert not r.allowed and r.reason == "stale_scan" and "qa" in r.detail[0] and "security" in r.detail[0]


def test_a_policy_failure_or_missing_approval_blocks_with_the_status_as_reason():
    assert check_gate(release(sec_ok=False), "aaa11111", "main").reason == "blocked"
    r = check_gate(release(sec_human=False), "aaa11111", "main")
    assert not r.allowed and r.status == "awaiting_security_approval"
