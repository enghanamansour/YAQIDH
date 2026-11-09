"""Live mode for the dashboard: releases come from the Yaqidh API instead of the seeded demo data.

The dashboard server keeps doing what it already does (login, roles, who may see what, discussions, admin).
This module only replaces where the release data comes from, and where a reviewer's decision goes:
  * reading: GET /releases and GET /releases/{id} on the Yaqidh API (one read per request, then cached for it);
  * deciding: POST /releases/{id}/stages/{stage}/approve|reject. The API still checks the release is waiting for
    that decision, so the dashboard cannot approve something that is not ready.
Start it with:  python server.py --live --api-url http://127.0.0.1:8000     (token in YAQIDH_API_TOKEN)
"""

import json
import os
import urllib.error
import urllib.request

QA_STATES = {"not_started", "qa_blocked", "awaiting_qa_approval", "qa_rejected"}
TOOLS = {"qa": ["playwright"], "security": ["semgrep", "trivy"]}


class LiveError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(f"{status}: {detail}")
        self.status, self.detail = status, detail


class LiveBackend:
    def __init__(self, base_url: str, token: str, evidence_model, project: str = "portal", owners=("developer",)):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.Evidence = evidence_model
        self.project = project
        self.owners = tuple(owners)
        self._evidence: dict[str, dict] = {}
        self._status: dict[str, dict] = {}
        self.error = ""  # why the last refresh failed ("" = fine), shown to the user instead of an empty page

    def _call(self, method: str, path: str, body: dict | None = None):
        request = urllib.request.Request(
            self.base_url + path, method=method, headers={"X-API-Token": self.token, "Content-Type": "application/json"},
            data=json.dumps(body).encode() if body is not None else None,
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read() or b"null")
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read()).get("detail", "")
            except Exception:
                detail = ""
            raise LiveError(e.code, str(detail)) from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise LiveError(503, f"the Yaqidh API is not reachable: {e}") from None

    # --- reading ---
    def refresh(self, releases: dict, runs: dict, dates: dict) -> None:
        """Rebuilds the dashboard's release tables from the API. Called once per request."""
        self._evidence.clear()
        self._status.clear()
        releases.clear(), runs.clear(), dates.clear()
        self.error = ""
        try:
            listed = self._call("GET", "/releases")
        except LiveError as e:  # the API is down or refuses us: show no releases (never stale ones) and say why
            self.error = {401: "the dashboard's API token does not match the API's token (check API_TOKEN)",
                          503: "the Yaqidh API is not reachable (is it running on the address given with --api-url?)"}.get(
                e.status, f"the Yaqidh API answered with an error ({e.status})")
            return
        for number, row in enumerate(listed, start=1):
            key = row["release_id"]
            full = self._call("GET", f"/releases/{key}")
            evidence, status = full["evidence"], full["status"]
            self._evidence[key], self._status[key] = evidence, status
            author = evidence.get("author") or ""
            releases[key] = dict(
                project=self.project, owner=author if author in self.owners else self.owners[0],
                pr=evidence.get("pr_number") or number, build=evidence.get("pr_number") or number,
                commit=(evidence.get("head_commit") or "—")[:7], branch=evidence.get("branch") or "—",
                active="qa" if status["status"] in QA_STATES else "security",
            )
            runs[key], latest = {}, ""
            for stage in evidence.get("stages", []):
                scanned = stage.get("scanned_at")
                runs[key][stage["name"]] = [{"tool": t, "state": "completed"} for t in TOOLS[stage["name"]]] if scanned else []
                latest = max(latest, scanned or "")
            dates[key] = latest[:10] or "—"

    def get_evidence(self, key: str):
        if key not in self._evidence:
            raise KeyError(key)
        return self.Evidence.model_validate(self._evidence[key])

    def status(self, key: str) -> str:
        return self._status.get(key, {}).get("status", "")

    def can_decide(self, key: str, role: str) -> bool:
        return self.status(key) == f"awaiting_{role}_approval"

    def history(self, key: str) -> dict:
        """The release's event log and whether its hash chain is intact (fetched only for the detail view)."""
        try:
            entries = self._call("GET", f"/releases/{key}/history")
            verified = self._call("GET", f"/releases/{key}/history/verify")
        except LiveError:
            return {"entries": [], "verified": {"ok": False, "reason": "the history could not be read"}}
        slim = [{"seq": e["seq"], "time": e["time"], "event": e["event"], "actor": e["actor"],
                 "data": {k: v for k, v in e["data"].items() if k not in ("text", "tool_versions", "reasons")}} for e in entries]
        return {"entries": slim, "verified": verified}

    # --- deciding ---
    def decide(self, key: str, role: str, choice: str, reason: str, by: str) -> None:
        self._call("POST", f"/releases/{key}/stages/{role}/{choice}", {"by": by, "reason": reason})


    def grant_exception(self, key: str, fingerprint: str, justification: str, by: str) -> None:
        self._call("POST", f"/releases/{key}/stages/security/exceptions",
                   {"fingerprint": fingerprint, "justification": justification, "approved_by": by})

    def record_review_request(self, key: str, decision: dict) -> None:
        self._call("POST", f"/releases/{key}/review-requests", decision)


class LiveStore:
    """Looks like the demo's EvidenceStore for reading; the evidence itself stays in the Yaqidh API."""

    def __init__(self, live: LiveBackend):
        self.live = live

    def get(self, key: str):
        return self.live.get_evidence(key)

    def save(self, evidence) -> None:  # decisions go through the API, never into a local copy
        raise RuntimeError("in live mode decisions are sent to the Yaqidh API")


def from_env(evidence_model, owners):
    url = os.environ.get("YAQIDH_API_URL", "")
    token = os.environ.get("YAQIDH_API_TOKEN", "")
    if not url or not token:
        raise SystemExit("live mode needs YAQIDH_API_URL (or --api-url) and YAQIDH_API_TOKEN")
    return LiveBackend(url, token, evidence_model, owners=owners)
