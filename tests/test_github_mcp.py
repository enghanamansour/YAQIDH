import json
from contextlib import asynccontextmanager

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session as connect

from src.agent.loop import AgentLoop
from src.github_mcp import McpCommentPoster
from src.github_sync import GitHubPublisher, post_release_comment
from tests.test_github_sync import FakeGitHub, evidence_with_findings
from tests.test_loop import ScriptedChat, call, say, skills  # noqa: F401
from tests.test_loop import anyio_backend, service  # noqa: F401
from tests.test_http_api import Stack

pytestmark = pytest.mark.anyio


class FakeGitHubMcp:
    """A stand-in with the same tool names as the official GitHub MCP server."""

    def __init__(self, fail=False):
        self.comments, self.calls, self.fail = [], [], fail
        mcp = FastMCP("github")

        @mcp.tool()
        def issue_read(method: str, owner: str, repo: str, issue_number: int, perPage: int = 30) -> str:
            self.calls.append(("issue_read", method))
            return json.dumps(self.comments)

        @mcp.tool()
        def add_issue_comment(owner: str, repo: str, issue_number: int, body: str) -> str:
            self.calls.append(("add_issue_comment", issue_number))
            if self.fail:
                raise RuntimeError("not allowed")
            self.comments.append({"id": 41 + len(self.comments), "body": body})
            return "ok"

        @mcp.tool()
        def update_issue_comment(owner: str, repo: str, comment_id: int, body: str) -> str:
            self.calls.append(("update_issue_comment", comment_id))
            next(c for c in self.comments if c["id"] == comment_id)["body"] = body
            return "ok"

        self.server = mcp

    def poster(self):
        @asynccontextmanager
        async def opener():
            async with connect(self.server) as session:
                yield session
        return McpCommentPoster(opener=opener)


async def test_the_comment_is_created_once_then_updated_in_place():
    import asyncio

    gh = FakeGitHubMcp()
    poster = gh.poster()
    first = await poster._upsert("o/n", 7, "release", "first")
    second = await poster._upsert("o/n", 7, "release", "second")
    assert (first["action"], second["action"]) == ("created", "updated")
    assert len(gh.comments) == 1 and "second" in gh.comments[0]["body"] and "<!-- yaqidh:release -->" in gh.comments[0]["body"]
    assert [c[0] for c in gh.calls] == ["issue_read", "add_issue_comment", "issue_read", "update_issue_comment"]


async def test_a_refused_comment_raises_instead_of_pretending():
    with pytest.raises(Exception):
        await FakeGitHubMcp(fail=True).poster()._upsert("o/n", 7, "release", "x")


async def test_another_persons_comment_is_never_touched():
    gh = FakeGitHubMcp()
    gh.comments.append({"id": 1, "body": "looks good to me"})
    await gh.poster()._upsert("o/n", 7, "release", "ours")
    assert gh.comments[0]["body"] == "looks good to me" and len(gh.comments) == 2


def test_the_publisher_posts_the_comment_through_mcp_and_the_statuses_directly(tmp_path):
    import asyncio

    stack = Stack(tmp_path)
    stack.service.store.save(evidence_with_findings())
    gh = FakeGitHubMcp()
    direct = FakeGitHub()
    poster = gh.poster()
    poster.upsert_comment = lambda repo, pr, phase, body: asyncio.run(poster._upsert(repo, pr, phase, body))
    GitHubPublisher(stack.service.store, stack.history, direct, poster).publish("r1")
    assert gh.comments and not direct.comments  # the comment went through MCP, not the direct client
    assert {s[2] for s in direct.statuses} == {"staging", "main"}  # statuses: the MCP server has no such tool


def test_without_the_mcp_settings_no_mcp_poster_is_made(monkeypatch):
    monkeypatch.delenv("GITHUB_MCP", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    assert McpCommentPoster.from_env() is None
    monkeypatch.setenv("GITHUB_MCP", "1")
    assert McpCommentPoster.from_env() is not None


async def test_the_agent_can_ask_for_the_comment_but_cannot_write_its_text(service, skills):  # noqa: F811
    from mcp.shared.memory import create_connected_server_and_client_session as conn
    from src.mcp_server import create_server

    posted = []
    chat = ScriptedChat(call("post_pr_comment", release_id="r1"), say("done"))
    async with conn(create_server(service)) as session:
        run = await AgentLoop(session, chat, skills, post_comment=lambda rid: posted.append(rid) or {"action": "created"}).run("r1")
    assert posted == ["r1"] and not run.calls[0]["error"]
    tools = {t["function"]["name"] for t in chat.sent[0][1]}
    assert "post_pr_comment" in tools
    # the tool takes only a release id: there is no text parameter for the model to fill
    schema = next(t for t in chat.sent[0][1] if t["function"]["name"] == "post_pr_comment")["function"]["parameters"]
    assert list(schema["properties"]) == ["release_id"]


async def test_the_comment_tool_is_not_offered_when_the_github_mcp_server_is_not_configured(service, skills):  # noqa: F811
    from mcp.shared.memory import create_connected_server_and_client_session as conn
    from src.mcp_server import create_server

    chat = ScriptedChat(call("post_pr_comment", release_id="r1"), say("done"))
    async with conn(create_server(service)) as session:
        run = await AgentLoop(session, chat, skills).run("r1")
    assert run.calls[0]["error"] and "post_pr_comment" not in {t["function"]["name"] for t in chat.sent[0][1]}
