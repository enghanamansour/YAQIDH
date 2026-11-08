"""Data models shared by the whole backend."""
from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Severity = Literal["high", "low"]
Phase = Literal["qa", "security"]

SEVERITY_ORDER = {"high": 0, "low": 1}

# Only these severities stop a merge. Lower ones are recorded and shown, but pass.
BLOCKING = frozenset({"high"})


class Finding(BaseModel):
    """One problem reported by the team's checking tools, in a common shape."""

    rule_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    severity: Severity
    file: str = Field(min_length=1, max_length=500)
    line: int | None = Field(default=None, ge=1)
    description: str = Field(default="", max_length=4000)
    snippet: str = Field(default="", max_length=4000)
    # When the checking tool already gives the finding a stable id, we keep it
    # as the fingerprint instead of making a second one.
    external_id: str | None = Field(default=None, max_length=100)
    # What the tool itself says about the finding. Used to explain it and to tell
    # apart two different problems that happen to sit on the same line.
    cwe: str | None = Field(default=None, max_length=300)
    confidence: Literal["high", "medium", "low"] | None = None

    @field_validator("confidence", mode="before")
    @classmethod
    def _clean_confidence(cls, value):
        if isinstance(value, str) and value.strip().lower() in {"high", "medium", "low"}:
            return value.strip().lower()
        return None  # unknown or missing: we simply do not claim anything

    @field_validator("severity", mode="before")
    @classmethod
    def _only_low_is_low(cls, value):
        """There are only two levels, and only an explicit 'low' is low.

        'critical', 'medium', 'info' and any unknown name count as high, so a
        label we did not expect can never let a finding slip through.
        """
        if isinstance(value, str) and value.strip().lower() == "low":
            return "low"
        return "high"

    @property
    def fingerprint(self) -> str:
        """Stable id for a vulnerability.

        It ignores the line number on purpose, so moving code around does not
        make an old problem look new, and a fixed problem really disappears.
        """
        if self.external_id:
            return self.external_id
        body = re.sub(r"\s+", " ", self.snippet or self.title).strip().lower()
        raw = "|".join([self.rule_id.strip().lower(), self.file.strip(), body])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class Scan(BaseModel):
    """The full result of one checking run on one pull request."""

    repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$")
    pr: int = Field(ge=1)
    commit: str = Field(min_length=7, max_length=64, pattern=r"^[0-9a-fA-F]+$")
    phase: Phase
    findings: list[Finding] = Field(default_factory=list, max_length=2000)
    lang: Literal["ar", "en"] = "ar"
    # Post the comment and the status on GitHub. Off unless asked, and it needs GITHUB_TOKEN.
    publish: bool = False


class Explanation(BaseModel):
    """What the agent says about a finding. Words only, never code."""

    problem: str = Field(min_length=1, max_length=800)
    why_dangerous: str = Field(min_length=1, max_length=800)
    direction: str = Field(min_length=1, max_length=800)
