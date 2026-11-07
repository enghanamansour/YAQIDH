"""HTTP API of the agent backend.

POST /scans    a checking run finished: record it, explain what is open, build the PR comment
GET  /gate     may this commit merge? (fixed rule, no language model involved)
GET  /evidence the evidence log of a pull request
GET  /evidence/verify  is the chain of the log intact?
"""
from __future__ import annotations

import hmac
import os
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from . import comment, config
from .evidence import EvidenceLog
from .explainer import Explainer, explain_group, get_explainer
from .gate import Gate
from .github import GitHubClient, GitHubError
from .grouping import group_findings
from .models import BLOCKING, Phase, Scan

config.load_env()  # keys come from the local .env file (never committed)

app = FastAPI(title="Yaqidh agent backend", version="0.1.0")


@lru_cache
def get_evidence() -> EvidenceLog:
    return EvidenceLog(os.environ.get("EVIDENCE_PATH", "data/evidence.jsonl"))


@lru_cache
def get_gate() -> Gate:
    return Gate(get_evidence())


@lru_cache
def get_agent() -> Explainer:
    return get_explainer()


@lru_cache
def get_github() -> GitHubClient | None:
    token = os.environ.get("GITHUB_TOKEN")
    return GitHubClient(token) if token else None


def require_token(x_api_token: str | None = Header(default=None)) -> None:
    """Fail closed: with no API_TOKEN configured, nothing is allowed."""
    expected = os.environ.get("API_TOKEN")
    if not expected:
        raise HTTPException(503, "API_TOKEN is not configured")
    if not x_api_token or not hmac.compare_digest(x_api_token, expected):
        raise HTTPException(401, "invalid token")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/scans", dependencies=[Depends(require_token)])
def record_scan(
    scan: Scan,
    gate: Gate = Depends(get_gate),
    agent: Explainer = Depends(get_agent),
    log: EvidenceLog = Depends(get_evidence),
    github: GitHubClient | None = Depends(get_github),
) -> dict:
    result = gate.record_scan(scan)
    groups = group_findings(result.all_open)
    items = [(g, explain_group(agent, g, scan.lang)) for g in groups]
    decision = gate.check(scan.repo, scan.pr, scan.phase, scan.commit)
    body = comment.render(scan.phase, items, result.closed, scan.lang)

    published = None
    if scan.publish:
        published = _publish(github, scan, decision, body, log)

    return {
        "allowed": decision.allowed,
        "reason": decision.reason,
        "blocking_count": decision.open_count,
        "low_count": decision.low_open,
        "open": [
            {
                "fingerprints": g.fingerprints,
                "rules": g.rules,
                "severity": g.severity,
                "title": g.representative.title,
                "blocking": g.severity in BLOCKING,
                "low_confidence": g.low_confidence,
                "explanation": e.model_dump(),
            }
            for g, e in items
        ],
        "closed": result.closed,
        "comment": body,
        "github": published,
    }


def _publish(github: GitHubClient | None, scan: Scan, decision, body: str, log: EvidenceLog) -> dict:
    """Posts to GitHub. Any failure is reported here and never changes the decision."""
    if github is None:
        return {"error": "GITHUB_TOKEN is not configured"}
    out: dict = {}
    try:
        out["comment"] = github.upsert_comment(scan.repo, scan.pr, scan.phase, body)
    except GitHubError as e:
        out["comment_error"] = str(e)
    try:
        note = "no blocking findings" if decision.allowed else f"{decision.open_count} blocking finding(s) open"
        out["status"] = github.set_status(scan.repo, scan.commit, scan.phase, allowed=decision.allowed, description=note)
    except GitHubError as e:
        out["status_error"] = str(e)
    log.append(repo=scan.repo, pr=scan.pr, commit=scan.commit, phase=scan.phase, event="published", data=out)
    return out


@app.get("/gate", dependencies=[Depends(require_token)])
def gate_status(
    repo: str = Query(pattern=r"^[\w.-]+/[\w.-]+$"),
    pr: int = Query(ge=1),
    phase: Phase = Query(),
    commit: str = Query(min_length=7, max_length=64, pattern=r"^[0-9a-fA-F]+$"),
    gate: Gate = Depends(get_gate),
) -> dict:
    d = gate.check(repo, pr, phase, commit)
    return {"allowed": d.allowed, "reason": d.reason, "open_count": d.open_count, "low_open": d.low_open}


@app.get("/evidence", dependencies=[Depends(require_token)])
def evidence(repo: str | None = None, pr: int | None = None, log: EvidenceLog = Depends(get_evidence)) -> dict:
    return {"entries": log.entries(repo, pr)}


@app.get("/evidence/verify", dependencies=[Depends(require_token)])
def evidence_verify(log: EvidenceLog = Depends(get_evidence)) -> dict:
    return log.verify()
