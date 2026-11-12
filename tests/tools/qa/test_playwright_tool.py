from contextlib import contextmanager

import pytest

from qa_checks.maktabti_security import CHECKS
from src.schema import Severity
from src.tools.base import ToolError
from src.tools.qa.app_server import AppServer
from src.tools.qa.checks import Check
from src.tools.qa.playwright_tool import PlaywrightTool, run_check, to_findings


class Pages:
    """Hands out a fresh fake page per attempt and counts them."""

    def __init__(self):
        self.opened = 0
        self.pages = []

    @contextmanager
    def __call__(self):
        self.opened += 1
        page = object()
        self.pages.append(page)
        yield page


def failing(times, error=AssertionError("expected X, got Y")):
    """A check that fails the first `times` calls and passes afterwards."""
    calls = {"n": 0}

    def fn(page, base_url):
        calls["n"] += 1
        if calls["n"] <= times:
            raise error

    fn.__module__ = "qa_checks.fake"
    return Check("some_check", fn)


# --- retries ---

def test_passing_check_runs_once():
    pages = Pages()
    r = run_check(failing(0), pages, "http://x")
    assert (r.passed, r.attempts, r.flaky) == (True, 1, False) and pages.opened == 1


def test_check_that_passes_on_a_retry_is_flaky_not_a_failure():
    r = run_check(failing(2), Pages(), "http://x")
    assert (r.passed, r.attempts, r.flaky) == (True, 3, True)
    assert to_findings([r]) == []


def test_check_that_fails_every_time_fails_after_two_retries():
    pages = Pages()
    r = run_check(failing(99), pages, "http://x")
    assert (r.passed, r.attempts) == (False, 3) and pages.opened == 3
    assert r.detail == "expected X, got Y"


def test_every_attempt_gets_a_fresh_page():
    pages = Pages()
    run_check(failing(99), pages, "http://x")
    assert len({id(p) for p in pages.pages}) == 3


def test_non_assertion_errors_count_as_failures_with_their_type():
    r = run_check(failing(99, TimeoutError("waited too long")), Pages(), "http://x")
    assert not r.passed and r.detail == "TimeoutError: waited too long"


def test_retries_can_be_set():
    assert run_check(failing(99), Pages(), "http://x", retries=0).attempts == 1


# --- findings ---

def test_failed_check_becomes_one_high_finding():
    (f,) = to_findings([run_check(failing(99), Pages(), "http://x")])
    assert f.tool == "playwright" and f.severity == Severity.HIGH and f.reported_as == "high"
    assert f.rule == "some_check" and f.location == "qa_checks/fake.py::some_check"
    assert f.detail == "expected X, got Y" and f.fingerprint.startswith("F-")


def test_fingerprint_ignores_the_error_message_and_the_number_of_attempts():
    a = to_findings([run_check(failing(99, AssertionError("one")), Pages(), "http://x")])[0]
    b = to_findings([run_check(failing(99, AssertionError("two")), Pages(), "http://x", retries=0)])[0]
    assert a.fingerprint == b.fingerprint


def test_different_checks_get_different_fingerprints():
    other = failing(99)
    other = Check("another_check", other.fn)
    fps = {to_findings([run_check(c, Pages(), "http://x")])[0].fingerprint for c in (failing(99), other)}
    assert len(fps) == 2


# --- the tool ---

def test_tool_rejects_empty_or_duplicate_checks():
    with pytest.raises(ValueError):
        PlaywrightTool([])
    with pytest.raises(ValueError):
        PlaywrightTool([failing(0), failing(0)])


def test_unreachable_app_is_an_error_not_a_pile_of_findings():
    with pytest.raises(ToolError, match="not reachable"):
        PlaywrightTool(CHECKS).scan("http://127.0.0.1:1")


def test_app_that_does_not_start_is_an_error(tmp_path):
    (tmp_path / "broken.py").write_text("raise SystemExit('boom')\n")
    with pytest.raises(ToolError, match="did not start"):
        with AppServer("broken", cwd=tmp_path, startup_timeout=5):
            pass


# --- a real browser against the real demo app ---

@pytest.fixture(scope="module")
def real_scan():
    with AppServer("demo_app.app") as url:
        return PlaywrightTool(CHECKS).scan(url)


def test_real_scan_finds_exactly_the_planted_defects(real_scan):
    # the two planted defects, plus a session that never expires
    assert sorted(f.rule for f in real_scan.findings) == sorted([
        "errors_do_not_leak_internals", "search_resists_sql_injection", "session_expires_after_inactivity",
    ])
    assert all(f.severity == Severity.HIGH for f in real_scan.findings)


def test_real_scan_passes_the_protections_the_app_has(real_scan):
    assert not {"cart_requires_login", "wrong_password_is_rejected", "security_headers_are_set"} & {
        f.rule for f in real_scan.findings
    }
    assert real_scan.flaky == []


def test_real_scan_records_versions_and_what_was_checked(real_scan):
    assert set(real_scan.versions) == {"playwright", "chromium"}
    assert real_scan.checked == sorted(c.name for c in CHECKS)
