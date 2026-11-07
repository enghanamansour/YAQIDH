from pathlib import Path

import pytest

from src.policy import ExceptionRules, Policy, PolicyError, evaluate_policy, load_policy
from src.schema import Closure, ExceptionRecord, Finding, FindingStatus, Severity

DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "config" / "policy.yaml"


def finding(fingerprint="F-1", severity=Severity.HIGH, status=FindingStatus.OPEN, **kw):
    return Finding(fingerprint=fingerprint, tool="semgrep", severity=severity, location="a.py:1", status=status, **kw)


@pytest.fixture
def policy():
    return Policy(block_on=[Severity.HIGH])


# --- the basic decision ---

def test_open_high_fails(policy):
    d = evaluate_policy([finding()], policy)
    assert d.result == "fail"
    assert d.reasons == ["1 high open"]
    assert d.decided_by == "policy_engine"


def test_no_findings_passes(policy):
    d = evaluate_policy([], policy)
    assert (d.result, d.reasons) == ("pass", ["no blocking findings"])


def test_low_passes(policy):
    d = evaluate_policy([finding("a", Severity.LOW), finding("b", Severity.LOW)], policy)
    assert (d.result, d.reasons) == ("pass", ["no blocking findings"])


def test_high_blocks_even_with_lows_around(policy):
    fs = [finding("a", Severity.HIGH), finding("b", Severity.LOW), finding("c", Severity.HIGH)]
    assert evaluate_policy(fs, policy).reasons == ["2 high open"]


# --- the same decision every time ---

def test_finding_order_does_not_change_the_decision(policy):
    fs = [finding("a", Severity.HIGH), finding("b", Severity.LOW), finding("c", Severity.HIGH)]
    assert evaluate_policy(fs, policy) == evaluate_policy(list(reversed(fs)), policy)


# --- changing the policy changes the behaviour, with no code change ---

def test_policy_change_changes_the_result():
    low = [finding(severity=Severity.LOW)]
    assert evaluate_policy(low, Policy(block_on=[Severity.HIGH])).result == "pass"
    assert evaluate_policy(low, Policy(block_on=[Severity.HIGH, Severity.LOW])).result == "fail"


# --- fixed findings only count as fixed when the verifier closed them ---

def test_fixed_with_verified_closure_does_not_count(policy):
    f = finding(status=FindingStatus.FIXED, closure=Closure(result="closed"))
    assert evaluate_policy([f], policy).result == "pass"


def test_fixed_without_closure_still_counts(policy):
    d = evaluate_policy([finding(status=FindingStatus.FIXED)], policy)
    assert d.result == "fail"
    assert "F-1: marked fixed without a verified closure" in d.reasons


def test_fixed_but_rescan_says_still_open_counts(policy):
    f = finding(status=FindingStatus.FIXED, closure=Closure(result="still_open"))
    assert evaluate_policy([f], policy).result == "fail"


# --- exceptions need a justification and a human approval ---

def excepted(**exc):
    return finding(status=FindingStatus.EXCEPTED, reported_as="medium", exception=ExceptionRecord(**exc))


def test_full_exception_is_honored(policy):
    assert evaluate_policy([excepted(justification="legacy, fix planned", approved_by="Sara")], policy).result == "pass"


def test_exception_without_justification_is_ignored(policy):
    d = evaluate_policy([excepted(approved_by="Sara")], policy)
    assert d.result == "fail"
    assert "F-1: exception ignored, no justification" in d.reasons


def test_exception_without_approval_is_ignored(policy):
    d = evaluate_policy([excepted(justification="legacy")], policy)
    assert d.result == "fail"
    assert "F-1: exception ignored, no human approval" in d.reasons


def test_excepted_with_no_record_at_all_is_ignored(policy):
    assert evaluate_policy([finding(status=FindingStatus.EXCEPTED, reported_as="medium")], policy).result == "fail"


@pytest.mark.parametrize("level", ["critical", "high", "unknown", ""])
def test_exception_is_not_allowed_above_medium(policy, level):
    f = finding(
        status=FindingStatus.EXCEPTED,
        reported_as=level,
        exception=ExceptionRecord(justification="legacy", approved_by="Sara"),
    )
    d = evaluate_policy([f], policy)
    assert d.result == "fail"
    assert f"F-1: exception ignored, not allowed for {level or 'unknown'}" in d.reasons


def test_allowed_levels_can_be_widened_in_the_policy():
    wide = Policy(block_on=[Severity.HIGH], exceptions=ExceptionRules(allowed_for=["medium", "high"]))
    f = finding(
        status=FindingStatus.EXCEPTED,
        reported_as="high",
        exception=ExceptionRecord(justification="legacy", approved_by="Sara"),
    )
    assert evaluate_policy([f], wide).result == "pass"


def test_exception_rules_can_be_relaxed_in_the_policy():
    relaxed = Policy(
        block_on=[Severity.HIGH],
        exceptions=ExceptionRules(require_justification=False, require_human_approval=False, allowed_for=[]),
    )
    assert evaluate_policy([finding(status=FindingStatus.EXCEPTED)], relaxed).result == "pass"


# --- loading the policy file ---

def test_default_policy_file_loads():
    p = load_policy(DEFAULT_POLICY)
    assert p.block_on == [Severity.HIGH]
    assert p.exceptions.require_justification and p.exceptions.require_human_approval
    assert p.exceptions.allowed_for == ["medium"]


def write(tmp_path, text):
    path = tmp_path / "policy.yaml"
    path.write_text(text)
    return path


def test_policy_file_changes_behaviour(tmp_path):
    low = [finding(severity=Severity.LOW)]
    assert evaluate_policy(low, load_policy(write(tmp_path, "block_on: [high]\n"))).result == "pass"
    assert evaluate_policy(low, load_policy(write(tmp_path, "block_on: [high, low]\n"))).result == "fail"


@pytest.mark.parametrize(
    "text",
    [
        "block_in: [high]\n",  # typo in the key: must not silently mean 'block nothing'
        "exceptions: {}\n",  # block_on missing
        "block_on: [catastrophic]\n",  # unknown severity
        "block_on: [medium]\n",  # severity that no longer exists
        "block_on: [high]\nwarn_on: [low]\n",  # removed key
        "block_on: [high]\nexceptions:\n  require_justificaton: true\n",  # typo inside exceptions
        "- just\n- a list\n",
        "block_on: [high\n",  # broken YAML
    ],
)
def test_invalid_policy_files_are_rejected(tmp_path, text):
    with pytest.raises(PolicyError):
        load_policy(write(tmp_path, text))


def test_missing_policy_file_is_rejected(tmp_path):
    with pytest.raises(PolicyError):
        load_policy(tmp_path / "nope.yaml")
