"""The dashboard in live mode, against the real Yaqidh API over HTTP (both run in threads, no network outside this machine)."""

import http.client
import importlib.util
import json
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from src.api.app import create_app
from src.schema import StageName
from tests.test_http_api import H, Stack  # noqa: F401

PREVIEW = Path(__file__).resolve().parents[1] / "frontend-preview"
C1 = "a" * 40


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "secret")
    # the tests use the built-in demo password and local host rules, whatever the machine's environment says
    monkeypatch.delenv("YAQIDH_DEMO_PASSWORD", raising=False)
    monkeypatch.delenv("YAQIDH_ALLOWED_HOSTS", raising=False)
    stack = Stack(tmp_path)
    api_port = free_port()
    api = uvicorn.Server(uvicorn.Config(create_app(stack.service, stack.history, stack.agent), host="127.0.0.1",
                                        port=api_port, log_level="error"))
    threading.Thread(target=api.run, daemon=True).start()
    for _ in range(100):
        if api.started:
            break
        time.sleep(0.05)

    monkeypatch.setattr(sys, "argv", ["server.py", "--live"])
    monkeypatch.syspath_prepend(str(PREVIEW))
    spec = importlib.util.spec_from_file_location("dashboard_server", PREVIEW / "server.py")
    server_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_mod)
    import live as live_mod

    backend = live_mod.LiveBackend(f"http://127.0.0.1:{api_port}", "secret", server_mod.Evidence, owners=["developer"])
    policy = server_mod.load_policy(Path(__file__).resolve().parents[1] / "config" / "policy.yaml")
    dash = server_mod.DemoServer(("127.0.0.1", 0), live_mod.LiveStore(backend), {}, policy, backend)
    dash.server_mod = server_mod
    threading.Thread(target=dash.serve_forever, daemon=True).start()
    yield stack, dash, api_port
    dash.shutdown()
    dash.server_close()
    api.should_exit = True
    sys.modules.pop("live", None)


