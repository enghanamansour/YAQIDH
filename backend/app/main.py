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

from . import comment
from .evidence import EvidenceLog
from .explainer import Explainer, get_explainer
from .gate import Gate
from .models import BLOCKING, Phase, Scan

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
def record_scan(scan: Scan, gate: Gate = Depends(get_gate), agent: Explainer = Depends(get_agent)) -> dict:
    result = gate.record_scan(scan)
    items = [(f, agent.explain(f, scan.lang)) for f in result.all_open]
    decision = gate.check(scan.repo, scan.pr, scan.phase, scan.commit)
    return {
        "allowed": decision.allowed,
        "reason": decision.reason,
        "blocking_count": decision.open_count,
        "low_count": decision.low_open,
        "open": [
            {"fingerprint": f.fingerprint, "severity": f.severity, "title": f.title,
             "blocking": f.severity in BLOCKING, "explanation": e.model_dump()}
            for f, e in items
        ],
        "closed": result.closed,
        "comment": comment.render(scan.phase, items, result.closed, scan.lang),
    }


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
