import json
import shutil
import subprocess
import sys
from pathlib import Path

from src.schema import Finding, Severity
from src.tools.base import ToolError
from src.tools.fingerprint import fingerprint, normalize_snippet

# Our own coarse mapping, not a CVSS score: ERROR and WARNING block, only INFO passes.
# WARNING is reported as "medium", so it is the one that can get an exception (config/policy.yaml).
# Any unknown level is treated as high, so it can never pass silently.
SEVERITY_MAP = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.HIGH,
    "INFO": Severity.LOW,
}
# Semgrep's own level, expressed on the common scale.
REPORTED_AS = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}


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


def _cwe_ids(metadata: dict) -> str:
    """Semgrep gives "CWE-89: Improper Neutralization..." (a string or a list). Keep the ids only."""
    raw = metadata.get("cwe") or []
    items = [raw] if isinstance(raw, str) else raw
    return ", ".join(str(i).split(":")[0].strip() for i in items if i)


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
        rel = rel.as_posix()  # templates/base.html on every system: Windows would give templates\base.html and a different fingerprint
        fp = fingerprint("semgrep", rule, rel, snippet)
        findings[fp] = Finding(
            fingerprint=fp,
            tool="semgrep",
            severity=SEVERITY_MAP.get(result["extra"]["severity"], Severity.HIGH),
            reported_as=REPORTED_AS.get(result["extra"]["severity"], "unknown"),
            location=f"{rel}:{start}",
            rule=rule,
            detail=str(result["extra"].get("message", ""))[:500],
            cwe=_cwe_ids(result["extra"].get("metadata") or {}),
            confidence=str((result["extra"].get("metadata") or {}).get("confidence", "")).lower(),
        )
    # Sorted so the same code always yields the same list, which keeps decisions deterministic.
    return merge_same_line(sorted(findings.values(), key=lambda f: (f.location, f.fingerprint)))


def merge_same_line(findings: list[Finding]) -> list[Finding]:
    """Several rules often flag the same line for the same problem. They become one finding.

    The most severe one is kept (then the first by rule name, so the choice is always the same), and the
    other rules are named in its detail, so nothing is hidden. Merging never lowers a severity.
    """
    groups: dict[str, list[Finding]] = {}
    for f in findings:
        groups.setdefault(f.location, []).append(f)
    merged = []
    for group in groups.values():
        group.sort(key=lambda f: (f.severity != Severity.HIGH, f.rule))
        main, others = group[0], group[1:]
        if others:
            names = ", ".join(sorted({o.rule for o in others if o.rule != main.rule}))
            cwes = sorted({c for f in group for c in f.cwe.split(", ") if c})
            main = main.model_copy(update={
                "detail": (main.detail + f" Also flagged at the same line by: {names}.").strip()[:900],
                "cwe": ", ".join(cwes),
            })
        merged.append(main)
    return sorted(merged, key=lambda f: (f.location, f.fingerprint))


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
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  stdin=subprocess.DEVNULL, timeout=self.timeout)
        except subprocess.TimeoutExpired as e:
            raise ToolError(f"semgrep timed out after {self.timeout}s") from e
        # Exit code 1 only means "findings exist" when --error is set; anything unparsable is a real failure.
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise ToolError(f"semgrep produced no JSON (exit {proc.returncode}): {proc.stderr[:300]}") from e
        return parse_output(data, target)
