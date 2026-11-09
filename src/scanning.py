"""Runs the tools of one stage and returns one combined result. Plain code; the agent never picks tools."""

from collections.abc import Callable
from contextvars import ContextVar
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

# The release a scan is running for, set by the service around each runner call, so a runner that needs it
# (the CI one) can read it without every runner's signature changing.
CURRENT_RELEASE: ContextVar[str] = ContextVar("current_release", default="")


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


def submitted_runner(store, stage: StageName = StageName.SECURITY) -> Runner:
    """Results come from a CI job (it has the pull request's code), not from a scan on this machine."""

    def run(target: Path) -> ScanResult:
        evidence = store.get(CURRENT_RELEASE.get())
        pending = evidence.pending_qa_scan if stage == StageName.QA else evidence.pending_scan
        if pending is None or pending.commit != evidence.head_commit:
            raise ToolError(
                f"waiting for the CI {stage.value} results of commit {evidence.head_commit[:8] or '(none yet)'}; nothing was scanned"
            )
        return ScanResult(list(pending.findings), dict(pending.versions), set(pending.tools_run),
                          set(pending.components), list(pending.flaky))

    return run


def build_runners(settings: Settings, store) -> dict[StageName, Runner]:
    runners = default_runners(settings)
    if settings.scan_source == "ci":
        runners[StageName.SECURITY] = submitted_runner(store, StageName.SECURITY)
        runners[StageName.QA] = submitted_runner(store, StageName.QA)
    return runners
