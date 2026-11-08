"""Posts the agent's comment and the check status on GitHub.

Two things, and they are different:
  * the comment is what the developer reads (it is updated, not repeated);
  * the status sits on the commit. Turn on "Require status checks" in the
    branch protection and name this status there, and GitHub itself refuses to
    merge while it is red. That is what really blocks a merge.

A failure here never changes the gate's decision. The gate (`GET /gate`) stays
the single source of truth, and a failed post is reported, not hidden.
"""
from __future__ import annotations

import re

import httpx

API = "https://api.github.com"
FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
CONTEXT = "yaqidh/{phase}"


def marker(phase: str) -> str:
    return f"<!-- yaqidh:{phase} -->"


class GitHubError(Exception):
    pass


class GitHubClient:
    def __init__(self, token: str, *, client: httpx.Client | None = None, api: str = API):
        self.api = api.rstrip("/")
        self.client = client or httpx.Client(timeout=20.0)
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _call(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            resp = self.client.request(method, f"{self.api}{path}", headers=self.headers, **kwargs)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise GitHubError(f"{method} {path} failed: {e}") from e
        return resp

    def upsert_comment(self, repo: str, pr: int, phase: str, body: str) -> dict:
        """One comment per phase on the pull request: edited in place on every scan."""
        tag = marker(phase)
        text = f"{tag}\n{body}"
        existing = self._call("GET", f"/repos/{repo}/issues/{pr}/comments", params={"per_page": 100}).json()
        mine = next((c for c in existing if tag in (c.get("body") or "")), None)
        if mine:
            resp = self._call("PATCH", f"/repos/{repo}/issues/comments/{mine['id']}", json={"body": text})
            return {"action": "updated", "id": resp.json().get("id", mine["id"])}
        resp = self._call("POST", f"/repos/{repo}/issues/{pr}/comments", json={"body": text})
        return {"action": "created", "id": resp.json().get("id")}

    def set_status(self, repo: str, commit: str, phase: str, *, allowed: bool, description: str) -> dict:
        if not FULL_SHA.match(commit):
            raise GitHubError("a status needs the full 40-character commit id")
        payload = {
            "state": "success" if allowed else "failure",
            "context": CONTEXT.format(phase=phase),
            "description": description[:140],
        }
        self._call("POST", f"/repos/{repo}/statuses/{commit}", json=payload)
        return {"state": payload["state"], "context": payload["context"]}
