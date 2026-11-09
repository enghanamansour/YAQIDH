from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StageName(str, Enum):
    QA = "qa"
    SECURITY = "security"


class Severity(str, Enum):
    HIGH = "high"
    LOW = "low"


class FindingStatus(str, Enum):
    OPEN = "open"
    FIXED = "fixed"
    EXCEPTED = "excepted"


class Explanation(BaseModel):
    """AI-written text. The source is fixed to the project name so it can never pass as a verified fact."""

    text: str
    source: Literal["Yaqidh"] = "Yaqidh"


class Closure(BaseModel):
    """Only the verifier (plain code) produces this."""

    verified_by: Literal["rescan"] = "rescan"
    result: Literal["closed", "still_open"]
    timestamp: datetime = Field(default_factory=utcnow)


class ExceptionRecord(BaseModel):
    """Why a finding is allowed to stay open, and who approved it. The policy decides if it is enough."""

    justification: str = ""
    approved_by: str = ""
    timestamp: datetime = Field(default_factory=utcnow)


class Finding(BaseModel):
    fingerprint: str
    tool: str
    severity: Severity
    # The level the tool itself reported, normalized (critical, high, medium, low, info, unknown).
    # `severity` is our two-level result; this keeps the detail, e.g. so only medium can get an exception.
    reported_as: str = ""
    # For dependency findings: the package and version, e.g. "flask==0.12.2". Empty otherwise.
    component: str = ""
    # How the finding first appeared. Set by the verifier; "initial" for the first scan.
    origin: Literal["initial", "new", "new_from_db_update"] = "initial"
    location: str
    status: FindingStatus = FindingStatus.OPEN
    rule: str = ""
    # The tool's own message about the problem (e.g. the failed assertion). Raw tool output, not an AI text.
    detail: str = ""
    # More of the tool's own output, used to explain the finding better. All optional and never part of the fingerprint.
    fixed_version: str = ""  # dependency findings: the first version that fixes it, e.g. "0.12.3"
    cwe: str = ""  # e.g. "CWE-89"
    confidence: str = ""  # how sure the tool is: high, medium or low
    explanation: Explanation | None = None
    closure: Closure | None = None
    exception: ExceptionRecord | None = None


class Decision(BaseModel):
    """Only the policy engine (plain code) produces this."""

    result: Literal["pass", "fail"]
    decided_by: Literal["policy_engine"] = "policy_engine"
    reasons: list[str] = Field(default_factory=list)


class StageRecord(BaseModel):
    name: StageName
    findings: list[Finding] = Field(default_factory=list)
    decision: Decision | None = None
    # Versions of the tools and their data (e.g. trivy, trivy-db), so a scan can be reproduced.
    tool_versions: dict[str, str] = Field(default_factory=dict)
    # Every package the scan saw (e.g. "flask==0.12.2"), so a re-scan can tell a newer DB from a changed dependency.
    components: list[str] = Field(default_factory=list)
    # QA checks that failed on a first try but passed on a retry. Logged here, they are not findings.
    flaky_tests: list[str] = Field(default_factory=list)
    # When the stage was last scanned. A human decision older than this scan does not cover the new results.
    scanned_at: datetime | None = None
    # The commit the last scan was run on. The merge gate only trusts a scan of the commit that is about to merge.
    scanned_commit: str = ""


class HumanDecision(BaseModel):
    stage: StageName
    decision: Literal["approve", "reject"]
    by: str
    reason: str
    timestamp: datetime = Field(default_factory=utcnow)
    # The commit that was current when the person decided.
    commit: str = ""


class Evidence(BaseModel):
    release_id: str
    stages: list[StageRecord] = Field(default_factory=list)
    human_decisions: list[HumanDecision] = Field(default_factory=list)
    # The newest commit of the pull request, as GitHub reported it. Set by the system, never by the agent.
    head_commit: str = ""
    # Which pull request this release is, so results can be posted back to it. Set from the GitHub event.
    repo: str = ""
    pr_number: int = 0

    def stage(self, name: StageName) -> StageRecord:
        """Return the stage record, creating it on first use."""
        for record in self.stages:
            if record.name == name:
                return record
        record = StageRecord(name=name)
        self.stages.append(record)
        return record
