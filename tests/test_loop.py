import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from src.agent.loop import AgentLoop
from src.agent.skills import Skills
from src.mcp_server import create_server
from src.schema import StageName
from src.service import ReleaseService
from src.storage import EvidenceStore
from tests.test_service import POLICY, FakeScanner, finding, seed_approved_qa

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


class ScriptedChat:
    """Stands in for the model: replies with the next scripted message and records what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.sent = []

    def complete(self, messages, tools):
        self.sent.append((list(messages), tools))
        if not self.replies:
            raise RuntimeError("the script ran out")
        return self.replies.pop(0)


def call(tool, /, **args):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": f"c-{tool}", "type": "function", "function": {"name": tool, "arguments": json.dumps(args)}}]}


def say(text):
    return {"role": "assistant", "content": text}


@pytest.fixture
def skills(tmp_path):
    d = tmp_path / "skills" / "sql-injection"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: sql-injection\ndescription: SQL built from user input\n---\nExplain it in words.\n")
    return Skills(tmp_path / "skills")


@pytest.fixture
def service(tmp_path):
    svc = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY,
                         {StageName.SECURITY: FakeScanner([finding("F-1"), finding("F-2")])}, Path(tmp_path))
    seed_approved_qa(svc.store)
    return svc


async def drive(service, skills, chat, **kw):
    async with connect(create_server(service)) as session:
        return await AgentLoop(session, chat, skills, **kw).run("r1")


async def test_the_model_chooses_the_tools_and_the_explanation_is_stored(service, skills):
    chat = ScriptedChat(
        call("run_scan", release_id="r1", stage="security"),
        call("evaluate_policy", release_id="r1", stage="security"),
        call("list_skills"),
        call("read_skill", name="sql-injection"),
        call("append_evidence", release_id="r1", stage="security", fingerprint="F-1", text="المشكلة: x"),
        say("done"),
    )
    run = await drive(service, skills, chat)
    assert run.stopped == "done" and run.final == "done" and run.steps == 6
    assert [c["tool"] for c in run.calls] == ["run_scan", "evaluate_policy", "list_skills", "read_skill", "append_evidence"]
    assert not any(c["error"] for c in run.calls)
    stage = next(s for s in service.get_evidence("r1")["stages"] if s["name"] == "security")
    assert stage["findings"][0]["explanation"]["source"] == "Yaqidh"
    assert stage["decision"]["decided_by"] == "policy_engine"  # the model decided nothing


async def test_the_model_is_told_the_release_state_and_sees_only_allowed_tools(service, skills):
    chat = ScriptedChat(say("nothing to do"))
    await drive(service, skills, chat)
    messages, tools = chat.sent[0]
    assert "awaiting_security_scan" in messages[1]["content"]
    names = {t["function"]["name"] for t in tools}
    assert names == {"run_scan", "verify_fix", "get_findings", "evaluate_policy", "append_evidence", "get_evidence", "list_skills", "read_skill"}


@pytest.mark.parametrize("tool", ["merge", "approve", "close_finding", "set_status"])
async def test_a_tool_that_does_not_exist_is_refused_and_the_loop_continues(service, skills, tool):
    chat = ScriptedChat(call(tool, release_id="r1"), say("ok"))
    run = await drive(service, skills, chat)
    assert run.calls[0]["error"] and run.stopped == "done"
    refusal = chat.sent[1][0][-1]["content"]
    assert "not an allowed tool" in refusal


async def test_bad_arguments_are_refused_before_the_tool_runs(service, skills):
    chat = ScriptedChat(call("run_scan", release_id="r1"), say("ok"))  # stage missing
    run = await drive(service, skills, chat)
    assert run.calls[0]["error"]
    assert not service.store.get("r1").stage(StageName.SECURITY).tool_versions  # nothing was scanned


async def test_an_unknown_skill_name_is_refused(service, skills):
    chat = ScriptedChat(call("read_skill", name="made-up"), say("ok"))
    run = await drive(service, skills, chat)
    assert run.calls[0]["error"] and "Available: sql-injection" in chat.sent[1][0][-1]["content"]


async def test_an_explanation_with_code_is_refused(service, skills):
    service.run_scan("r1", "security")
    chat = ScriptedChat(call("append_evidence", release_id="r1", stage="security", fingerprint="F-1", text="use `cursor.execute(q, p)`"), say("ok"))
    run = await drive(service, skills, chat)
    assert run.calls[0]["error"]
    assert service.get_findings("r1", "security")[0]["explanation"] is None


async def test_the_same_finding_is_not_explained_twice(service, skills):
    service.run_scan("r1", "security")
    service.append_evidence("r1", "security", "F-1", "first")
    chat = ScriptedChat(call("append_evidence", release_id="r1", stage="security", fingerprint="F-1", text="again"), say("ok"))
    run = await drive(service, skills, chat)
    assert run.calls[0]["error"]
    assert service.get_findings("r1", "security")[0]["explanation"]["text"] == "first"


async def test_the_stage_order_still_holds_when_the_model_tries_to_skip_it(tmp_path, skills):
    svc = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY, {StageName.SECURITY: FakeScanner([finding("F-1")])}, tmp_path)
    chat = ScriptedChat(call("run_scan", release_id="r1", stage="security"), say("ok"))
    run = await drive(svc, skills, chat)  # QA was never approved
    assert run.calls[0]["error"] and "not_started" in chat.sent[1][0][-1]["content"]


async def test_a_model_that_never_stops_is_cut_off_at_the_step_limit(service, skills):
    chat = ScriptedChat(*[call("get_evidence", release_id="r1")] * 10)
    run = await drive(service, skills, chat, max_steps=4)
    assert run.stopped == "step_limit" and run.steps == 4


async def test_a_failing_model_call_ends_the_run_without_crashing(service, skills):
    run = await drive(service, skills, ScriptedChat())  # the script is empty, so complete() raises
    assert run.stopped == "error" and "script ran out" in run.final


# --- keeping each model request small, and waiting out rate limits ---

async def test_the_model_sees_unexplained_findings_in_small_batches(tmp_path, skills):
    many = [finding(f"F-{i}") for i in range(12)]
    svc = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY, {StageName.SECURITY: FakeScanner(many)}, tmp_path)
    seed_approved_qa(svc.store)
    svc.run_scan("r1", "security")
    svc.append_evidence("r1", "security", "F-0", "done already")
    chat = ScriptedChat(call("get_findings", release_id="r1", stage="security"), say("ok"))
    await drive(svc, skills, chat)
    seen = json.loads(chat.sent[1][0][-1]["content"])
    assert seen["total_findings"] == 12 and seen["need_explanation"] == 11
    assert len(seen["shown"]) == 5 and "F-0" not in {f["fingerprint"] for f in seen["shown"]}


def test_a_rate_limit_is_waited_out_then_the_call_goes_through():
    import httpx

    from src.agent.loop import ChatClient

    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, text="Rate limit reached. Please try again in 3.5s.")
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "hi"}}]})

    waits = []
    chat = ChatClient("http://x", "k", "m", client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=waits.append)
    assert chat.complete([], [])["content"] == "hi"
    assert waits == [4.5]


def test_a_wrong_model_name_fails_at_once_instead_of_retrying():
    import httpx

    from src.agent.loop import ChatClient

    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404, text="model_not_found")

    chat = ChatClient("http://x", "k", "m", client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None)
    with pytest.raises(RuntimeError, match="404"):
        chat.complete([], [])
    assert len(calls) == 1


async def test_old_steps_are_dropped_whole_so_the_conversation_stays_small_and_valid(service, skills):
    chat = ScriptedChat(*[call("get_evidence", release_id="r1")] * 8, say("ok"))
    await drive(service, skills, chat)
    last_sent = chat.sent[-1][0]
    steps = [m for m in last_sent if m.get("tool_calls")]
    assert len(steps) == 3  # only the latest steps remain
    # every tool message directly follows the model message that asked for it
    for i, m in enumerate(last_sent):
        if m["role"] == "tool":
            assert last_sent[i - 1].get("tool_calls") or last_sent[i - 1]["role"] == "tool"
    assert "Earlier steps were removed" in last_sent[2]["content"]


async def test_a_slow_model_call_does_not_freeze_the_rest_of_the_server(service, skills):
    """The model call blocks (and may sleep through a rate limit). It must not stop the event loop, or the whole API hangs."""
    import asyncio
    import time

    class SlowChat(ScriptedChat):
        def complete(self, messages, tools):
            time.sleep(0.6)
            return super().complete(messages, tools)

    ticks = []

    async def heartbeat():
        while True:
            ticks.append(time.monotonic())
            await asyncio.sleep(0.05)

    task = asyncio.create_task(heartbeat())
    try:
        await drive(service, skills, SlowChat(say("done")))
    finally:
        task.cancel()
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    assert ticks and max(gaps) < 0.3  # without the thread there would be one gap of about 0.6 seconds
