"""Policy engine: plain code that decides pass/fail. It never imports from agent/ and never calls an LLM."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.schema import Decision, Finding, FindingStatus, Severity

# Fixed order, so reasons always come out the same way.
SEVERITY_ORDER = [Severity.HIGH, Severity.LOW]


class PolicyError(Exception):
    """The policy file is missing or invalid. Never ignored, because a broken policy must not mean 'pass'."""


class ExceptionRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    require_justification: bool = True
    require_human_approval: bool = True
    # Only findings the tool reported at one of these levels can get an exception. Empty = any level.
    allowed_for: list[str] = Field(default_factory=lambda: ["medium"])


class Policy(BaseModel):
    # Unknown keys are rejected and block_on has no default, so a typo in the file fails loudly
    # instead of silently turning the policy into "block nothing".
    model_config = ConfigDict(extra="forbid")

    block_on: list[Severity]
    exceptions: ExceptionRules = Field(default_factory=ExceptionRules)


def load_policy(path: Path) -> Policy:
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise PolicyError(f"cannot read policy file {path}: {e}") from e
    except yaml.YAMLError as e:
        raise PolicyError(f"policy file {path} is not valid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise PolicyError(f"policy file {path} must contain a mapping")
    try:
        return Policy.model_validate(raw)
    except ValidationError as e:
        raise PolicyError(f"policy file {path} is invalid: {e}") from e


def _still_open(finding: Finding, policy: Policy) -> str | None:
    """None if the finding no longer counts; otherwise a note ('' when it is simply open)."""
    if finding.status == FindingStatus.OPEN:
        return ""
    if finding.status == FindingStatus.FIXED:
        # Fixed only counts when the verifier's re-scan closed it.
        if finding.closure is not None and finding.closure.result == "closed":
            return None
        return f"{finding.fingerprint}: marked fixed without a verified closure"
    exc = finding.exception
    rules = policy.exceptions
    if rules.allowed_for and finding.reported_as not in rules.allowed_for:
        return f"{finding.fingerprint}: exception ignored, not allowed for {finding.reported_as or 'unknown'}"
    if rules.require_justification and not (exc and exc.justification.strip()):
        return f"{finding.fingerprint}: exception ignored, no justification"
    if rules.require_human_approval and not (exc and exc.approved_by.strip()):
        return f"{finding.fingerprint}: exception ignored, no human approval"
    return None


def evaluate_policy(findings: list[Finding], policy: Policy) -> Decision:
    counts: dict[Severity, int] = {s: 0 for s in SEVERITY_ORDER}
    notes: list[str] = []
    for finding in findings:
        note = _still_open(finding, policy)
        if note is None:
            continue
        counts[finding.severity] += 1
        if note and finding.severity in policy.block_on:
            notes.append(note)

    reasons = [f"{counts[s]} {s.value} open" for s in SEVERITY_ORDER if s in policy.block_on and counts[s]]
    blocking = bool(reasons)
    reasons += sorted(notes)
    if not reasons:
        reasons = ["no blocking findings"]
    return Decision(result="fail" if blocking else "pass", reasons=reasons)
