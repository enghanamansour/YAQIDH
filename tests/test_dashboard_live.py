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
    monkeypatch.setenv("YAQIDH_DEMO_PASSWORD", "test-demo-password")
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
        assert self.call("POST", "/api/login", {"account": account, "password": "test-demo-password"})[0] == 200
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


def test_the_security_reviewer_accepts_a_medium_finding_in_the_dashboard_but_never_a_high_one(world):
    from src.schema import Severity
    from tests.test_service import finding

    stack, dash, _ = world
    stack.sec.findings = [finding("F-1", Severity.HIGH).model_copy(update={"reported_as": "medium"}),
                          finding("F-2", Severity.HIGH).model_copy(update={"reported_as": "high"})]
    open_pr(stack)
    Browser(dash).login("qa").call("POST", "/api/releases/r1/decision", {"decision": "approve", "reason": "fine", "commit": "aaaaaaa"})
    sec = Browser(dash).login("security")
    view = sec.call("GET", "/api/releases/r1")[1]
    assert view["live"] is True and {f["fingerprint"] for f in view["findings"]} == {"F-1", "F-2"}

    path = "/api/releases/r1/exception"
    assert sec.call("POST", path, {"fingerprints": ["F-1"], "justification": "short"})[0] == 400  # a written reason is required
    assert Browser(dash).login("qa").call("POST", path, {"fingerprints": ["F-1"], "justification": "a long enough reason"})[0] == 403
    assert sec.call("POST", path, {"fingerprints": ["F-1", "F-2"], "justification": "a long enough reason"})[0] == 409  # high: never
    assert stack.service.store.get("r1").stage(__import__("src.schema", fromlist=["StageName"]).StageName.SECURITY).findings[1].exception is None

    status, after = sec.call("POST", path, {"fingerprints": ["F-1"], "justification": "isolated, fix scheduled next sprint"})
    assert status == 200
    f1 = next(f for f in after["findings"] if f["fingerprint"] == "F-1")
    assert f1["status"] == "excepted" and f1["exception"]["approved_by"] == "security"  # recorded under the account, not typed
    assert next(f for f in after["findings"] if f["fingerprint"] == "F-2")["status"] == "open"


def _page_after_login(browser, dash, account):
    ctx = browser.new_context(locale="en-US")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{dash.server_port}/login")
    page.fill("input[name=account]", account)
    page.fill("input[name=password]", "test-demo-password")
    page.click("form#sign-in button")
    page.wait_for_url("**/dashboard", timeout=10000)
    page.wait_for_timeout(1500)
    return page, errors


def test_the_real_pages_render_for_the_developer_and_the_security_reviewer(world):
    """Opens the real dashboard in a browser: no script error, the report and the exception form are on the page."""
    playwright = pytest.importorskip("playwright.sync_api")
    from src.schema import Severity
    from tests.test_service import finding

    stack, dash, _ = world
    stack.sec.findings = [finding("F-1", Severity.HIGH).model_copy(update={"reported_as": "medium"}),
                          finding("F-2", Severity.HIGH).model_copy(update={"reported_as": "high"})]
    open_pr(stack)
    Browser(dash).login("qa").call("POST", "/api/releases/r1/decision", {"decision": "approve", "reason": "fine", "commit": "aaaaaaa"})
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page, errors = _page_after_login(browser, dash, "developer")
        text = page.inner_text("body")
        assert errors == [] and "تقرير البناء" in text and "ملاحظات وُجدت" in text and "تمنع الدمج الآن" in text

        page, errors = _page_after_login(browser, dash, "security")
        assert errors == [] and "الملاحظات المتوسطة" in page.inner_text("body") and page.locator("form#exception-form input[name=finding]").count() == 1
        # the approve button is always there; while findings block it is disabled and says why
        assert page.locator("button.big.good[disabled]").count() == 1
        assert "تمنع الدمج" in page.locator(".result-actions .why").first.inner_text()
        assert page.locator("form#exception-form").count() == 1  # only the medium one, never the high
        page.fill("form#exception-form textarea", "isolated component, fix is scheduled")
        page.click("form#exception-form button")
        page.wait_for_timeout(1500)
        assert "مقبولة سابقًا" in page.inner_text("body")
        browser.close()
    assert stack.service.store.get("r1").stage(__import__("src.schema", fromlist=["StageName"]).StageName.SECURITY).findings[0].exception


def test_a_private_page_never_flashes_the_login_form_while_it_loads(world):
    """Opening /communication or /exceptions after login must not show the sign-in form for a moment."""
    playwright = pytest.importorskip("playwright.sync_api")
    stack, dash, _ = world
    open_pr(stack)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page, _ = _page_after_login(browser, dash, "developer")
        for path in ("/communication", "/exceptions", "/dashboard"):
            page.add_init_script("window.__sawLogin=false;new MutationObserver(()=>{if(document.querySelector('#sign-in'))window.__sawLogin=true}).observe(document,{childList:true,subtree:true})")
            page.goto(f"http://127.0.0.1:{dash.server_port}{path}")
            page.wait_for_timeout(1500)
            assert page.evaluate("window.__sawLogin") is False, path
            assert page.locator("form#sign-in").count() == 0, path
        browser.close()
