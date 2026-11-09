import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.schema import Finding, Severity
from src.tools.base import ToolError
from src.tools.fingerprint import fingerprint

# Our own coarse mapping, not a CVSS score: only LOW passes. CRITICAL, HIGH, MEDIUM and UNKNOWN
# are all high, and any new level Trivy invents is high too, so it can never pass silently.
# The original level is kept in `reported_as` (medium may get an exception, see config/policy.yaml).
KNOWN_LEVELS = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"}


def _severity(raw: str) -> Severity:
    return Severity.LOW if raw == "LOW" else Severity.HIGH


def _reported_as(raw: str) -> str:
    return raw.lower() if raw in KNOWN_LEVELS else "unknown"


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
            fp = fingerprint("trivy", rule, target, snippet)
            raw = vuln.get("Severity", "")
            findings[fp] = Finding(
                fingerprint=fp,
                tool="trivy",
                severity=_severity(raw),
                reported_as=_reported_as(raw),
                component=snippet,
                location=target,
                rule=rule,
                detail=str(vuln.get("Title", ""))[:500],
                fixed_version=str(vuln.get("FixedVersion", "")),
                cwe=", ".join(vuln.get("CweIDs") or []),
            )
        for secret in result.get("Secrets") or []:
            rule = secret["RuleID"]
            fp = fingerprint("trivy", rule, target, secret.get("Match", ""))
            raw = secret.get("Severity", "")
            findings[fp] = Finding(
                fingerprint=fp,
                tool="trivy",
                severity=_severity(raw),
                reported_as=_reported_as(raw),
                location=f"{target}:{secret['StartLine']}",
                rule=rule,
                detail=str(secret.get("Title", ""))[:500],
            )
    # Sorted so the same input always yields the same list, which keeps decisions deterministic.
    return sorted(findings.values(), key=lambda f: (f.location, f.fingerprint))


def parse_components(data: dict) -> set[str]:
    """Every package Trivy saw, with or without vulnerabilities, as "name==version"."""
    return {
        f"{pkg['Name']}=={pkg['Version']}"
        for result in data.get("Results") or []
        for pkg in result.get("Packages") or []
    }


@dataclass(frozen=True)
class TrivyScan:
    findings: list[Finding]
    components: set[str]  # lets the verifier tell "dependency changed" from "DB got newer"


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

    def scan(self, target: Path) -> TrivyScan:
        target = Path(target)
        if not target.exists():
            raise ToolError(f"target does not exist: {target}")
        self.versions()  # fails early and clearly if the DB is missing
        proc = self._run(
            [
                "fs", "--scanners", "vuln,secret", "--list-all-pkgs",
                "--format", "json", "--quiet", "--skip-db-update", str(target),
            ]
        )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise ToolError(f"trivy produced no JSON (exit {proc.returncode}): {proc.stderr[-300:]}") from e
        return TrivyScan(findings=parse_output(data), components=parse_components(data))

    def run(self, target: Path) -> list[Finding]:
        return self.scan(target).findings
