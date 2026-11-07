import json
import shutil
import subprocess
import sys
from pathlib import Path

from src.schema import Finding, Severity
from src.tools.base import ToolError
from src.tools.finding_id import finding_id, normalize_snippet

# Our own coarse mapping, not a CVSS score: ERROR blocks, WARNING and INFO pass.
# Any unknown level is treated as high, so it can never pass silently.
SEVERITY_MAP = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.LOW,
    "INFO": Severity.LOW,
}


def _read_snippet(file: Path, start: int, end: int) -> str:
    # Semgrep prints "requires login" in extra.lines when not logged in, so read the source ourselves.
    try:
        lines = file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    return normalize_snippet(" ".join(lines[start - 1 : end]))


def _rule_id(check_id: str) -> str:
    """Semgrep prefixes check_id with the folder the rules were loaded from, which depends on
    where they are stored. Official ids start at "python.", so cut everything before that."""
    parts = check_id.split(".")
    if "python" in parts:
        return ".".join(parts[parts.index("python") :])
    return parts[-1]


def parse_output(data: dict, target: Path) -> list[Finding]:
    """Turn Semgrep's JSON into Findings. Pure function, so it is testable without running Semgrep."""
    if data.get("errors"):
        raise ToolError(f"semgrep reported errors: {data['errors'][0].get('message', data['errors'][0])}")

    findings: dict[str, Finding] = {}
    for result in data.get("results", []):
        rule = _rule_id(result["check_id"])
        path = Path(result["path"])
        start, end = result["start"]["line"], result["end"]["line"]
        snippet = _read_snippet(path, start, end)
        try:
            rel = path.relative_to(target)
        except ValueError:
            rel = path
        fid = finding_id("semgrep", rule, str(rel), snippet)
        findings[fid] = Finding(
            id=fid,
            tool="semgrep",
            severity=SEVERITY_MAP.get(result["extra"]["severity"], Severity.HIGH),
            location=f"{rel}:{start}",
            rule=rule,
        )
    # Sorted so the same code always yields the same list, which keeps decisions deterministic.
    return sorted(findings.values(), key=lambda f: (f.location, f.id))


class SemgrepTool:
    name = "semgrep"

    def __init__(self, rules_dir: Path, timeout: int = 300):
        """rules_dir is the folder made by scripts/fetch_semgrep_rules.sh (official rules, pinned commit)."""
        self.rules_dir = Path(rules_dir)
        self.rules_path = self.rules_dir / "python"
        self.timeout = timeout

    def rules_version(self) -> str:
        """The pinned commit of the official rules; goes into the evidence so a scan can be reproduced."""
        try:
            return (self.rules_dir / "VERSION").read_text(encoding="utf-8").strip()
        except OSError:
            return "unknown"

    def run(self, target: Path) -> list[Finding]:
        target = Path(target)
        if not target.exists():
            raise ToolError(f"target does not exist: {target}")
        if not self.rules_path.is_dir():
            raise ToolError("Semgrep rules not found, run scripts/fetch_semgrep_rules.sh")
        # Look next to the running Python first, so it works without activating the venv.
        sibling = Path(sys.executable).parent / "semgrep"
        exe = str(sibling) if sibling.exists() else shutil.which("semgrep")
        if exe is None:
            raise ToolError("semgrep is not installed (uv pip install semgrep)")
        cmd = [exe, "--json", "--quiet", "--metrics=off", "--config", str(self.rules_path), str(target)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired as e:
            raise ToolError(f"semgrep timed out after {self.timeout}s") from e
        # Exit code 1 only means "findings exist" when --error is set; anything unparsable is a real failure.
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise ToolError(f"semgrep produced no JSON (exit {proc.returncode}): {proc.stderr[:300]}") from e
        return parse_output(data, target)
