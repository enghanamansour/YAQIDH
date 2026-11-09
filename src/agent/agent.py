"""The agent: an MCP client that explains findings. It explains; it never decides, fixes or merges.

The agent does not choose its own tools. Plain code runs a fixed loop and the agent can only call the
two tools below, so even a misbehaving model has no way to change a status, a decision or a merge.
The model itself only writes the explanation text.
"""

import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.agent.explain import BackendExplainer

ALLOWED_TOOLS = frozenset({"get_findings", "append_evidence"})
ROOT = Path(__file__).resolve().parents[2]


class ToolNotAllowed(Exception):
    pass


class ToolBox:
    """The only way the agent talks to the system. Anything outside ALLOWED_TOOLS is refused."""

    def __init__(self, session: ClientSession):
        self._session = session

    async def call(self, name: str, **args):
        if name not in ALLOWED_TOOLS:
            raise ToolNotAllowed(f"the agent may not call '{name}'")
        result = await self._session.call_tool(name, args)
        text = result.content[0].text if result.content else ""
        if result.isError:
            raise RuntimeError(text)
        data = result.structuredContent
        if data is not None:  # a list comes back as {"result": [...]}
            return data["result"] if set(data) == {"result"} else data
        return json.loads(text) if text else None


class Agent:
    def __init__(self, tools: ToolBox, explainer):
        self.tools = tools
        self.explainer = explainer

    async def explain_stage(self, release_id: str, stage: str) -> dict:
        """Explains every open finding that has no explanation yet. The same fingerprint is never explained twice."""
        findings = await self.tools.call("get_findings", release_id=release_id, stage=stage)
        done, reused, failed = [], [], []
        for f in findings:
            if f["status"] != "open":
                continue
            if f.get("explanation"):
                reused.append(f["fingerprint"])
                continue
            try:
                text = self.explainer.explain(f)
                await self.tools.call(
                    "append_evidence", release_id=release_id, stage=stage, fingerprint=f["fingerprint"], text=text
                )
                done.append(f["fingerprint"])
            except Exception as e:  # one bad finding must not stop the others
                failed.append({"fingerprint": f["fingerprint"], "error": str(e)})
        return {"explained": done, "reused": reused, "failed": failed}


async def run_with_server(release_id: str, stage: str, explainer=None) -> dict:
    """Starts the internal MCP server as a child process and runs the agent against it."""
    params = StdioServerParameters(command=sys.executable, args=["-m", "src.mcp_server"], cwd=ROOT, env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await Agent(ToolBox(session), explainer or BackendExplainer()).explain_stage(release_id, stage)


async def run_loop_with_server(release_id: str, event: str = "pull_request_opened", chat=None):
    """The real agent: starts the internal MCP server and lets the model drive the tools (see loop.py)."""
    from src.agent.loop import AgentLoop, ChatClient

    params = StdioServerParameters(command=sys.executable, args=["-m", "src.mcp_server"], cwd=ROOT, env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await AgentLoop(session, chat or ChatClient()).run(release_id, event)
