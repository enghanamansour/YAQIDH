"""Runs the tools of one stage and returns one combined result. Plain code; the agent never picks tools."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from src.schema import Finding, StageName
from src.settings import Settings
from src.tools.base import ToolError


@dataclass
class ScanResult:
    findings: list[Finding]
    versions: dict[str, str]
    tools_run: set[str]
    components: set[str] = field(default_factory=set)
    flaky: list[str] = field(default_factory=list)


Runner = Callable[[Path], ScanResult]


def dedupe(findings: list[Finding]) -> list[Finding]:
    """Identical rule + file + code is one finding by design (the fingerprint has no line number)."""
    seen: dict[str, Finding] = {}
    for f in sorted(findings, key=lambda f: (f.location, f.fingerprint)):
        seen.setdefault(f.fingerprint, f)
    return sorted(seen.values(), key=lambda f: (f.location, f.fingerprint))


def security_runner(semgrep, trivy) -> Runner:
    def run(target: Path) -> ScanResult:
        trivy_scan = trivy.scan(target)
        findings = semgrep.run(target) + trivy_scan.findings
        versions = {"semgrep-rules": semgrep.rules_version(), **trivy.versions()}
        return ScanResult(dedupe(findings), versions, {"semgrep", "trivy"}, trivy_scan.components)

    return run


def qa_runner(playwright, app_factory) -> Runner:
    """app_factory() is a context manager that starts the app under test and gives its URL."""

    def run(target: Path) -> ScanResult:
        with app_factory() as base_url:
            scan = playwright.scan(base_url)
        return ScanResult(scan.findings, scan.versions, {"playwright"}, flaky=scan.flaky)

    return run


def default_runners(settings: Settings) -> dict[StageName, Runner]:
    """A stage without a runner fails loudly instead of passing."""
    from qa_checks.maktabti_security import CHECKS
    from src.tools.qa.app_server import AppServer
    from src.tools.qa.playwright_tool import PlaywrightTool
    from src.tools.security.semgrep import SemgrepTool
    from src.tools.security.trivy import TrivyTool

    return {
        StageName.QA: qa_runner(PlaywrightTool(CHECKS), lambda: AppServer("demo_app.app")),
        StageName.SECURITY: security_runner(SemgrepTool(settings.semgrep_rules_dir), TrivyTool()),
    }


class NoRunner(ToolError):
    pass
