"""Append-only evidence log.

Every entry carries the hash of the entry before it, so changing or deleting
anything in the middle breaks the chain and `verify()` reports it.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64


def _digest(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class EvidenceLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def append(self, *, repo: str, pr: int, commit: str, phase: str, event: str, data: dict | None = None) -> dict:
        with self._lock:
            entries = self._entries()
            entry = {
                "seq": len(entries) + 1,
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "repo": repo,
                "pr": pr,
                "commit": commit,
                "phase": phase,
                "event": event,
                "data": data or {},
                "prev_hash": entries[-1]["hash"] if entries else GENESIS,
            }
            entry["hash"] = _digest(entry)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            return entry

    def entries(self, repo: str | None = None, pr: int | None = None) -> list[dict]:
        return [e for e in self._entries() if (repo is None or e["repo"] == repo) and (pr is None or e["pr"] == pr)]

    def verify(self) -> dict:
        prev = GENESIS
        for i, e in enumerate(self._entries(), start=1):
            if e.get("seq") != i or e.get("prev_hash") != prev or e.get("hash") != _digest(e):
                return {"valid": False, "broken_at": i}
            prev = e["hash"]
        return {"valid": True, "broken_at": None}
