"""Run with: uvicorn src.api.main:app   (needs API_TOKEN in .env; phase 11 points GitHub at it)."""

import os

from src.agent.agent import run_loop_with_server
from src.api.app import create_app
from src.github_mcp import McpCommentPoster
from src.github_sync import GitHubPublisher, github_client
from src.history import HistoryLog
from src.scanning import build_runners
from src.service import ReleaseService
from src.settings import get_settings
from src.storage import EvidenceStore


async def _agent(release_id: str, event: str) -> dict:
    from dataclasses import asdict

    return asdict(await run_loop_with_server(release_id, event))


async def template_agent(release_id: str, event: str) -> dict:
    """The no-model mode (AGENT_MODE=template): the explanations come from the fixed template, so a demo costs no tokens
    and cannot hit a rate limit. Scanning and the decision are done by plain code either way."""
    from src.agent.agent import run_with_server
    from src.agent.explain import BackendExplainer, _backend_modules

    explainer = BackendExplainer(_backend_modules()[1].TemplateExplainer())
    explained = 0
    for stage in ("qa", "security"):
        try:
            explained += len((await run_with_server(release_id, stage, explainer))["explained"])
        except Exception:  # that stage has no scan yet
            continue
    return {"stopped": "done", "steps": 0, "tokens": 0, "mode": "template", "calls": [{"tool": "append_evidence"}] * explained}


def build():
    settings = get_settings()
    history = HistoryLog(settings.history_dir)
    store = EvidenceStore(settings.data_dir)
    service = ReleaseService(store, settings.policy_path, build_runners(settings, store), settings.scan_target, history)
    publisher = None
    if os.environ.get("GITHUB_TOKEN"):  # without a token the API still works, it just does not post to GitHub
        publisher = GitHubPublisher(service.store, history, github_client(os.environ["GITHUB_TOKEN"]), McpCommentPoster.from_env())
    runner = template_agent if os.environ.get("AGENT_MODE", "").lower() == "template" else _agent
    return create_app(service, history, runner, publisher)


app = build()
