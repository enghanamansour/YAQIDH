import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

from src.schema import Evidence

_RELEASE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class ReleaseNotFound(Exception):
    pass


class ReleaseExists(Exception):
    pass


try:  # POSIX file locks; on other systems only the in-process lock applies
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


class EvidenceStore:
    """One JSON file per release. Kept behind this interface so the storage can change later."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, release_id: str) -> Path:
        # release_id becomes a filename, so reject anything that could escape data_dir.
        if not _RELEASE_ID.match(release_id):
            raise ValueError(f"invalid release_id: {release_id!r}")
        return self.data_dir / f"{release_id}.json"

    @contextmanager
    def locked(self, release_id: str):
        """Holds an exclusive lock on one release across processes (the API and the MCP server both write evidence).

        Wrap a whole read-change-save in it, so two writers can never overwrite each other's change."""
        self._path(release_id)  # rejects a bad id before it becomes a file name
        lock_dir = self.data_dir / ".locks"
        lock_dir.mkdir(exist_ok=True)
        with (lock_dir / f"{release_id}.lock").open("a") as handle:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(handle, fcntl.LOCK_UN)

    def exists(self, release_id: str) -> bool:
        return self._path(release_id).exists()

    def create(self, release_id: str) -> Evidence:
        if self.exists(release_id):
            raise ReleaseExists(release_id)
        evidence = Evidence(release_id=release_id)
        self.save(evidence)
        return evidence

    def get(self, release_id: str) -> Evidence:
        path = self._path(release_id)
        if not path.exists():
            raise ReleaseNotFound(release_id)
        return Evidence.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, evidence: Evidence) -> None:
        path = self._path(evidence.release_id)
        # Write to a temp file then rename, so a crash never leaves a half-written file.
        fd, tmp = tempfile.mkstemp(dir=self.data_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(evidence.model_dump_json(indent=2))
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
