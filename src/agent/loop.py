"""The agent as a tool-calling loop: the model chooses which tool to call and in what order.

What keeps it safe is not the loop but the tools: the MCP server has no tool that decides, closes,
approves or merges. The code adds: a fixed list of allowed tools, argument checks against each tool's
schema, a step limit, and a few rules on the one write the model has (its explanation text).
"""

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field

import httpx
from jsonschema import ValidationError, validate
from mcp import ClientSession

from src.agent.prompt import SYSTEM_PROMPT, task_message
from src.agent.skills import SkillError, Skills
from src.phases.status import release_status
from src.schema import Evidence

MCP_TOOLS = frozenset({"run_scan", "verify_fix", "get_findings", "evaluate_policy", "append_evidence", "get_evidence"})
LOCAL_TOOLS = {
    "list_skills": {"description": "List the available skills (name and when to use each).", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    "read_skill": {
        "description": "Read one skill by name before explaining a finding that fits it.",
        "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"], "additionalProperties": False},
    },
}
POST_COMMENT_TOOL = {
    "description": "Post (or update) the one summary comment on the release's pull request. The text is built from the "
                   "evidence by the system; you cannot write it. Call it once at the end, after your explanations are saved.",
    "inputSchema": {"type": "object", "properties": {"release_id": {"type": "string"}}, "required": ["release_id"], "additionalProperties": False},
}
MAX_STEPS = 60
MAX_RESULT_CHARS = 8000
BATCH = 5  # how many unexplained findings the model sees per get_findings call, to keep each request small
MAX_GROUP = 12  # how many CVEs of one library are listed to the model
KEEP_STEPS = 3 # only the latest tool steps stay in the conversation, so each request stays small


class ChatClient:
    """Any OpenAI-compatible chat endpoint (Groq by default). Reads LLM_API_KEY, LLM_BASE_URL, LLM_MODEL."""

    def __init__(self, base_url=None, api_key=None, model=None, client: httpx.Client | None = None, sleep=time.sleep):
        self.sleep = sleep
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "openai/gpt-oss-120b")
        self.client = client or httpx.Client(timeout=60)
        self.total_tokens = 0  # what this client has used so far, to see what a run costs
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY is not set")

    def complete(self, messages: list[dict], tools: list[dict] | None = None, model: str | None = None) -> dict:
        last = None
        body = {"model": model or self.model, "temperature": 0, "messages": messages}
        if tools:
            body.update(tools=tools, tool_choice="auto")
        for _ in range(10):  # a malformed tool call or a rate limit usually passes on another try
            resp = self.client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            if resp.status_code == 200:
                body_json = resp.json()
                self.total_tokens += (body_json.get("usage") or {}).get("total_tokens", 0)
                return body_json["choices"][0]["message"]
            last = f"{resp.status_code}: {resp.text[:300]}"
            if resp.status_code == 429:  # free tiers limit tokens per minute: wait as long as the server says
                wait = re.search(r"try again in ([\d.]+)s", resp.text)
                self.sleep(min(float(wait.group(1)) + 1 if wait else 10, 60))
            elif resp.status_code in (401, 403, 404):
                break  # a wrong key or model name will not fix itself
        raise RuntimeError(f"the model call failed ({last})")


@dataclass
class Run:
    stopped: str = "done"  # done | step_limit | error
    steps: int = 0
    final: str = ""
    calls: list[dict] = field(default_factory=list)
    tokens: int = 0  # tokens the model calls used, when the client reports them


def _openai_tool(name: str, description: str, schema: dict) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": schema}}


