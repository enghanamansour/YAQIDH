"""The HTTP API: the one door for the dashboard and for GitHub. FastAPI, plain code.

Reading is open to any caller with the token. Writes are split: the agent never uses this API (it has its
own MCP tools); people write decisions here, and GitHub events start the agent. Nothing here lets a caller
set a status, close a finding or open a gate directly: those come from the evidence only.
"""

import asyncio
import hashlib
import hmac
import json
import os
from collections import Counter
from typing import Awaitable, Callable, Literal

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from src.gate import check_gate
from src.github_sync import release_id_for
from src.history import HistoryLog
from src.schema import Finding
from src.tools.base import ToolError
from src.verifier import VerifierError
from src.phases.workflow import Workflow, WorkflowError
from src.schema import StageName
from src.service import ReleaseService, ServiceError
from src.storage import ReleaseNotFound

AgentRunner = Callable[[str, str], Awaitable[dict]]


class EventIn(BaseModel):
    event: Literal["pull_request_opened", "push"]
    commit: str = Field(min_length=4, max_length=64)


class DecisionIn(BaseModel):
    by: str = Field(min_length=1, max_length=100)
    reason: str = Field(default="", max_length=2000)


class ExceptionIn(BaseModel):
    fingerprint: str = Field(min_length=1, max_length=64)
    justification: str = Field(min_length=1, max_length=2000)
    approved_by: str = Field(min_length=1, max_length=100)


class ScanSubmission(BaseModel):
    """Security results a CI job sends: findings already fingerprinted by our own tools, plus what ran and which versions."""

    commit: str = Field(min_length=4, max_length=64)
    findings: list[Finding]
    versions: dict[str, str]
    tools_run: list[str]
    components: list[str] = []


def require_token(x_api_token: str | None = Header(default=None)) -> None:
    """Fail closed: with no API_TOKEN configured, nothing is allowed."""
    expected = os.environ.get("API_TOKEN")
    if not expected:
        raise HTTPException(503, "API_TOKEN is not configured")
    if not x_api_token or not hmac.compare_digest(x_api_token, expected):
        raise HTTPException(401, "invalid token")


