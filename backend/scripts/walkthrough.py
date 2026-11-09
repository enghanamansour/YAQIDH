"""Walks one pull request through the whole Yaqidh loop against a RUNNING API and prints PASS or FAIL per step.

    python scripts/walkthrough.py --url http://127.0.0.1:8000

It only calls the API (the way GitHub and the dashboard do), so it never touches the code of the system it checks.
The API token is read from the API_TOKEN environment variable and is never printed.

The loop it checks, in order:
  1  the door is locked (no token, wrong token)
  2  a pull request opens      -> the agent scans QA, the policy engine decides, the agent explains
  3  the gate says no          -> staging is closed while QA has blocking findings
  4  the developer fixes QA    -> a push; the agent must RE-SCAN QA (verify_fix) and the old findings must close
  5  the QA reviewer approves  -> security is scanned by plain code; the agent explains what it found
  6  exceptions                -> allowed only for a "medium" finding, never for a "high" one
  7  the developer fixes security -> a push; QA AND security must both be re-scanned on the new commit
  8  the security reviewer approves -> the gate opens for exactly that commit, and for no other
  9  a new push after the approval -> the gate closes again until the new commit is checked
  10 the history chain is intact

How to "fix" the code: pass --on-fix-qa / --on-fix-security with a command that does it, or leave them out and
the script pauses and asks you to do it by hand (then press Enter).

The steps assume the demo app: QA has blocking findings first, security has blocking findings after QA is approved.
What the AGENT did in each step is printed too, because the agent is a language model and may choose differently.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import uuid

import httpx


class Failed(Exception):
    pass


class Walk:
    def __init__(self, args):
        self.url = args.url.rstrip("/")
        self.token = os.environ.get("API_TOKEN", "")
        self.release = args.release
        self.args = args
        self.client = httpx.Client(timeout=args.http_timeout)
        self.results: list[tuple[str, bool, str]] = []
        self.commit = ""
        self.runs_before_approval = 0

    # ---- plumbing ----
    def call(self, method: str, path: str, *, token: bool = True, **kw) -> httpx.Response:
        headers = {"X-API-Token": self.token} if token else {}
        return self.client.request(method, f"{self.url}{path}", headers=headers, **kw)

    def get(self, path: str, **kw):
        resp = self.call("GET", path, **kw)
        if resp.status_code != 200:
            raise Failed(f"GET {path} -> HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def history(self) -> list[dict]:
        resp = self.call("GET", f"/releases/{self.release}/history")
        if resp.status_code == 404:  # the release does not exist until the first event creates it
            return []
        if resp.status_code != 200:
            raise Failed(f"GET history -> HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def agent_runs(self) -> list[dict]:
        return [e for e in self.history() if e["event"] == "agent_run"]

    def status(self) -> dict:
        return self.get(f"/releases/{self.release}/status")

    def findings(self, stage: str) -> list[dict]:
        return self.get(f"/releases/{self.release}/findings", params={"stage": stage})

    def gate(self, commit: str, target: str) -> dict:
        return self.get("/gate", params={"release_id": self.release, "commit": commit, "target": target})

    def wait_agent(self, runs_before: int, what: str) -> list[dict]:
        """Waits for a new agent run, then until the history stops growing (the agent may run again)."""
        deadline, started = time.time() + self.args.timeout, time.time()
        while time.time() < deadline:
            if len(self.agent_runs()) > runs_before:
                break
            time.sleep(2)
        else:
            raise Failed(f"the agent did not finish within {self.args.timeout}s after: {what}")
        last, stable_since = -1, time.time()
        while time.time() - stable_since < 4 and time.time() < deadline:
            size = len(self.history())
            if size != last:
                last, stable_since = size, time.time()
            time.sleep(1)
        runs = self.agent_runs()[runs_before:]
        print(f"      agent finished in {time.time() - started:.0f}s: " + "; ".join(self.describe(r) for r in runs))
        return runs

    @staticmethod
    def describe(run: dict) -> str:
        d = run["data"]
        tools = ", ".join(f"{k}x{v}" for k, v in sorted((d.get("tools") or {}).items())) or "no tools"
        return f"[{d.get('event')}] stopped={d.get('stopped')} steps={d.get('steps')} tools: {tools}" + (
            f" ERROR: {d.get('error')}" if d.get("error") else "")

    def rescans(self, commit: str) -> dict[str, dict]:
        """stage -> the rescan history entry for this commit (what the verifier did)."""
        return {e["data"]["stage"]: e["data"] for e in self.history() if e["event"] == "rescan" and e["data"].get("commit") == commit}

    def fix(self, which: str) -> None:
        cmd = getattr(self.args, f"on_fix_{which}")
        if cmd:
            print(f"      fixing the code: {cmd}")
            if subprocess.run(cmd, shell=True).returncode != 0:
                raise Failed(f"the fix command failed: {cmd}")
        else:
            input(f"      >>> Fix the {which.upper()} problems in the demo app now, then press Enter... ")

    def push(self, why: str) -> tuple[str, int]:
        """A new commit arrives (what GitHub's webhook does). Returns the commit and the agent runs seen before."""
        before = len(self.agent_runs())
        self.commit = uuid.uuid4().hex[:12]
        resp = self.call("POST", f"/releases/{self.release}/events", json={"event": "push", "commit": self.commit})
        if resp.status_code != 202:
            raise Failed(f"push event -> HTTP {resp.status_code}: {resp.text[:200]}")
        return self.commit, before

    # ---- steps ----
    def step(self, name: str, fn) -> bool:
        print(f"\n[{len(self.results) + 1}] {name}")
        try:
            detail = fn() or ""
            self.results.append((name, True, detail))
            print(f"    PASS {detail}")
            return True
        except Failed as e:
            self.results.append((name, False, str(e)))
            print(f"    FAIL {e}")
            return False
        except httpx.TimeoutException:
            msg = (f"the server did not answer within {self.args.http_timeout}s. It may be blocked while an agent run is "
                   f"in progress (the model call is not run off the server's event loop); try --http-timeout 300")
            self.results.append((name, False, msg))
            print(f"    FAIL {msg}")
            return False
        except httpx.HTTPError as e:
            self.results.append((name, False, f"network error: {e}"))
            print(f"    FAIL network error: {e}")
            return False

    def s_door(self):
        if self.call("GET", "/health", token=False).status_code != 200:
            raise Failed("/health should be open")
        no_token = self.call("GET", "/releases", token=False).status_code
        wrong = self.client.get(f"{self.url}/releases", headers={"X-API-Token": "definitely-wrong"}).status_code
        if (no_token, wrong) != (401, 401):
            raise Failed(f"without a token or with a wrong one the API must answer 401, got {no_token} and {wrong}")
        if not self.token:
            raise Failed("set the API_TOKEN environment variable to the API's token")
        resp = self.call("GET", "/releases")
        if resp.status_code != 200:
            raise Failed(f"with the right token GET /releases gave HTTP {resp.status_code}")
        return "locked without a token, open with it"

    def explained(self, stage: str) -> str:
        open_ = [f for f in self.findings(stage) if f["status"] == "open"]
        missing = [f["fingerprint"] for f in open_ if not f.get("explanation")]
        bad = [f["fingerprint"] for f in open_ if f.get("explanation") and (
            "`" in f["explanation"]["text"] or f["explanation"].get("source") != "Yaqidh")]
        if missing:
            raise Failed(f"{len(missing)} of {len(open_)} open {stage} findings have no explanation: {', '.join(missing[:4])}")
        if bad:
            raise Failed(f"explanations with code or a wrong source: {', '.join(bad[:4])}")
        return f"all {len(open_)} open {stage} findings are explained"

    def s_open_pr(self):
        before = len(self.agent_runs())
        self.commit = uuid.uuid4().hex[:12]
        resp = self.call("POST", f"/releases/{self.release}/events", json={"event": "pull_request_opened", "commit": self.commit})
        if resp.status_code != 202:
            raise Failed(f"event -> HTTP {resp.status_code}: {resp.text[:200]}")
        runs = self.wait_agent(before, "the pull request opened")
        # Judge by what the history recorded, not by who did it: the agent or plain code may run the scan.
        events = self.history()
        if not [e for e in events if e["event"] == "scan" and e["data"].get("stage") == "qa"]:
            tools = sorted({t for r in runs for t in (r["data"].get("tools") or {})})
            raise Failed(f"QA was never scanned (no 'scan' in the history); the agent called: {tools or 'nothing'}")
        if not [e for e in events if e["event"] == "policy_decision" and e["data"].get("stage") == "qa"]:
            raise Failed("QA was scanned but the policy engine never gave a decision")
        st = self.status()
        if st["status"] != "qa_blocked":
            raise Failed(f"expected qa_blocked (the demo app has planted QA defects), got {st['status']}: {st['reasons']}")
        return self.explained("qa") + f"; status {st['status']}"

    def s_gate_closed(self):
        g = self.gate(self.commit, "staging")
        if g["allowed"]:
            raise Failed(f"staging must be closed while QA is blocked, the gate said: {g}")
        return f"closed ({g['reason']})"

    def s_fix_qa(self):
        old = {f["fingerprint"] for f in self.findings("qa") if f["status"] == "open"}
        self.fix("qa")
        commit, before = self.push("a fix for QA")
        runs = self.wait_agent(before, "the QA fix was pushed")
        r = self.rescans(commit).get("qa")
        if r is None:
            g = self.gate(commit, "staging")
            raise Failed(f"QA was NOT re-scanned on the new commit (the agent called: "
                         f"{sorted({t for x in runs for t in (x['data'].get('tools') or {})})}); gate says {g['reason']}")
        still = [fp for fp in old if fp not in set(r.get("closed", []))]
        st = self.status()
        if still:
            raise Failed(f"{len(still)} QA findings did not close ({still[:3]}); status {st['status']}")
        if st["status"] != "awaiting_qa_approval":
            raise Failed(f"expected awaiting_qa_approval, got {st['status']}: {st['reasons']}")
        return f"{len(r.get('closed', []))} findings closed by the verifier; status {st['status']}"

    def s_approve_qa(self):
        self.runs_before_approval = len(self.agent_runs())  # the 'approved' agent run is the next one to appear
        resp = self.call("POST", f"/releases/{self.release}/stages/qa/approve",
                         json={"by": self.args.qa_reviewer, "reason": "walkthrough"})
        if resp.status_code != 200:
            raise Failed(f"approve QA -> HTTP {resp.status_code}: {resp.text[:300]}")
        st = resp.json()
        if not st.get("can_merge_to_staging"):
            raise Failed(f"after the QA approval staging should be open, got: {st}")
        return f"approved; status {st['status']}; staging is open"

    def s_security_explained(self):
        self.wait_agent(self.runs_before_approval, "the QA approval")  # the agent explains security's findings
        st = self.status()
        if st["status"] not in ("security_blocked", "awaiting_security_approval"):
            raise Failed(f"security should have been scanned by now, status is {st['status']}: {st['reasons']}")
        if not self.findings("security"):
            raise Failed("security has no findings at all; this walkthrough expects the demo app's planted ones")
        return self.explained("security") + f"; status {st['status']}"

    def s_exceptions(self):
        open_ = [f for f in self.findings("security") if f["status"] == "open"]
        high = next((f for f in open_ if f["reported_as"] == "high"), None)
        medium = next((f for f in open_ if f["reported_as"] == "medium"), None)
        if not high or not medium:
            raise Failed(f"need one high and one medium finding to test exceptions (found reported_as: "
                         f"{sorted({f['reported_as'] for f in open_})})")
        body = {"justification": "walkthrough: accepted for the test", "approved_by": self.args.security_reviewer}
        before = self.status()
        self.call("POST", f"/releases/{self.release}/stages/security/exceptions", json={**body, "fingerprint": high["fingerprint"]})
        after_high = self.status()
        if after_high["reasons"] == ["no blocking findings"] or "no blocking" in " ".join(after_high["reasons"]):
            raise Failed("an exception on a HIGH finding was accepted, it must never count")
        resp = self.call("POST", f"/releases/{self.release}/stages/security/exceptions", json={**body, "fingerprint": medium["fingerprint"]})
        if resp.status_code != 200:
            raise Failed(f"exception on a medium finding -> HTTP {resp.status_code}: {resp.text[:200]}")
        return f"high ignored, medium accepted (status {before['status']} -> {self.status()['status']})"

    def s_fix_security(self):
        self.fix("security")
        commit, before = self.push("a fix for security")
        runs = self.wait_agent(before, "the security fix was pushed")
        done = self.rescans(commit)
        missing = [s for s in ("qa", "security") if s not in done]
        if missing:
            g = self.gate(commit, "main")
            tools = sorted({t for x in runs for t in (x["data"].get("tools") or {})})
            raise Failed(f"{' and '.join(missing)} was NOT re-scanned on the new commit (agent called: {tools}); "
                         f"the gate says {g['reason']}: {g['detail']}")
        st = self.status()
        if st["status"] != "awaiting_security_approval":
            raise Failed(f"expected awaiting_security_approval, got {st['status']}: {st['reasons']}")
        return f"both stages re-scanned on {commit}; status {st['status']}"

    def s_approve_security(self):
        resp = self.call("POST", f"/releases/{self.release}/stages/security/approve",
                         json={"by": self.args.security_reviewer, "reason": "walkthrough"})
        if resp.status_code != 200:
            raise Failed(f"approve security -> HTTP {resp.status_code}: {resp.text[:300]}")
        ok = self.gate(self.commit, "main")
        if not ok["allowed"]:
            raise Failed(f"main should be open for the approved commit, the gate said: {ok}")
        other = self.gate("0000deadbeef", "main")
        if other["allowed"] or other["reason"] != "stale_commit":
            raise Failed(f"another commit must get stale_commit, got: {other}")
        return f"main open for {self.commit} only ({other['reason']} for any other)"

    def s_new_push(self):
        commit, before = self.push("a new commit after the approval")
        self.wait_agent(before, "a new push after the approval")
        g = self.gate(commit, "main")
        st = self.status()
        if g["allowed"]:
            raise Failed(f"main must close after a new commit until it is checked again, the gate said: {g}")
        staging = self.gate(commit, "staging")
        return f"main closed ({g['reason']}); status {st['status']}; staging {'open' if staging['allowed'] else 'closed: ' + staging['reason']}"

    def s_history(self):
        v = self.get(f"/releases/{self.release}/history/verify")
        if not v.get("ok"):
            raise Failed(f"the history chain is broken: {v}")
        return f"{v['entries']} entries, chain intact"

    def run(self) -> int:
        steps = [
            ("the door is locked", self.s_door),
            ("pull request opens: QA scan, decision, explanations", self.s_open_pr),
            ("the gate refuses staging", self.s_gate_closed),
            ("developer fixes QA: re-scan and closure", self.s_fix_qa),
            ("QA reviewer approves: security starts", self.s_approve_qa),
            ("security results are explained", self.s_security_explained),
            ("exceptions: medium yes, high never", self.s_exceptions),
            ("developer fixes security: QA and security re-scanned", self.s_fix_security),
            ("security reviewer approves: the gate opens for that commit", self.s_approve_security),
            ("a new push closes the gate again", self.s_new_push),
            ("the history chain is intact", self.s_history),
        ]
        print(f"release: {self.release}   api: {self.url}")
        for name, fn in steps:
            if not self.step(name, fn) and not self.args.keep_going:
                print("\nstopped at the first failure (use --keep-going to continue)")
                break
        passed = sum(ok for _, ok, _ in self.results)
        print(f"\n==== {passed}/{len(self.results)} steps passed ({len(steps)} in total) ====")
        for name, ok, detail in self.results:
            if not ok:
                print(f"  FAILED: {name}\n          {detail}")
        return 0 if passed == len(steps) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--release", default=f"walkthrough-{uuid.uuid4().hex[:6]}")
    ap.add_argument("--qa-reviewer", default="walkthrough-qa")
    ap.add_argument("--security-reviewer", default="walkthrough-security")
    ap.add_argument("--on-fix-qa", help="command that fixes the QA problems (otherwise the script pauses for you)")
    ap.add_argument("--on-fix-security", help="command that fixes the security problems")
    ap.add_argument("--timeout", type=int, default=900, help="seconds to wait for each agent run")
    ap.add_argument("--http-timeout", type=int, default=60, help="seconds to wait for one HTTP answer")
    ap.add_argument("--keep-going", action="store_true", help="do not stop at the first failing step")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    return Walk(args).run()


if __name__ == "__main__":
    sys.exit(main())