class AgentLoop:
    def __init__(self, session: ClientSession, chat, skills: Skills | None = None, max_steps: int = MAX_STEPS,
                 post_comment=None, dialect=None):
        """post_comment(release_id) posts the PR comment through the GitHub MCP server; without it the tool is not offered.
        dialect (DialectStep) rewrites each saved explanation in Saudi dialect; the original is kept if it is rejected."""
        self.post_comment = post_comment
        self.dialect = dialect
        self.session = session
        self.chat = chat
        self.skills = skills or Skills()
        self.max_steps = max_steps
        self._schemas: dict[str, dict] = {}

    async def _load_tools(self) -> list[dict]:
        listed = {t.name: t for t in (await self.session.list_tools()).tools}
        tools = []
        for name in sorted(MCP_TOOLS & listed.keys()):
            self._schemas[name] = listed[name].inputSchema
            tools.append(_openai_tool(name, listed[name].description or "", listed[name].inputSchema))
        local = dict(LOCAL_TOOLS)
        if self.post_comment is not None:
            local["post_pr_comment"] = POST_COMMENT_TOOL
        for name, spec in local.items():
            self._schemas[name] = spec["inputSchema"]
            tools.append(_openai_tool(name, spec["description"], spec["inputSchema"]))
        return tools

    async def _state(self, release_id: str) -> tuple[str, list[str]]:
        try:
            result = await self.session.call_tool("get_evidence", {"release_id": release_id})
            if result.isError:
                raise ValueError(result.content[0].text if result.content else "error")
            data = result.structuredContent if result.structuredContent is not None else json.loads(result.content[0].text)
            report = release_status(Evidence.model_validate(data))
        except Exception:  # a release that does not exist yet
            return "not_started", ["no evidence yet"]
        return report.status.value, report.reasons

    async def _execute(self, name: str, args: dict) -> str:
        """Runs one tool call the model asked for. Every problem comes back as text the model can read."""
        allowed = MCP_TOOLS | LOCAL_TOOLS.keys() | ({"post_pr_comment"} if self.post_comment is not None else set())
        if name not in allowed:
            return f"ERROR: '{name}' is not an allowed tool. Allowed: {', '.join(sorted(allowed))}"
        try:
            validate(args, self._schemas[name])
        except ValidationError as e:
            return f"ERROR: bad arguments for {name}: {e.message}"
        try:
            if name == "post_pr_comment":
                return json.dumps(await asyncio.to_thread(self.post_comment, args["release_id"]), ensure_ascii=False)
            if name == "list_skills":
                return json.dumps(self.skills.list(), ensure_ascii=False)
            if name == "read_skill":
                return self.skills.read(args["name"])
            if name == "append_evidence":
                problem = await self._explanation_problem(args)
                if problem:
                    return f"ERROR: {problem}"
                if self.dialect is not None:
                    args = {**args, "text": await asyncio.to_thread(self.dialect.rewrite, args["text"])}
            result = await self.session.call_tool(name, args)
        except SkillError as e:
            return f"ERROR: {e}"
        if name == "get_findings" and not result.isError:
            return self._findings_view(result)
        text = json.dumps(result.structuredContent, ensure_ascii=False) if result.structuredContent is not None else (
            result.content[0].text if result.content else ""
        )
        return ("ERROR: " if result.isError else "") + text[:MAX_RESULT_CHARS]

    @staticmethod
    def _upgrade_target(versions: list[str]) -> str | None:
        """The one version that fixes every CVE of a library: the highest of all the fixed versions listed."""
        from packaging.version import InvalidVersion, Version

        tokens = [t.strip() for v in versions for t in v.split(",") if t.strip()]
        try:
            return str(max(tokens, key=Version)) if tokens else None
        except InvalidVersion:
            return None

    @classmethod
    def _findings_view(cls, result) -> str:
        """What the model sees: open findings that still need an explanation, a few at a time.

        Findings of the same library (same component) are shown as ONE item with also_for listing the other
        fingerprints, so the model explains the library once. Each CVE keeps its own fingerprint and status."""
        items = (result.structuredContent or {}).get("result", [])
        todo = [f for f in items if f["status"] == "open" and not f.get("explanation")]
        keys = ("fingerprint", "tool", "rule", "location", "severity", "reported_as", "component", "fixed_version", "cwe", "confidence")
        groups: dict[str, list[dict]] = {}
        units: list[list[dict]] = []
        for f in todo:
            comp = f.get("component")
            if comp and comp in groups:
                groups[comp].append(f)
            else:
                unit = [f]
                units.append(unit)
                if comp:
                    groups[comp] = unit
        shown = []
        for unit in units[:BATCH]:
            unit = sorted(unit, key=lambda f: (f["severity"] != "high", f["rule"]))
            main = unit[0]
            entry = {**{k: main[k] for k in keys if main.get(k)}, "detail": main.get("detail", "")[:300]}
            if len(unit) > 1:
                entry["also_for"] = [f["fingerprint"] for f in unit[1:]]
                entry["group"] = [
                    {k: f[k] for k in ("rule", "severity", "fixed_version", "cwe") if f.get(k)} for f in unit[:MAX_GROUP]
                ]
                target = cls._upgrade_target([f["fixed_version"] for f in unit if f.get("fixed_version")])
                if target:
                    entry["fix_all_by_upgrading_to"] = target
            shown.append(entry)
        return json.dumps(
            {"total_findings": len(items), "need_explanation": len(todo), "shown": shown,
             "note": "call get_findings again after explaining these to see the next ones"},
            ensure_ascii=False,
        )

    async def _explanation_problem(self, args: dict) -> str | None:
        if "`" in args["text"]:
            return "explanations are words only: no code, no commands, no backticks"
        found = await self.session.call_tool("get_findings", {"release_id": args["release_id"], "stage": args["stage"]})
        items = (found.structuredContent or {}).get("result", [])
        for f in items:
            if f["fingerprint"] == args["fingerprint"] and f.get("explanation"):
                return f"{args['fingerprint']} already has an explanation and has not changed, do not explain it again"
        return None

    @staticmethod
    def _trim(messages: list[dict]) -> None:
        """Drops the oldest tool steps (a model message with its tool results) beyond KEEP_STEPS.

        Whole steps are removed, never half of one, so the conversation stays valid. Nothing is lost that
        matters: what is already explained is in the evidence, and get_findings only shows what is left."""
        starts = [i for i, m in enumerate(messages) if i >= 2 and m.get("role") == "assistant" and m.get("tool_calls")]
        if len(starts) <= KEEP_STEPS:
            return
        cut = starts[-KEEP_STEPS]
        del messages[2:cut]
        messages.insert(2, {"role": "user", "content": "Earlier steps were removed to save space. Continue from the current "
                            "state: call get_findings to see what still needs an explanation."})

    async def run(self, release_id: str, event: str = "pull_request_opened") -> Run:
        tools = await self._load_tools()
        status, reasons = await self._state(release_id)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task_message(release_id, event, status, reasons, self.skills.list())},
        ]
        run = Run()
        start_tokens = getattr(self.chat, "total_tokens", 0)
        try:
            return await self._loop(run, messages, tools, start_tokens)
        finally:
            run.tokens = getattr(self.chat, "total_tokens", 0) - start_tokens

    async def _loop(self, run: Run, messages: list[dict], tools: list[dict], start_tokens: int) -> Run:
        for _ in range(self.max_steps):
            self._trim(messages)
            try:
                # The call is blocking (an HTTP request, and a sleep when the provider says "wait"). Run directly it
                # froze the whole server for as long as 20 seconds: no webhook, gate or dashboard answered.
                message = await asyncio.to_thread(self.chat.complete, messages, tools)
            except Exception as e:
                run.stopped, run.final = "error", str(e)
                return run
            run.steps += 1
            messages.append({k: v for k, v in message.items() if v is not None})
            calls = message.get("tool_calls") or []
            if not calls:
                run.final = message.get("content") or ""
                return run
            for call in calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args, output = {}, "ERROR: the arguments were not valid JSON"
                else:
                    output = await self._execute(name, args)
                run.calls.append({"tool": name, "args": args, "error": output.startswith("ERROR")})
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": output})
        run.stopped = "step_limit"
        return run