def create_app(
    service: ReleaseService, history: HistoryLog, agent_runner: AgentRunner | None = None, publisher=None
) -> FastAPI:
    app = FastAPI(title="Yaqidh API", version="0.2.0")
    workflow = Workflow(service)
    running: set[str] = set()  # releases whose agent is working right now
    rerun: set[str] = set()  # a newer event arrived while the agent was working

    def release_or_404(release_id: str):
        try:
            return service.store.get(release_id)
        except ReleaseNotFound:
            raise HTTPException(404, f"no release {release_id}")
        except ValueError as e:
            raise HTTPException(422, str(e))

    async def publish(release_id: str) -> None:
        """Tell GitHub the new state (comment + statuses). Failures are logged by the publisher, never raised."""
        if publisher is not None:
            await asyncio.to_thread(publisher.publish, release_id)

    async def run_agent(release_id: str, event: str) -> None:
        if agent_runner is None:
            await publish(release_id)
            return
        if release_id in running:
            rerun.add(release_id)
            return
        running.add(release_id)
        try:
            while True:
                rerun.discard(release_id)
                try:
                    result = await agent_runner(release_id, event)
                    summary = {"stopped": result.get("stopped"), "steps": result.get("steps"),
                               "tools": dict(Counter(c["tool"] for c in result.get("calls", [])))}
                except Exception as e:  # a failing agent must never take the API down
                    summary = {"stopped": "error", "error": str(e)[:300]}
                history.append(release_id, "agent_run", "agent", {"event": event, **summary})
                if release_id not in rerun:
                    break
                event = "push"
        finally:
            running.discard(release_id)
        await publish(release_id)

    auth = [Depends(require_token)]

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    # --- GitHub events start the agent ---
    @app.post("/releases/{release_id}/events", status_code=202, dependencies=auth)
    def receive_event(release_id: str, body: EventIn, background: BackgroundTasks) -> dict:
        try:
            out = service.set_head_commit(release_id, body.commit)
        except (ServiceError, ValueError) as e:
            raise HTTPException(422, str(e))
        history.append(release_id, "event", "github", {"event": body.event, "commit": body.commit})
        background.add_task(run_agent, release_id, body.event)
        return {"accepted": True, **out, "agent_busy": release_id in running}

    # --- a CI job sends the security scan of the pull request's code ---
    @app.post("/releases/{release_id}/scan-results", status_code=202, dependencies=auth)
    def receive_scan_results(release_id: str, body: ScanSubmission, background: BackgroundTasks) -> dict:
        try:
            out = service.submit_scan_results(release_id, body.commit, body.findings, body.versions, body.tools_run, body.components)
        except ServiceError as e:
            raise HTTPException(409, str(e))
        except ValueError as e:
            raise HTTPException(422, str(e))
        applied, error = False, None
        try:  # if it is security's turn the results are used at once, otherwise they wait for it
            workflow.apply_security_results(release_id)
            applied = service.store.get(release_id).stage(StageName.SECURITY).scanned_commit == body.commit
        except (ServiceError, VerifierError, ToolError) as e:
            error = str(e)[:300]
            history.append(release_id, "scan_results_not_applied", "system", {"error": error})
        background.add_task(run_agent, release_id, "scan_results")
        return {"accepted": True, **out, "applied": applied, "error": error}

    # --- reading, for the dashboard ---
    @app.get("/releases", dependencies=auth)
    def list_releases() -> list[dict]:
        out = []
        for path in sorted(service.store.data_dir.glob("*.json")):
            e = service.store.get(path.stem)
            report = workflow.status(e.release_id)
            out.append({"release_id": e.release_id, "status": report.status.value, "head_commit": e.head_commit})
        return out

    @app.get("/releases/{release_id}", dependencies=auth)
    def get_release(release_id: str) -> dict:
        evidence = release_or_404(release_id)
        return {"evidence": evidence.model_dump(mode="json"), "status": workflow.status(release_id).model_dump(mode="json")}

    @app.get("/releases/{release_id}/status", dependencies=auth)
    def get_status(release_id: str) -> dict:
        release_or_404(release_id)
        return workflow.status(release_id).model_dump(mode="json")

    @app.get("/releases/{release_id}/findings", dependencies=auth)
    def get_findings(release_id: str, stage: Literal["qa", "security"]) -> list[dict]:
        release_or_404(release_id)
        return service.get_findings(release_id, stage)

    @app.get("/releases/{release_id}/history", dependencies=auth)
    def get_history(release_id: str) -> list[dict]:
        release_or_404(release_id)
        return history.entries(release_id)

    @app.get("/releases/{release_id}/history/verify", dependencies=auth)
    def verify_history(release_id: str) -> dict:
        release_or_404(release_id)
        return history.verify(release_id)

    # --- people decide ---
    def human(action: Callable[[], object]) -> dict:
        try:
            report = action()
        except (WorkflowError, ServiceError) as e:
            raise HTTPException(409, str(e))
        except ReleaseNotFound as e:
            raise HTTPException(404, f"no release {e}")
        except ValueError as e:
            raise HTTPException(422, str(e))
        return report.model_dump(mode="json")

    @app.post("/releases/{release_id}/stages/{stage}/approve", dependencies=auth)
    def approve(release_id: str, stage: Literal["qa", "security"], body: DecisionIn, background: BackgroundTasks) -> dict:
        out = human(lambda: workflow.approve(release_id, stage, body.by, body.reason))
        background.add_task(run_agent, release_id, "approved")  # explain what the next stage found
        return out

    @app.post("/releases/{release_id}/stages/{stage}/reject", dependencies=auth)
    def reject(release_id: str, stage: Literal["qa", "security"], body: DecisionIn, background: BackgroundTasks) -> dict:
        out = human(lambda: workflow.reject(release_id, stage, body.by, body.reason))
        background.add_task(publish, release_id)
        return out

    @app.post("/releases/{release_id}/stages/{stage}/exceptions", dependencies=auth)
    def grant_exception(release_id: str, stage: Literal["qa", "security"], body: ExceptionIn, background: BackgroundTasks) -> dict:
        out = human(lambda: workflow.grant_exception(release_id, stage, body.fingerprint, body.justification, body.approved_by))
        background.add_task(publish, release_id)
        return out

    # --- GitHub calls this when a pull request is opened or gets new commits ---
    @app.post("/github/webhook")
    async def github_webhook(
        request: Request,
        background: BackgroundTasks,
        x_hub_signature_256: str | None = Header(default=None),
        x_github_event: str | None = Header(default=None),
    ) -> dict:
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
        if not secret:
            raise HTTPException(503, "GITHUB_WEBHOOK_SECRET is not configured")
        raw = await request.body()
        expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if not x_hub_signature_256 or not hmac.compare_digest(x_hub_signature_256, expected):
            raise HTTPException(401, "invalid signature")  # only GitHub, holding the secret, can start the agent
        if x_github_event == "ping":
            return {"pong": True}
        if x_github_event != "pull_request":
            return {"ignored": x_github_event}
        try:
            payload = json.loads(raw)
            action = payload["action"]
            repo = payload["repository"]["full_name"]
            number = int(payload["number"])
            sha = payload["pull_request"]["head"]["sha"]
            author = str((payload["pull_request"].get("user") or {}).get("login", ""))
            branch = str(payload["pull_request"]["head"].get("ref", ""))
        except (ValueError, KeyError, TypeError):
            raise HTTPException(422, "not a pull_request event we understand")
        if action not in ("opened", "reopened", "synchronize"):
            return {"ignored": f"pull_request.{action}"}
        release_id = release_id_for(repo, number)
        event = "pull_request_opened" if action in ("opened", "reopened") else "push"
        try:
            service.set_pull_request(release_id, repo, number, author, branch)
            service.set_head_commit(release_id, sha)
        except (ServiceError, ValueError) as e:
            raise HTTPException(422, str(e))
        history.append(release_id, "event", "github", {"event": event, "commit": sha, "action": action})
        background.add_task(run_agent, release_id, event)
        return {"accepted": True, "release_id": release_id, "event": event}

    # --- GitHub asks if a commit may merge ---
    @app.get("/gate", dependencies=auth)
    def gate(release_id: str, commit: str, target: Literal["staging", "main"]) -> dict:
        try:
            evidence = service.store.get(release_id)
        except ReleaseNotFound:
            evidence = None
        except ValueError as e:
            raise HTTPException(422, str(e))
        result = check_gate(evidence, commit, target)
        if evidence is not None:
            history.append(release_id, "gate_checked", "github", {"commit": commit, "target": target,
                                                                   "allowed": result.allowed, "reason": result.reason})
        return result.model_dump()

    return app
