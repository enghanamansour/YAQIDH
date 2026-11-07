import pytest

from src.storage import EvidenceStore, ReleaseExists, ReleaseNotFound
from src.schema import Finding, Severity, StageName


@pytest.fixture
def store(tmp_path):
    return EvidenceStore(tmp_path / "releases")


def test_create_then_get(store):
    store.create("rel-001")
    assert store.get("rel-001").release_id == "rel-001"


def test_create_twice_fails(store):
    store.create("rel-001")
    with pytest.raises(ReleaseExists):
        store.create("rel-001")


def test_get_missing_fails(store):
    with pytest.raises(ReleaseNotFound):
        store.get("nope")


def test_save_persists_changes(store):
    ev = store.create("rel-001")
    ev.stage(StageName.QA).findings.append(
        Finding(id="F-001", tool="semgrep", severity=Severity.HIGH, location="a.py:1")
    )
    store.save(ev)
    assert store.get("rel-001").stages[0].findings[0].id == "F-001"


@pytest.mark.parametrize("bad", ["../evil", "a/b", "", "x" * 65, "a b", "..", "a.json"])
def test_unsafe_release_ids_rejected(store, bad):
    with pytest.raises(ValueError):
        store.exists(bad)


def test_no_temp_files_left_behind(store):
    store.create("rel-001")
    assert [p.name for p in store.data_dir.iterdir()] == ["rel-001.json"]
