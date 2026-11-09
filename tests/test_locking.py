"""Two processes (like the API and the MCP server) writing the same release must never lose each other's change."""

import multiprocessing as mp
from pathlib import Path

from src.schema import StageName
from src.service import ReleaseService
from src.storage import EvidenceStore
from tests.test_service import POLICY

WRITES = 25


def worker(data_dir: str, name: str) -> None:
    service = ReleaseService(EvidenceStore(Path(data_dir)), POLICY, {}, Path(data_dir))
    for i in range(WRITES):
        service.add_human_decision("r1", "qa", "approve", f"{name}-{i}", "")


def test_decisions_written_by_two_processes_at_once_are_all_kept(tmp_path):
    EvidenceStore(tmp_path).create("r1")
    ctx = mp.get_context("spawn")
    procs = [ctx.Process(target=worker, args=(str(tmp_path), n)) for n in ("a", "b")]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=120)
        assert p.exitcode == 0
    decisions = EvidenceStore(tmp_path).get("r1").human_decisions
    assert len(decisions) == 2 * WRITES
    assert {d.by for d in decisions} == {f"{n}-{i}" for n in ("a", "b") for i in range(WRITES)}


def test_the_lock_does_not_leave_files_that_look_like_releases(tmp_path):
    store = EvidenceStore(tmp_path)
    store.create("r1")
    with store.locked("r1"):
        pass
    assert [p.name for p in tmp_path.glob("*.json")] == ["r1.json"]


def test_a_bad_release_id_is_still_refused_by_the_lock(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        with EvidenceStore(tmp_path).locked("../x"):
            pass
