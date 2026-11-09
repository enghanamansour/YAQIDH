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


def build():
    settings = get_settings()
    history = HistoryLog(settings.history_dir)
    store = EvidenceStore(settings.data_dir)
    service = ReleaseService(store, settings.policy_path, build_runners(settings, store), settings.scan_target, history)
    publisher = None
    if os.environ.get("GITHUB_TOKEN"):  # without a token the API still works, it just does not post to GitHub
        publisher = GitHubPublisher(service.store, history, github_client(os.environ["GITHUB_TOKEN"]), McpCommentPoster.from_env())
    return create_app(service, history, _agent, publisher)


app = build()