class Browser:
    def __init__(self, dash):
        self.port, self.cookie = dash.server_port, None

    def call(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        headers = {"Origin": f"http://127.0.0.1:{self.port}", "Content-Type": "application/json"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        conn.request(method, path, json.dumps(body) if body is not None else None, headers)
        resp = conn.getresponse()
        data = resp.read()
        if resp.getheader("Set-Cookie") and "Max-Age=0" not in resp.getheader("Set-Cookie"):
            self.cookie = resp.getheader("Set-Cookie").split(";")[0]
        return resp.status, (json.loads(data) if data else None)

    def login(self, account):
        assert self.call("POST", "/api/login", {"account": account, "password": "YaqidhDemo-2026"})[0] == 200
        return self


def open_pr(stack):
    """What GitHub + the agent do: a pull request arrives, QA is scanned and passes."""
    stack.service.set_head_commit("r1", C1)
    stack.service.set_pull_request("r1", "o/n", 42, author="developer", branch="feature/42")
    stack.service.run_scan("r1", "qa")
    stack.service.evaluate_policy("r1", "qa")


def test_the_dashboard_shows_the_real_release_to_the_right_people(world):
    stack, dash, _ = world
    open_pr(stack)
    status, board = Browser(dash).login("qa").call("GET", "/api/dashboard")
    row = next(r for r in board["releases"] if r["id"] == "r1")
    assert status == 200 and row["pr"] == 42 and row["commit"] == "aaaaaaa" and row["active"] == "qa"
    assert row["outcome"] == "pass" and row["pendingReview"] is True
    # the release belongs to developer; security has nothing to review yet
    assert [r["id"] for r in Browser(dash).login("security").call("GET", "/api/dashboard")[1]["releases"]] == []
    assert Browser(dash).login("security").call("GET", "/api/releases/r1")[0] == 403
    dev = Browser(dash).login("developer").call("GET", "/api/releases/r1")[1]
    assert dev["canApprove"] is False and dev["branch"] == "feature/42"


def test_a_qa_approval_in_the_dashboard_reaches_the_api_and_starts_the_security_stage(world):
    stack, dash, _ = world
    open_pr(stack)
    qa = Browser(dash).login("qa")
    view = qa.call("GET", "/api/releases/r1")[1]
    assert view["canApprove"] and view["outcome"]["result"] == "pass"
    status, after = qa.call("POST", "/api/releases/r1/decision", {"decision": "approve", "reason": "checked it", "commit": view["commit"]})
    assert status == 200 and after["canApprove"] is False
    decision = stack.service.store.get("r1").human_decisions[-1]
    assert (decision.stage.value, decision.decision, decision.by) == ("qa", "approve", "qa")  # recorded in the API, by the account
    sec = Browser(dash).login("security").call("GET", "/api/releases/r1")[1]
    assert sec["stage"] == "security" and sec["outcome"]["result"] == "fail" and sec["blockerIds"]
    assert sec["canApprove"] is False  # policy failed, nothing to approve


def test_the_dashboard_cannot_approve_what_the_api_says_is_not_ready(world):
    stack, dash, _ = world
    open_pr(stack)
    qa = Browser(dash).login("qa")
    assert qa.call("POST", "/api/releases/r1/decision", {"decision": "approve", "reason": "x" * 5, "commit": "wrong00"})[0] == 409
    assert qa.call("POST", "/api/releases/r1/decision", {"decision": "approve", "reason": "ab", "commit": "aaaaaaa"})[0] == 400
    assert stack.service.store.get("r1").human_decisions == []
    qa.call("POST", "/api/releases/r1/decision", {"decision": "approve", "reason": "fine", "commit": "aaaaaaa"})
    again = qa.call("POST", "/api/releases/r1/decision", {"decision": "approve", "reason": "fine", "commit": "aaaaaaa"})
    assert again[0] == 403  # QA is no longer the active stage for this release


def test_a_rejection_goes_to_the_api_and_the_developer_sees_the_reason(world):
    stack, dash, _ = world
    open_pr(stack)
    qa = Browser(dash).login("qa")
    assert qa.call("POST", "/api/releases/r1/decision", {"decision": "reject", "reason": "please recheck login", "commit": "aaaaaaa"})[0] == 200
    dev = Browser(dash).login("developer").call("GET", "/api/dashboard")[1]["releases"][0]
    assert dev["returnReason"] == "please recheck login"
    assert stack.service.store.get("r1").human_decisions[-1].decision == "reject"


def test_when_the_api_is_down_the_dashboard_shows_nothing_instead_of_stale_data(world):
    stack, dash, _ = world
    open_pr(stack)
    dash.live.base_url = "http://127.0.0.1:9"  # nothing listens here
    status, board = Browser(dash).login("qa").call("GET", "/api/dashboard")
    assert status == 200 and board["releases"] == []


def test_the_demo_mode_still_works_unchanged(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["server.py"])
    monkeypatch.setattr(sys, "path", list(sys.path))  # the demo adds its own backend copy to the path; undo that afterwards
    spec = importlib.util.spec_from_file_location("dashboard_demo", PREVIEW / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "portal-133" in mod.RELEASES  # the seeded demo data is still there


def test_the_release_view_carries_the_history_and_the_new_finding_fields(world):
    stack, dash, _ = world
    stack.sec.findings = [stack.sec.findings[0].model_copy(update={"fixed_version": "2.0.1", "cwe": "CWE-400", "confidence": "low"})]
    open_pr(stack)
    stack.service.add_human_decision("r1", "qa", "approve", "Sara", "")
    stack.service.run_scan("r1", "security")
    sec = Browser(dash).login("security").call("GET", "/api/releases/r1")[1]
    f = sec["findings"][0]
    assert (f["fixed_version"], f["cwe"], f["confidence"]) == ("2.0.1", "CWE-400", "low")
    log = sec["log"]
    assert log["verified"]["ok"] is True and log["verified"]["entries"] == len(log["entries"])
    assert [e["event"] for e in log["entries"]][:2] == ["commit_received", "scan"]
    assert all("text" not in e["data"] for e in log["entries"])  # long texts stay out of the dashboard payload


def test_a_tampered_history_is_shown_as_broken(world, tmp_path):
    stack, dash, _ = world
    open_pr(stack)
    path = stack.history.directory / "r1.jsonl"
    lines = path.read_text().splitlines()
    first = json.loads(lines[0])
    first["data"]["commit"] = "evil"
    lines[0] = json.dumps(first)
    path.write_text("\n".join(lines) + "\n")
    view = Browser(dash).login("qa").call("GET", "/api/releases/r1")[1]
    assert view["log"]["verified"]["ok"] is False and view["log"]["verified"]["broken_at"] == 1


def test_with_no_real_releases_every_number_is_zero_and_nothing_is_seeded(world):
    stack, dash, _ = world
    for account in ("developer", "qa", "security", "company-admin"):
        b = Browser(dash).login(account)
        board = b.call("GET", "/api/dashboard")[1]
        assert board.get("releases", []) == [] and board.get("runSummary", []) == [], account
        assert b.call("GET", "/api/threads")[1] == [], account
        if account == "company-admin":
            assert board.get("requests", []) == []  # no demo "pending account request" either


def test_a_wrong_api_token_is_reported_instead_of_showing_an_empty_dashboard(world):
    stack, dash, _ = world
    open_pr(stack)
    dash.live.token = "not-the-real-token"
    board = Browser(dash).login("qa").call("GET", "/api/dashboard")[1]
    assert board["releases"] == [] and "token" in board["liveError"]
    dash.live.token = "secret"
    board = Browser(dash).login("qa").call("GET", "/api/dashboard")[1]
    assert board["liveError"] == "" and len(board["releases"]) == 1


def test_an_unreachable_api_is_reported_too(world):
    stack, dash, _ = world
    dash.live.base_url = "http://127.0.0.1:9"
    board = Browser(dash).login("qa").call("GET", "/api/dashboard")[1]
    assert board["releases"] == [] and "not reachable" in board["liveError"]


# --- release status and merge, readable titles, and granting an exception from the dashboard ---

def ready_for_security(stack, findings):
    stack.sec.findings = findings
    open_pr(stack)
    stack.service.add_human_decision("r1", "qa", "approve", "Sara", "")
    stack.service.run_scan("r1", "security")
    stack.service.evaluate_policy("r1", "security")


def test_the_view_says_whether_merging_is_allowed_and_gives_readable_titles(world):
    stack, dash, _ = world
    f = stack.sec.findings[0].model_copy(update={"tool": "semgrep", "rule": "python.flask.security.audit.debug-enabled"})
    t = stack.sec.findings[0].model_copy(update={"fingerprint": "F-2", "tool": "trivy", "rule": "CVE-1", "detail": "Denial of service"})
    ready_for_security(stack, [f, t])
    view = Browser(dash).login("security").call("GET", "/api/releases/r1")[1]
    assert view["gate"]["status"] == "security_blocked" and view["gate"]["staging"] is True and view["gate"]["main"] is False
    assert {x["title"] for x in view["findings"]} == {"debug enabled", "CVE-1: Denial of service"}
    assert Browser(dash).login("security").call("GET", "/api/dashboard")[1]["live"] is True


def test_a_security_reviewer_can_grant_an_exception_for_a_medium_finding_only(world):
    stack, dash, _ = world
    medium = stack.sec.findings[0].model_copy(update={"fingerprint": "F-m", "reported_as": "medium"})
    high = stack.sec.findings[0].model_copy(update={"fingerprint": "F-h", "reported_as": "high"})
    ready_for_security(stack, [medium, high])
    sec = Browser(dash).login("security")
    view = sec.call("GET", "/api/releases/r1")[1]
    assert view["exceptionEligible"] == ["F-m"]
    assert sec.call("POST", "/api/releases/r1/exception", {"fingerprint": "F-h", "justification": "legacy code"})[0] == 409
    assert sec.call("POST", "/api/releases/r1/exception", {"fingerprint": "F-m", "justification": "ab"})[0] == 400
    status, after = sec.call("POST", "/api/releases/r1/exception", {"fingerprint": "F-m", "justification": "legacy, fix planned"})
    assert status == 200
    saved = {f.fingerprint: f for f in stack.service.store.get("r1").stage(StageName.SECURITY).findings}
    assert saved["F-m"].status.value == "excepted" and saved["F-m"].exception.approved_by == "security"
    assert saved["F-h"].status.value == "open"  # the high finding still blocks


def test_only_the_security_reviewer_may_grant_exceptions(world):
    stack, dash, _ = world
    medium = stack.sec.findings[0].model_copy(update={"fingerprint": "F-m", "reported_as": "medium"})
    ready_for_security(stack, [medium])
    for account in ("qa", "developer"):
        assert Browser(dash).login(account).call("POST", "/api/releases/r1/exception", {"fingerprint": "F-m", "justification": "because"})[0] == 403
    assert stack.service.store.get("r1").stage(StageName.SECURITY).findings[0].status.value == "open"


def test_a_review_request_answer_from_the_dashboard_reaches_the_api(world):
    stack, dash, _ = world
    ready_for_security(stack, stack.sec.findings)
    dash.live.record_review_request("r1", {"request_id": "t9", "commit": C1, "finding": "F-1", "kind": "deadline", "status": "approved",
                                           "by": "security", "reason": "more time", "approved_deadline": "2026-11-20"})
    saved = stack.service.store.get("r1").review_request_decisions
    assert [(d.kind, d.status, d.by) for d in saved] == [("deadline", "approved", "security")]


# --- the QA page shows every check, not only the failed ones ---

def test_the_qa_view_lists_every_check_with_its_result(world):
    stack, dash, _ = world
    stack.qa.findings = [stack.sec.findings[0].model_copy(update={"fingerprint": "F-q", "tool": "playwright",
                                                                  "rule": "search_resists_sql_injection"})]
    open_pr(stack)
    view = Browser(dash).login("qa").call("GET", "/api/releases/r1")[1]
    checks = {c["id"]: c for c in view["qaChecks"]}
    assert len(checks) == 14
    assert checks["search_resists_sql_injection"]["state"] == "failed" and checks["search_resists_sql_injection"]["finding"] == "F-q"
    assert {c["state"] for k, c in checks.items() if k != "search_resists_sql_injection"} == {"passed"}
    assert checks["cart_requires_login"]["titleAr"] and checks["cart_requires_login"]["descEn"]


def test_a_fixed_check_is_shown_as_fixed(world):
    from src.scanning import ScanResult

    stack, dash, _ = world
    stack.service.runners[StageName.QA] = lambda target: ScanResult(list(stack.qa.findings), {"playwright": "1"}, {"playwright"}, set())
    stack.qa.findings = [stack.sec.findings[0].model_copy(update={"fingerprint": "F-q", "tool": "playwright", "rule": "cart_requires_login"})]
    open_pr(stack)
    stack.qa.findings = []
    stack.service.set_head_commit("r1", "b" * 40)
    stack.service.verify_fix("r1", "qa")
    view = Browser(dash).login("qa").call("GET", "/api/releases/r1")[1]
    assert {c["id"]: c["state"] for c in view["qaChecks"]}["cart_requires_login"] == "fixed"
    assert sum(1 for c in view["qaChecks"] if c["state"] == "passed") == 13


def test_the_pages_for_the_role_are_served(world):
    stack, dash, _ = world
    import urllib.request
    for path in ("/pages/dashboard/qa.js", "/pages/dashboard/review.js", "/app.js", "/style.css"):
        assert urllib.request.urlopen(f"http://127.0.0.1:{dash.server_port}{path}").status == 200


def post(dash, host, origin, body, extra=None):
    conn = http.client.HTTPConnection("127.0.0.1", dash.server_port)
    headers = {"Host": host, "Content-Type": "application/json", **({"Origin": origin} if origin else {}), **(extra or {})}
    conn.request("POST", "/api/login", json.dumps(body), headers)
    resp = conn.getresponse()
    resp.read()
    return resp.status, resp.getheader("Set-Cookie")


def test_a_public_host_works_only_when_it_is_listed_and_the_origin_matches(world):
    _, dash, _ = world
    mod = dash.server_mod
    login = {"account": "developer", "password": "YaqidhDemo-2026"}
    # not listed: refused, even with a matching origin
    assert post(dash, "demo.example.test", "https://demo.example.test", login)[0] == 403
    assert post(dash, "demo.example.test", "http://demo.example.test", login)[0] == 403
    if True:
        mod.ALLOWED_HOSTS.add("demo.example.test")
        try:
            status, cookie = post(dash, "demo.example.test", "https://demo.example.test", login, {"X-Forwarded-Proto": "https"})
            assert status == 200 and "Secure" in cookie and "HttpOnly" in cookie
            # a foreign origin on a listed host is still refused
            assert post(dash, "demo.example.test", "https://evil.example", login)[0] == 403
            # an unlisted host is still refused
            assert post(dash, "evil.example", "https://evil.example", login)[0] == 403
        finally:
            mod.ALLOWED_HOSTS.discard("demo.example.test")


def test_the_demo_endpoints_are_off_unless_demo_mode_is_on(world):
    _, dash, _ = world
    browser = Browser(dash)
    assert browser.call("GET", "/api/demo/info")[1]["enabled"] is False
    assert browser.call("POST", "/api/demo/enter", {"role": "developer"})[0] == 404
    assert browser.call("POST", "/api/demo/push", {})[0] == 401


def test_the_replay_player_walks_the_recorded_states_in_order(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(PREVIEW))
    from demo import DemoPlayer

    calls = []

    class Fake:
        def _call(self, method, path, body=None):
            calls.append((path.rsplit("/", 1)[-1], (body or {}).get("event") or (body or {}).get("stage"), (body or {}).get("commit")))

    fixtures = tmp_path / "fixtures.json"
    fixtures.write_text(json.dumps({"qa": [{"findings": []}] * 3, "security": [{"findings": []}] * 2}), encoding="utf-8")
    player = DemoPlayer(Fake(), fixtures)
    player.start()
    assert calls == [] and player.guide("")["status"] == "none"  # a clean slate: no pull request yet
    assert player.can_push("")
    player.push("")  # the developer's first push opens the pull request and QA fails
    assert [c[:2] for c in calls] == [("events", "pull_request_opened"), ("scan-results", "qa")]
    assert player.guide("qa_blocked")["status"] == "qa_blocked"
    assert player.can_push("qa_blocked") and not player.can_push("awaiting_qa_approval")
    calls.clear()
    player.push("qa_blocked")  # the developer's QA fix: QA results, and the security results wait for their turn
    assert player.phase == 1 and [c[:2] for c in calls] == [("events", "push"), ("scan-results", "qa"), ("scan-results", "security")]
    assert len({c[2] for c in calls}) == 1  # one new commit for the whole push
    player.push("security_blocked")  # the security fix
    assert player.phase == 2
    assert not player.can_push("security_blocked")  # nothing left to fix: the security reviewer decides on the medium finding
    assert player.can_push("security_rejected")  # a returned request can be pushed again
    before = player.phase
    player.push("security_rejected")
    assert player.phase == before
