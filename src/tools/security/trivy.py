import json
import shutil
import subprocess
from pathlib import Path

from src.schema import Finding, Severity
from src.tools.base import ToolError
from src.tools.finding_id import finding_id

# Our own coarse mapping, not a CVSS score: CRITICAL and HIGH block, MEDIUM and LOW pass.
# Any unknown level (e.g. UNKNOWN) is treated as high, so it can never pass silently.
SEVERITY_MAP = {
    "CRITICAL": Severity.HIGH,
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.LOW,
    "LOW": Severity.LOW,
}


def _severity(raw: str) -> Severity:
    return SEVERITY_MAP.get(raw, Severity.HIGH)


def parse_output(data: dict) -> list[Finding]:
    """Turn Trivy's JSON into Findings. Pure function, so it is testable without running Trivy.

    Vulnerabilities: the rule is the CVE id and the snippet is "package==version", so the
    finding stays the same across scans and a bumped version gives a different one.
    Secrets: Trivy masks the secret value itself, and we only ever use that masked text.
    """
    findings: dict[str, Finding] = {}
    for result in data.get("Results") or []:
        target = result["Target"]
        for vuln in result.get("Vulnerabilities") or []:
            rule = vuln["VulnerabilityID"]
            snippet = f"{vuln['PkgName']}=={vuln['InstalledVersion']}"
            fid = finding_id("trivy", rule, target, snippet)
            findings[fid] = Finding(
                id=fid, tool="trivy", severity=_severity(vuln.get("Severity", "")), location=target, rule=rule
            )
        for secret in result.get("Secrets") or []:
            rule = secret["RuleID"]
            fid = finding_id("trivy", rule, target, secret.get("Match", ""))
            findings[fid] = Finding(
                id=fid,
                tool="trivy",
                severity=_severity(secret.get("Severity", "")),
                location=f"{target}:{secret['StartLine']}",
                rule=rule,
            )
    # Sorted so the same input always yields the same list, which keeps decisions deterministic.
    return sorted(findings.values(), key=lambda f: (f.location, f.id))


class TrivyTool:
    """Scans dependencies (requirements files) and hardcoded secrets.

    Scanning never updates the vulnerability DB: that is a separate, explicit step
    (update_db), so the same code plus the same DB always gives the same findings.
    """

    name = "trivy"

    def __init__(self, timeout: int = 300):
        self.timeout = timeout

    def _exe(self) -> str:
        exe = shutil.which("trivy")
        if exe is None:
            raise ToolError("trivy is not installed (brew install trivy)")
        return exe

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        try:
            return subprocess.run([self._exe(), *args], capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired as e:
            raise ToolError(f"trivy timed out after {self.timeout}s") from e

    def update_db(self) -> None:
        """Explicit step, run by code or CI before scanning. The agent never calls this."""
        proc = self._run(["fs", "--download-db-only", "--quiet"])
        if proc.returncode != 0:
            raise ToolError(f"trivy DB update failed: {proc.stderr[-300:]}")

    def versions(self) -> dict[str, str]:
        """Trivy version and the DB snapshot used, for the evidence. Raises if there is no DB."""
        proc = self._run(["version", "--format", "json"])
        try:
            info = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise ToolError(f"cannot read trivy version: {proc.stderr[:300]}") from e
        db = info.get("VulnerabilityDB")
        if not db:
            raise ToolError("trivy vulnerability DB not found, run TrivyTool().update_db()")
        return {"trivy": info["Version"], "trivy-db": db["UpdatedAt"]}

    def run(self, target: Path) -> list[Finding]:
        target = Path(target)
        if not target.exists():
            raise ToolError(f"target does not exist: {target}")
        self.versions()  # fails early and clearly if the DB is missing
        proc = self._run(
            ["fs", "--scanners", "vuln,secret", "--format", "json", "--quiet", "--skip-db-update", str(target)]
        )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise ToolError(f"trivy produced no JSON (exit {proc.returncode}): {proc.stderr[-300:]}") from e
        return parse_output(data)
