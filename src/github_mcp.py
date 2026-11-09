"""Writes the pull request comment through the GitHub MCP server (an external MCP server, run by GitHub).

Uses its tools issue_read (method get_comments), add_issue_comment and update_issue_comment. The comment text is built by
our own code from the evidence (github_sync.render_comment): the model never writes a free-form GitHub message.
That server has no tool for commit statuses, so statuses still go through the direct API client.
NOT tested against the real GitHub MCP server yet, only against a stand-in with the same tool names.
"""

import asyncio
import json
import os
import shlex
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DEFAULT_COMMAND = "docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server"


def marker(phase: str) -> str:
    return f"<!-- yaqidh:{phase} -->"


class McpCommentPoster:
    def __init__(self, params: StdioServerParameters | None = None, opener=None):
        self._params = params
        self._opener = opener  # tests give a session that is already connected

    @classmethod
    def from_env(cls) -> "McpCommentPoster | None":
        """Configured when GITHUB_TOKEN is set and GITHUB_MCP=1 (command in GITHUB_MCP_COMMAND, else the docker image)."""
        token = os.environ.get("GITHUB_TOKEN")
        if not token or os.environ.get("GITHUB_MCP") != "1":
            return None
        parts = shlex.split(os.environ.get("GITHUB_MCP_COMMAND", DEFAULT_COMMAND))
        env = {**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": token}
        return cls(StdioServerParameters(command=parts[0], args=parts[1:], env=env))

    @asynccontextmanager
    async def _session(self):
        if self._opener is not None:
            async with self._opener() as session:
                yield session
            return
        async with stdio_client(self._params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    @staticmethod
    def _comments(result) -> list[dict]:
        text = result.content[0].text if result.content else "[]"
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):  # some versions wrap the list
            data = next((v for v in data.values() if isinstance(v, list)), [])
        return [c for c in data if isinstance(c, dict)]

    async def _upsert(self, repo: str, pr: int, phase: str, body: str) -> dict:
        owner, name = repo.split("/", 1)
        text = f"{marker(phase)}\n{body}"
        async with self._session() as session:
            listed = await session.call_tool("issue_read", {"method": "get_comments", "owner": owner, "repo": name,
                                                            "issue_number": pr, "perPage": 100})
            mine = next((c for c in self._comments(listed) if marker(phase) in (c.get("body") or "")), None)
            if mine is not None:
                res = await session.call_tool("update_issue_comment", {"owner": owner, "repo": name,
                                                                       "comment_id": int(mine["id"]), "body": text})
                action = "updated"
            else:
                res = await session.call_tool("add_issue_comment", {"owner": owner, "repo": name,
                                                                    "issue_number": pr, "body": text})
                action = "created"
            if res.isError:
                raise RuntimeError(res.content[0].text if res.content else "the GitHub MCP server refused the comment")
        return {"action": action, "via": "github-mcp"}

    def upsert_comment(self, repo: str, pr: int, phase: str, body: str) -> dict:
        """Same shape as the direct client, so the publisher can use either. Call it from a thread, not the event loop."""
        return asyncio.run(self._upsert(repo, pr, phase, body))
