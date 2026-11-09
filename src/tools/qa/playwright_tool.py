"""Runs the QA security checks in a real browser and turns failures into findings.

A failed check is tried again (twice by default). Passing on a retry means flaky: it is logged but is
not a finding. Failing every time is a high finding. The fingerprint comes from the check's name and
file, never from the error message, so the same broken check keeps the same fingerprint between scans.
"""

import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field

from src.schema import Finding, Severity
from src.tools.base import ToolError
from src.tools.fingerprint import fingerprint
from src.tools.qa.checks import Check

RETRIES = 2


@dataclass
class CheckResult:
    check: Check
    passed: bool
    attempts: int
    detail: str = ""

    @property
    def flaky(self) -> bool:
        return self.passed and self.attempts > 1


@dataclass
class QaScan:
    findings: list[Finding]
    flaky: list[str]
    versions: dict[str, str]
    checked: list[str] = field(default_factory=list)


def _message(error: BaseException) -> str:
    text = " ".join(str(error).split())
    return text if isinstance(error, AssertionError) and text else f"{type(error).__name__}: {text}"[:500]


def run_check(check: Check, new_page: Callable[[], AbstractContextManager], base_url: str, retries: int = RETRIES) -> CheckResult:
    """new_page() gives a fresh page each attempt, so a retry never inherits the state of a failed try."""
    detail = ""
    for attempt in range(1, retries + 2):
        try:
            with new_page() as page:
                check.fn(page, base_url)
            return CheckResult(check, True, attempt)
        except Exception as e:  # any error inside a check (assertion, timeout, crash) counts as a failure
            detail = _message(e)
    return CheckResult(check, False, retries + 1, detail)


def to_findings(results: Sequence[CheckResult]) -> list[Finding]:
    findings = [
        Finding(
            fingerprint=fingerprint("playwright", r.check.name, r.check.file, ""),
            tool="playwright",
            severity=Severity.HIGH,
            reported_as="high",
            location=f"{r.check.file}::{r.check.name}",
            rule=r.check.name,
            detail=r.detail,
        )
        for r in results
        if not r.passed
    ]
    return sorted(findings, key=lambda f: (f.location, f.fingerprint))


class PlaywrightTool:
    name = "playwright"

    def __init__(self, checks: Sequence[Check], retries: int = RETRIES):
        names = [c.name for c in checks]
        if len(set(names)) != len(names):
            raise ValueError("two checks share a name")
        if not checks:
            raise ValueError("no checks given")
        self.checks = list(checks)
        self.retries = retries

    @staticmethod
    def _preflight(base_url: str) -> None:
        """If the app is not reachable, every check would fail for the wrong reason. Stop instead."""
        try:
            urllib.request.urlopen(base_url, timeout=10).close()
        except urllib.error.HTTPError:
            pass  # the server answered, which is all we need here
        except (urllib.error.URLError, OSError) as e:
            raise ToolError(f"the app under test is not reachable at {base_url}: {e}") from e

    def scan(self, base_url: str) -> QaScan:
        self._preflight(base_url)
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise ToolError("playwright is not installed (pip install playwright && playwright install chromium)") from e
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                try:
                    from importlib.metadata import version

                    versions = {"playwright": version("playwright"), "chromium": browser.version}

                    def new_page():
                        return _Page(browser)

                    results = [run_check(c, new_page, base_url, self.retries) for c in self.checks]
                finally:
                    browser.close()
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"playwright could not run: {e}") from e
        return QaScan(
            findings=to_findings(results),
            flaky=sorted(r.check.name for r in results if r.flaky),
            versions=versions,
            checked=sorted(r.check.name for r in results),
        )

    def run(self, base_url: str) -> list[Finding]:
        return self.scan(base_url).findings


class _Page(AbstractContextManager):
    """A fresh browser context and page, closed afterwards."""

    def __init__(self, browser):
        self._context = browser.new_context()

    def __enter__(self):
        self._context.set_default_timeout(10_000)
        return self._context.new_page()

    def __exit__(self, *exc):
        self._context.close()
        return False
