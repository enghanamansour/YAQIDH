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


class HumanDecision(BaseModel):
    stage: StageName
    decision: Literal["approve", "reject"]
    by: str
    reason: str
    timestamp: datetime = Field(default_factory=utcnow)


class ReviewRequestDecision(BaseModel):
    request_id: str
    commit: str
    finding: str
    kind: Literal["exception", "deadline"]
    status: Literal["approved", "rejected"]
    by: str
    reason: str
    original: str | None = None
    requested: str | None = None
    approved_deadline: str | None = None
    timestamp: datetime = Field(default_factory=utcnow)


class Evidence(BaseModel):
    release_id: str
    stages: list[StageRecord] = Field(default_factory=list)
    human_decisions: list[HumanDecision] = Field(default_factory=list)
    review_request_decisions: list[ReviewRequestDecision] = Field(default_factory=list)

    def stage(self, name: StageName) -> StageRecord:
        """Return the stage record, creating it on first use."""
        for record in self.stages:
            if record.name == name:
                return record
        record = StageRecord(name=name)
        self.stages.append(record)
        return record
