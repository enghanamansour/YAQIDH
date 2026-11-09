"""Internal MCP server: the only door the agent has into the system. Run with: python -m src.mcp_server

Exactly six tools. There is no tool to set a status, write a closure, record an exception, record a
human decision or merge, because the agent must not be able to do any of those.
"""

import asyncio

from mcp.server.fastmcp import FastMCP

from src.history import HistoryLog
from src.scanning import build_runners
from src.service import ReleaseService
from src.settings import get_settings
from src.storage import EvidenceStore


def create_server(service: ReleaseService) -> FastMCP:
    mcp = FastMCP("yaqidh")

    @mcp.tool()
    async def run_scan(release_id: str, stage: str) -> dict:
        """Run the first scan of a stage ('qa' or 'security'). The system picks the tools and the target."""
        return await asyncio.to_thread(service.run_scan, release_id, stage)

    @mcp.tool()
    async def verify_fix(release_id: str, stage: str) -> dict:
        """Re-scan after the developer's fix. Plain code compares the scans and decides what is closed."""
        return await asyncio.to_thread(service.verify_fix, release_id, stage)

    @mcp.tool()
    def get_findings(release_id: str, stage: str) -> list[dict]:
        """List the findings of a stage."""
        return service.get_findings(release_id, stage)

    @mcp.tool()
    def evaluate_policy(release_id: str, stage: str) -> dict:
        """Ask the policy engine for the pass/fail decision. It is the only source of that decision."""
        return service.evaluate_policy(release_id, stage)

    @mcp.tool()
    def append_evidence(release_id: str, stage: str, fingerprint: str, text: str) -> dict:
        """Attach your explanation text to a finding. It is stored as written by Yaqidh, never as fact."""
        return service.append_evidence(release_id, stage, fingerprint, text)

    @mcp.tool()
    def get_evidence(release_id: str) -> dict:
        """Read the full evidence record of a release."""
        return service.get_evidence(release_id)

    return mcp


def main() -> None:
    settings = get_settings()
    store = EvidenceStore(settings.data_dir)
    service = ReleaseService(store, settings.policy_path, build_runners(settings, store), settings.scan_target,
                             HistoryLog(settings.history_dir))
    create_server(service).run()


if __name__ == "__main__":
    main()
