"""The guided demo: a visitor plays the whole loop (developer, QA, security) without GitHub.

The results of the real tools (Playwright, Semgrep, Trivy), recorded on demo_app by scripts/record_demo_fixtures.py, are sent
to the real Yaqidh API exactly as a CI job would send them. So the policy engine, the explanations, the human approvals and
the evidence log all run for real; only the tool runs are replayed. The dashboard says so on every page.

Three recorded states, in the order the demo walks them:
  phase 0  the pull request as planted      QA fails
  phase 1  after the developer's QA fix     QA passes; the security results wait until the QA reviewer approves
  phase 2  after the security fix           the problems are closed; the security reviewer decides
"""
import hashlib
import json
import secrets
from pathlib import Path

PUSHABLE = {"qa_blocked", "qa_rejected", "security_blocked", "security_rejected"}


class DemoPlayer:
    def __init__(self, backend, fixtures_path):
        self.backend = backend  # live.LiveBackend: it already knows the API address and token
        self.fixtures = json.loads(Path(fixtures_path).read_text(encoding="utf-8"))
        self.release = ""
        self.phase = 0
        self.pushes = 0
        self.runs = 0

    def _commit(self) -> str:
        self.pushes += 1
        return hashlib.sha1(f"{self.release}-{self.pushes}".encode()).hexdigest()

    def _results(self, stage: str, index: int, commit: str) -> dict:
        return {**self.fixtures[stage][index], "stage": stage, "commit": commit}

    def start(self) -> None:
        """A new pull request: the first recorded QA results arrive, and QA fails."""
        self.runs += 1
        self.release = f"demo-{self.runs}-{secrets.token_hex(2)}"
        self.phase = self.pushes = 0
        commit = self._commit()
        self.backend._call("POST", f"/releases/{self.release}/events", {"event": "pull_request_opened", "commit": commit})
        self.backend._call("POST", f"/releases/{self.release}/scan-results", self._results("qa", 0, commit))

    def can_push(self, status: str) -> bool:
        if not self.release:
            return False
        if status == "security_blocked" and self.phase >= 2:
            return False  # the developer's fixes are all in; the security reviewer decides about the one medium finding left
        return status in PUSHABLE

    def push(self, status: str) -> None:
        """The developer pushes a fix: the next recorded state arrives. After a reviewer returned the request, the same state
        arrives again on a new commit (the developer pushes again)."""
        if not self.can_push(status):
            raise ValueError("nothing to push in this state")
        if status in ("qa_blocked", "security_blocked") and self.phase < 2:
            self.phase += 1
        commit = self._commit()
        self.backend._call("POST", f"/releases/{self.release}/events", {"event": "push", "commit": commit})
        self.backend._call("POST", f"/releases/{self.release}/scan-results", self._results("qa", self.phase, commit))
        if self.phase >= 1:  # the security scan of the same code; it waits until it is security's turn
            self.backend._call("POST", f"/releases/{self.release}/scan-results", self._results("security", self.phase - 1, commit))

    def guide(self, status: str) -> dict:
        return {"phase": self.phase, "status": status, "canPush": self.can_push(status)}
