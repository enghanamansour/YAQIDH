"""History: an append-only log of everything that happened to a release, one JSON line per event.

The evidence file holds the current state; this log keeps the story (scan 1 found 5, scan 2 found 2,
who approved, which explanation was written). Each line carries a hash of its own content plus the hash
of the line before it, so a changed or removed line breaks the chain and verify() reports where.
This detects tampering; it does not prevent someone who rewrites the whole file and every hash.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from src.lock import InterProcessLock

_RELEASE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
GENESIS = "0" * 64


def _digest(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class HistoryLog:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = InterProcessLock(self.directory / ".lock")  # the API and the MCP server both append

    def _path(self, release_id: str) -> Path:
        if not _RELEASE_ID.match(release_id):
            raise ValueError(f"invalid release_id: {release_id!r}")
        return self.directory / f"{release_id}.jsonl"

    def entries(self, release_id: str) -> list[dict]:
        path = self._path(release_id)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def append(self, release_id: str, event: str, actor: str, data: dict | None = None) -> dict:
        """actor says who did it: 'agent', 'system', or the name of the person."""
        with self._lock:
            previous = self.entries(release_id)
            entry = {
                "seq": len(previous) + 1,
                "time": datetime.now(timezone.utc).isoformat(),
                "release_id": release_id,
                "event": event,
                "actor": actor,
                "data": data or {},
                "prev_hash": previous[-1]["hash"] if previous else GENESIS,
            }
            entry["hash"] = _digest(entry)
            with self._path(release_id).open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def verify(self, release_id: str) -> dict:
        """{'ok': True, 'entries': n} or {'ok': False, 'broken_at': seq, 'reason': ...}."""
        entries = self.entries(release_id)
        expected_prev = GENESIS
        for i, e in enumerate(entries, start=1):
            if e.get("seq") != i:
                return {"ok": False, "broken_at": i, "reason": "a line is missing or out of order"}
            if e.get("prev_hash") != expected_prev:
                return {"ok": False, "broken_at": i, "reason": "this line does not follow the one before it"}
            if e.get("hash") != _digest(e):
                return {"ok": False, "broken_at": i, "reason": "this line was changed"}
            expected_prev = e["hash"]
        return {"ok": True, "entries": len(entries)}
