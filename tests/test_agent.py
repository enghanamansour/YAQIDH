import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from src.agent.agent import Agent, ToolBox, ToolNotAllowed
from src.agent.explain import BackendExplainer
from src.mcp_server import create_server
from src.schema import StageName
from src.service import ReleaseService
from src.storage import EvidenceStore
from tests.test_service import POLICY, FakeScanner, finding, seed_approved_qa

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeExplainer:
    def __init__(self):
        self.seen = []

    def explain(self, f):
        self.seen.append(f["fingerprint"])
        return f"explained {f['fingerprint']}"


@pytest.fixture
def service(tmp_path):
    scanner = FakeScanner([finding("F-1"), finding("F-2")])
    svc = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY, {StageName.SECURITY: scanner}, Path(tmp_path))
    seed_approved_qa(svc.store)
    return svc


async def test_agent_explains_open_findings_through_mcp(service):
    service.run_scan("r1", "security")
    fake = FakeExplainer()
    async with connect(create_server(service)) as session:
        result = await Agent(ToolBox(session), fake).explain_stage("r1", "security")
    assert sorted(result["explained"]) == ["F-1", "F-2"] and not result["failed"]
    stage = next(s for s in service.get_evidence("r1")["stages"] if s["name"] == "security")
    assert all(f["explanation"]["source"] == "Yaqidh" for f in stage["findings"])
    assert stage["decision"] is None  # the agent decided nothing


async def test_same_fingerprint_is_not_explained_twice(service):
    service.run_scan("r1", "security")
    fake = FakeExplainer()
    async with connect(create_server(service)) as session:
        agent = Agent(ToolBox(session), fake)
        await agent.explain_stage("r1", "security")
        second = await agent.explain_stage("r1", "security")
    assert second["explained"] == [] and sorted(second["reused"]) == ["F-1", "F-2"]
    assert len(fake.seen) == 2


async def test_one_failing_explanation_does_not_stop_the_rest(service):
    service.run_scan("r1", "security")

    class Flaky(FakeExplainer):
        def explain(self, f):
            if f["fingerprint"] == "F-1":
                raise ValueError("model down")
            return super().explain(f)

    async with connect(create_server(service)) as session:
        result = await Agent(ToolBox(session), Flaky()).explain_stage("r1", "security")
    assert result["explained"] == ["F-2"] and result["failed"][0]["fingerprint"] == "F-1"


@pytest.mark.parametrize("tool", ["run_scan", "verify_fix", "evaluate_policy", "get_evidence", "approve", "merge"])
async def test_agent_cannot_call_any_other_tool(service, tool):
    async with connect(create_server(service)) as session:
        with pytest.raises(ToolNotAllowed):
            await ToolBox(session).call(tool, release_id="r1", stage="security")


def test_backend_explainer_turns_a_finding_into_labelled_text():
    from src.agent.explain import _backend_modules

    TemplateExplainer = _backend_modules()[1].TemplateExplainer  # hana's fixed-text fallback, no network

    text = BackendExplainer(TemplateExplainer(), "ar").explain(
        {"fingerprint": "F-1", "rule": "python.flask.security.audit.debug-enabled", "severity": "high",
         "location": "app.py:12", "detail": "debug on", "tool": "semgrep"}
    )
    assert "المشكلة:" in text and "app.py" in text and "ليش خطرة:" in text
