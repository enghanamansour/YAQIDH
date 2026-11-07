import pytest

from src.policy import Policy, evaluate_policy
from src.schema import Closure, Finding, FindingStatus, Severity
from src.verifier import VerifierError, verify

SG = {"semgrep"}


def f(fp, tool="semgrep", component="", **kw):
    return Finding(fingerprint=fp, tool=tool, severity=Severity.HIGH, location=f"{fp}.py:1", component=component, **kw)


def by_fp(result):
    return {x.fingerprint: x for x in result.findings}


# --- the three outcomes ---

def test_gone_is_closed():
    r = verify([f("F-1")], [], tools_run=SG)
    out = by_fp(r)["F-1"]
    assert r.closed == ["F-1"]
    assert out.status == FindingStatus.FIXED
    assert out.closure.result == "closed" and out.closure.verified_by == "rescan"


def test_still_there_is_still_open():
    r = verify([f("F-1")], [f("F-1")], tools_run=SG)
    assert r.still_open == ["F-1"]
    assert by_fp(r)["F-1"].closure.result == "still_open"
    assert by_fp(r)["F-1"].status == FindingStatus.OPEN


def test_not_seen_before_is_new():
    r = verify([f("F-1")], [f("F-1"), f("F-2")], tools_run=SG)
    assert r.new == ["F-2"]
    out = by_fp(r)["F-2"]
    assert out.origin == "new" and out.status == FindingStatus.OPEN and out.closure is None


def test_mix():
    r = verify([f("F-1"), f("F-2")], [f("F-2"), f("F-3")], tools_run=SG)
    assert (r.closed, r.still_open, r.new) == (["F-1"], ["F-2"], ["F-3"])


def test_claimed_fixed_but_still_there_goes_back_to_open():
    r = verify([f("F-1", status=FindingStatus.FIXED)], [f("F-1")], tools_run=SG)
    assert by_fp(r)["F-1"].status == FindingStatus.OPEN


def test_excepted_finding_stays_excepted_while_present():
    r = verify([f("F-1", status=FindingStatus.EXCEPTED)], [f("F-1")], tools_run=SG)
    assert by_fp(r)["F-1"].status == FindingStatus.EXCEPTED


def test_closed_finding_that_comes_back_is_reopened():
    old = f("F-1", status=FindingStatus.FIXED, closure=Closure(result="closed"))
    r = verify([old], [f("F-1")], tools_run=SG)
    assert r.reopened == ["F-1"]
    out = by_fp(r)["F-1"]
    assert out.status == FindingStatus.OPEN and out.closure is None


def test_already_closed_stays_closed_and_is_not_reported_again():
    old = f("F-1", status=FindingStatus.FIXED, closure=Closure(result="closed"))
    r = verify([old], [], tools_run=SG)
    assert r.closed == [] and by_fp(r)["F-1"] == old


# --- deterministic ---

def test_input_order_does_not_change_the_outcome():
    prev, cur = [f("F-1"), f("F-2"), f("F-3")], [f("F-3"), f("F-4"), f("F-5")]
    a = verify(prev, cur, tools_run=SG)
    b = verify(list(reversed(prev)), list(reversed(cur)), tools_run=SG)
    strip = lambda r: [x.model_copy(update={"closure": x.closure and x.closure.result}) for x in r.findings]
    assert strip(a) == strip(b)
    assert (a.closed, a.still_open, a.new) == (b.closed, b.still_open, b.new)


# --- refusing instead of guessing ---

def test_refuses_when_no_tool_ran():
    with pytest.raises(VerifierError):
        verify([f("F-1")], [], tools_run=set())


def test_refuses_when_a_tool_with_findings_did_not_run():
    # Trivy failed, so only Semgrep ran: Trivy's findings must not look closed.
    with pytest.raises(VerifierError, match="trivy did not run"):
        verify([f("F-1", tool="trivy")], [], tools_run=SG)


def test_does_not_refuse_for_a_tool_that_did_not_run_if_it_was_already_closed():
    old = f("F-1", tool="trivy", status=FindingStatus.FIXED, closure=Closure(result="closed"))
    assert verify([old], [], tools_run=SG).findings == [old]


