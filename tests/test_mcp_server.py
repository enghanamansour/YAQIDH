import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from src.mcp_server import create_server
from src.schema import StageName
from src.service import ReleaseService
from src.storage import EvidenceStore
from tests.test_service import POLICY, FakeScanner, finding, seed_approved_qa

pytestmark = pytest.mark.anyio

EXPECTED = {"run_scan", "get_findings", "verify_fix", "evaluate_policy", "append_evidence", "get_evidence"}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def server(tmp_path):
    service = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY, {StageName.SECURITY: FakeScanner([finding("F-1")])}, Path(tmp_path))
    seed_approved_qa(service.store)
    return create_server(service)


async def call(session, name, **args):
    result = await session.call_tool(name, args)
    text = result.content[0].text if result.content else ""
    return result.isError, text


async def test_exactly_six_tools_and_none_that_decide(server):
    async with connect(server) as session:
        names = {t.name for t in (await session.list_tools()).tools}
    assert names == EXPECTED


async def test_a_full_round_through_mcp(server):
    async with connect(server) as session:
        assert not (await call(session, "run_scan", release_id="r1", stage="security"))[0]
        is_error, text = await call(session, "evaluate_policy", release_id="r1", stage="security")
        assert not is_error and json.loads(text)["result"] == "fail"
        assert not (await call(session, "append_evidence", release_id="r1", stage="security", fingerprint="F-1", text="why")) [0]
        _, text = await call(session, "get_evidence", release_id="r1")
        stage = next(s for s in json.loads(text)["stages"] if s["name"] == "security")
        assert stage["findings"][0]["explanation"]["source"] == "Yaqidh"
        assert stage["decision"]["decided_by"] == "policy_engine"


async def test_errors_come_back_as_tool_errors_not_as_success(server):
    async with connect(server) as session:
        is_error, text = await call(session, "run_scan", release_id="r1", stage="qa")
        assert is_error and "no tools are registered" in text
        is_error, _ = await call(session, "get_evidence", release_id="nope")
        assert is_error