def test_refuses_findings_from_a_tool_that_is_not_listed_as_run():
    with pytest.raises(VerifierError):
        verify([], [f("F-1", tool="trivy")], tools_run=SG)


def test_refuses_duplicate_fingerprints():
    with pytest.raises(VerifierError):
        verify([f("F-1"), f("F-1")], [], tools_run=SG)
    with pytest.raises(VerifierError):
        verify([], [f("F-1"), f("F-1")], tools_run=SG)


def test_refuses_when_semgrep_rules_changed():
    with pytest.raises(VerifierError, match="rules changed"):
        verify([f("F-1")], [], tools_run=SG,
               previous_versions={"semgrep-rules": "a"}, current_versions={"semgrep-rules": "b"})


# --- Trivy DB updates ---

TR = {"trivy"}
OLD_DB, NEW_DB = {"trivy-db": "2026-11-01"}, {"trivy-db": "2026-11-07"}


def test_new_finding_on_an_unchanged_package_after_a_db_update_is_tagged():
    r = verify([f("F-1", "trivy", "flask==0.12.2")], [f("F-1", "trivy", "flask==0.12.2"), f("F-2", "trivy", "flask==0.12.2")],
               tools_run=TR, previous_versions=OLD_DB, current_versions=NEW_DB,
               components_before={"flask==0.12.2"})
    assert r.new_from_db_update == ["F-2"] and r.new == []
    assert by_fp(r)["F-2"].origin == "new_from_db_update"


def test_package_with_no_vulnerabilities_before_is_also_recognised():
    r = verify([], [f("F-2", "trivy", "requests==2.32.3")], tools_run=TR,
               previous_versions=OLD_DB, current_versions=NEW_DB,
               components_before={"requests==2.32.3"})
    assert r.new_from_db_update == ["F-2"]


def test_new_finding_on_a_new_dependency_is_plain_new_even_if_the_db_changed():
    r = verify([], [f("F-2", "trivy", "django==1.0")], tools_run=TR,
               previous_versions=OLD_DB, current_versions=NEW_DB, components_before={"flask==0.12.2"})
    assert r.new == ["F-2"] and r.new_from_db_update == []


def test_same_db_means_plain_new():
    r = verify([], [f("F-2", "trivy", "flask==0.12.2")], tools_run=TR,
               previous_versions=OLD_DB, current_versions=OLD_DB, components_before={"flask==0.12.2"})
    assert r.new == ["F-2"]


def test_db_change_without_known_packages_warns_and_does_not_tag():
    r = verify([], [f("F-2", "trivy", "flask==0.12.2")], tools_run=TR,
               previous_versions=OLD_DB, current_versions=NEW_DB)
    assert r.new == ["F-2"] and any("earlier packages are unknown" in w for w in r.warnings)


def test_db_change_with_closures_warns():
    r = verify([f("F-1", "trivy", "flask==0.12.2")], [], tools_run=TR,
               previous_versions=OLD_DB, current_versions=NEW_DB, components_before={"flask==0.12.2"})
    assert r.closed == ["F-1"] and any("may come from the DB" in w for w in r.warnings)


def test_secrets_are_never_tagged_as_db_updates():
    r = verify([], [f("F-2", "trivy")], tools_run=TR, previous_versions=OLD_DB, current_versions=NEW_DB,
               components_before=set())
    assert r.new == ["F-2"]


# --- together with the policy ---

def test_policy_passes_only_after_the_verifier_closed_everything():
    policy = Policy(block_on=[Severity.HIGH])
    prev = [f("F-1")]
    claimed = [p.model_copy(update={"status": FindingStatus.FIXED}) for p in prev]
    assert evaluate_policy(claimed, policy).result == "fail"  # a claim is not proof
    assert evaluate_policy(verify(prev, [f("F-1")], tools_run=SG).findings, policy).result == "fail"
    assert evaluate_policy(verify(prev, [], tools_run=SG).findings, policy).result == "pass"
    assert evaluate_policy(verify(prev, [f("F-9")], tools_run=SG).findings, policy).result == "fail"  # new one
