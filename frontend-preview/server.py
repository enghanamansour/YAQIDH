"""Local, authenticated role preview using the supplied YAQIDH backend."""
import argparse
import hashlib
import hmac
import os
import re
import json
import secrets
import sys
import tempfile
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
# Live mode uses the real project code in the repository root; the demo uses the copy in ./backend.
LIVE = "--live" in sys.argv
sys.path.insert(0, str(ROOT.parent if LIVE else ROOT / "backend"))
from src.policy import evaluate_policy, load_policy
from src.schema import Evidence, ExceptionRecord, Finding, HumanDecision, ReviewRequestDecision, StageRecord
from src.storage import EvidenceStore
from src.verifier import verify

PASSWORD = "YaqidhDemo-2026"
ACCOUNTS = {
    "developer": {"role": "developer", "projects": ["portal"], "active": True},
    "qa": {"role": "qa", "projects": ["portal"], "active": True, "display": "سما"},
    "security": {"role": "security", "projects": ["portal"], "active": True},
    "company-admin": {"role": "company-admin", "projects": ["portal", "research"], "active": True},
}
RELEASES = {
    "portal-128": dict(project="portal", owner="developer", pr=42, build=128, commit="a3f82c1", branch="staging", active="security"),
    "portal-129": dict(project="portal", owner="developer", pr=42, build=129, commit="a3f82d2", branch="staging", active="security"),
    "portal-130": dict(project="portal", owner="developer", pr=43, build=130, commit="a3f82e3", branch="feature/43", active="qa"),
    "portal-131": dict(project="portal", owner="developer", pr=44, build=131, commit="a3f82f4", branch="staging", active="security"),
    "portal-132": dict(project="portal", owner="developer", pr=45, build=132, commit="a3f8305", branch="feature/45", active="qa"),
    "portal-133": dict(project="portal", owner="developer", pr=46, build=133, commit="a3f8316", branch="feature/46", active="qa"),
    "portal-134": dict(project="portal", owner="developer", pr=47, build=134, commit="a3f8327", branch="staging", active="security"),
    "portal-135": dict(project="portal", owner="developer", pr=48, build=135, commit="a3f8338", branch="staging", active="security"),
    "private-200": dict(project="private", owner="other", pr=88, build=200, commit="bd64fe1", branch="staging", active="security"),
}
# The supplied schema has no execution records or commit metadata. These are demo
# sidecars. Production must populate them from immutable CI run identities.
RUNS = {
    key: {"qa": [{"tool": "playwright", "state": "completed", "demo": True}],
          "security": [{"tool": "semgrep", "state": "completed", "demo": True},
                       {"tool": "trivy", "state": "completed", "demo": True}]}
    for key in ("portal-128", "portal-129", "portal-131", "portal-134", "portal-135")
}
RUNS["portal-130"] = {"qa": []}
RUNS["portal-131"]["security"][1]["state"] = "error"
RUNS["portal-132"] = {"qa": [{"tool": "playwright", "state": "completed", "demo": True}]}
RUNS["portal-133"] = {"qa": [{"tool": "playwright", "state": "completed", "demo": True}]}
DEMO_RUN_DATES = {"portal-128": "2026-11-04", "portal-129": "2026-11-05",
    "portal-130": "2026-11-05", "portal-131": "2026-11-06", "portal-132": "2026-11-07",
    "portal-133": "2026-11-08", "portal-134": "2026-11-08", "portal-135": "2026-11-09"}
QA_APPROVED = {"portal-128", "portal-129", "portal-131", "portal-134", "portal-135"}
QA_CHECKED = QA_APPROVED | {"portal-132"}
STATIC = {
    "/components/navigation.js": "components/navigation.js",
    "/components/charts.js": "components/charts.js",
    "/components/metric-card.js": "components/metric-card.js",
    "/pages/home.js": "pages/home.js",
    "/pages/about.js": "pages/about.js",
    "/pages/login.js": "pages/login.js",
    "/pages/signup.js": "pages/signup.js",
    "/pages/communication.js": "pages/communication.js",
    "/pages/admin.js": "pages/admin.js",
    "/pages/dashboard/developer.js": "pages/dashboard/developer.js",
    "/pages/dashboard/review.js": "pages/dashboard/review.js",
    "/pages/dashboard/qa.js": "pages/dashboard/qa.js",
    "/pages/dashboard/index.js": "pages/dashboard/index.js",
    "/app.js": "app.js", "/style.css": "style.css",
          "/assets/yaqidh-dark-transparent.png": "assets/yaqidh-dark-transparent.png",
          **{f"/assets/fonts/{p.name}": f"assets/fonts/{p.name}" for p in (ROOT / "web/assets/fonts").glob("*.woff2")},
          "/assets/yaqidh-light-transparent.png": "assets/yaqidh-light-transparent.png"}
MIME = {".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".html": "text/html", ".woff2": "font/woff2", ".svg": "image/svg+xml"}

def seed(store, policy):
    old = [
        Finding(fingerprint="semgrep-demo-001", tool="semgrep", severity="high",
                reported_as="high", location="src/orders.py:42", rule="demo.sql-query",
                explanation={"text": "A query builds SQL from request input. Review the reported location."}),
        Finding(fingerprint="trivy-demo-001", tool="trivy", severity="low",
                reported_as="low", location="requirements.txt", component="demo-lib==1.0",
                rule="DEMO-ADVISORY-01"),
        Finding(fingerprint="trivy-demo-002", tool="trivy", severity="high",
                reported_as="medium", location="requirements.txt", component="legacy-demo==2.0",
                rule="DEMO-ADVISORY-02", status="excepted",
                exception={"justification": "Isolated demo dependency pending replacement.", "approved_by": "Demo reviewer"}),
    ]
    old.append(Finding(fingerprint="trivy-demo-003", tool="trivy", severity="high",
        reported_as="medium", location="requirements.txt", component="demo-support==1.0",
        rule="DEMO-ADVISORY-03"))
    current = [finding.model_copy(deep=True) for finding in old if finding.tool == "trivy" and finding.fingerprint != "trivy-demo-003"]
    verification = verify(old, current, tools_run={"semgrep", "trivy"})
    for key in RELEASES:
        qa = StageRecord(name="qa")
        if key in QA_CHECKED:
            qa.decision = evaluate_policy([], policy)
        if key == "portal-133":
            qa.findings = [Finding(
                fingerprint="playwright-demo-001", tool="playwright", severity="high",
                location="tests/orders.spec.ts:18", rule="demo.order-confirmation",
                explanation={"text": "Demo: the order confirmation did not appear after submission."},
            )]
            qa.decision = evaluate_policy(qa.findings, policy)
        security = StageRecord(name="security")
        decisions = []
        if key in QA_APPROVED:
            decisions.append(HumanDecision(stage="qa", decision="approve", by="Demo QA reviewer",
                                           reason="Fixture: QA checks completed for this commit."))
        if key in {"portal-128", "portal-129"}:
            security.findings = old if key == "portal-128" else verification.findings
            security.decision = evaluate_policy(security.findings, policy)
            security.tool_versions = {"semgrep-rules": "demo-rules", "trivy-db": "demo-db"}
        if key in {"portal-134", "portal-135"}:
            security.decision = evaluate_policy([], policy)
        if key == "portal-133":
            decisions.append(HumanDecision(stage="qa", decision="reject", by="qa", reason="qa-return-demo"))
        if key == "portal-135":
            decisions.append(HumanDecision(stage="security", decision="approve", by="security", reason="ready-demo"))
        stages = [qa] if RELEASES[key]["active"] == "qa" else [qa, security]
        store.save(Evidence(release_id=key, stages=stages, human_decisions=decisions))
    return {key: getattr(verification, key) for key in ("closed", "still_open", "new", "new_from_db_update", "reopened", "warnings")}

# The QA checks in plain words (Arabic first, English second). A check with no finding passed.
QA_CATALOG = {
    "cart_requires_login": ("السلة تطلب تسجيل دخول", "The cart requires a login",
                            "صفحات المستخدم الخاصة ما تنفتح لزائر ما سجّل دخول.", "Private pages do not open for a visitor who is not signed in."),
    "wrong_password_is_rejected": ("كلمة المرور الخاطئة تُرفض", "A wrong password is rejected",
                                   "الدخول بكلمة مرور غلط لازم يفشل.", "Signing in with a wrong password must fail."),
    "security_headers_are_set": ("رؤوس الحماية موجودة", "Security headers are set",
                                 "المتصفح يستلم تعليمات الحماية (مثل منع عرض الموقع داخل إطار).", "The browser receives protection instructions (such as no framing)."),
    "search_resists_sql_injection": ("البحث يقاوم حقن SQL", "Search resists SQL injection",
                                     "نص خطر في خانة البحث ما يغيّر استعلام قاعدة البيانات.", "Dangerous text in the search box cannot change the database query."),
    "errors_do_not_leak_internals": ("الأخطاء ما تكشف تفاصيل داخلية", "Errors do not leak internals",
                                     "صفحة الخطأ ما تعرض معلومات عن بنية التطبيق.", "The error page does not show how the application is built."),
    "passwords_are_stored_hashed": ("كلمات المرور مخزّنة مشفّرة", "Passwords are stored hashed", "كلمات المرور ما تُحفظ نصًا صريحًا.", "Passwords are never saved as plain text."),
    "session_expires_after_inactivity": ("الجلسة تنتهي بعد خمول", "The session expires", "جلسة الدخول لها مدة انتهاء.", "A signed-in session has an expiry time."),
    "search_output_is_escaped": ("البحث لا ينفّذ أكواد خبيثة", "Search does not run scripts", "نص برمجي مكتوب بخانة البحث ما يشتغل بالصفحة.", "A script typed in the search box does not run on the page."),
    "cart_add_and_quantity_work": ("السلة تضيف الكتب وتحسب الكمية", "The cart adds books and counts quantity", "إضافة نفس الكتاب مرتين تعطي كمية 2.", "Adding the same book twice gives quantity 2."),
    "search_finds_books_by_title_and_author": ("البحث يجد الكتب بالعنوان والمؤلف", "Search finds books by title and author", "البحث باسم كتاب أو مؤلف يرجع نتائج.", "Searching for a title or an author returns results."),
    "card_data_is_not_stored": ("بيانات البطاقة لا تُخزَّن", "Card data is not stored", "قاعدة البيانات ما فيها أرقام بطاقات.", "The database holds no card numbers."),
    "other_users_orders_are_not_visible": ("طلبات الآخرين غير ظاهرة", "Other users' orders are not visible", "الزائر ما يقدر يفتح طلب مستخدم.", "A visitor cannot open a user's order."),
    "upload_accepts_images_only": ("الرفع يقبل الصور فقط", "Uploads accept images only", "رفع ملف نصي يُرفض.", "Uploading a text file is rejected."),
    "home_page_loads_fast": ("الصفحة الرئيسية سريعة", "The home page loads fast", "تُحمَّل بأقل من 3 ثوانٍ.", "It loads in under 3 seconds."),
}


def qa_checks(stage):
    """Every QA check with its result, so the page can show what passed and not only what failed."""
    if stage is None:
        return []
    scanned = bool(getattr(stage, "scanned_at", None) or stage.decision)
    by_rule = {}
    for f in stage.findings:
        by_rule[f.rule] = f
    items = []
    for name, (title_ar, title_en, desc_ar, desc_en) in QA_CATALOG.items():
        f = by_rule.pop(name, None)
        state = "pending" if not scanned else "passed"
        if f is not None:
            closed = f.closure is not None and f.closure.result == "closed"
            state = "fixed" if closed or f.status.value == "fixed" else "failed"
        items.append({"id": name, "titleAr": title_ar, "titleEn": title_en, "descAr": desc_ar, "descEn": desc_en,
                      "state": state, "finding": f.fingerprint if f is not None else None})
    for rule, f in by_rule.items():  # any other check that produced a finding
        closed = f.closure is not None and f.closure.result == "closed"
        items.append({"id": rule, "titleAr": finding_title(f), "titleEn": finding_title(f), "descAr": f.detail or "", "descEn": f.detail or "",
                      "state": "fixed" if closed or f.status.value == "fixed" else "failed", "finding": f.fingerprint})
    return items


_REQ_CACHE = {}  # (repo) -> (time, entries or None): the file is read from GitHub at most once a minute


def load_requirements(repo=None):
    """The requirements the QA reviewer checks against. Read from requirements.yaml in the release's GitHub repository
    (its default branch); if that is not possible, from config/requirements.yaml. Returns (entries, source)."""
    import time as _time
    import urllib.request
    import yaml
    if repo and re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        cached = _REQ_CACHE.get(repo)
        if not cached or _time.time() - cached[0] > 60:
            entries = None
            try:
                url = f"https://raw.githubusercontent.com/{repo}/HEAD/requirements.yaml"
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "yaqidh"}), timeout=4) as response:
                    entries = (yaml.safe_load(response.read(200_000).decode("utf-8")) or {}).get("requirements")
            except Exception:  # offline, no such file, bad yaml: use the local copy
                entries = None
            cached = _REQ_CACHE[repo] = (_time.time(), entries)
        if cached[1]:
            return cached[1], {"kind": "github", "repo": repo, "path": "requirements.yaml"}
    path = ROOT.parent / "config" / "requirements.yaml"
    try:
        return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("requirements", []), {"kind": "local", "path": "config/requirements.yaml"}
    except (OSError, yaml.YAMLError):
        return [], {"kind": "none"}


def requirement_status(checks, entries):
    """Each requirement with its status, computed from the QA check results (plain code, no AI)."""
    by_id = {c["id"]: c for c in checks}
    result = []
    for entry in entries:
        linked = [by_id[i] for i in entry.get("checks") or [] if i in by_id]
        states = {c["state"] for c in linked}
        if not entry.get("checks"):
            state = "uncovered"
        elif "failed" in states:
            state = "failed"
        elif "pending" in states or not linked:
            state = "pending"
        else:
            state = "met"
        result.append({"id": entry["id"], "titleAr": entry["ar"], "titleEn": entry["en"], "source": entry.get("source", ""),
                       "state": state, "checks": [{"id": c["id"], "titleAr": c["titleAr"], "titleEn": c["titleEn"], "state": c["state"]} for c in linked]})
    return result


def finding_title(finding):
    """A readable name for a real finding (the tools give rule ids like python.flask.security.audit.debug-enabled)."""
    rule = finding.rule or ""
    if finding.tool == "trivy" and finding.detail:
        return f"{rule}: {finding.detail}" if rule else finding.detail
    if finding.tool == "playwright":
        return rule.replace("_", " ")
    if finding.tool == "semgrep":
        return rule.split(".")[-1].replace("-", " ")
    return rule


def clean_finding(finding):
    data = finding.model_dump(mode="json")
    data["title"] = finding_title(finding)
    # Never pass arbitrary explanation text or location details from a secret result.
    if finding.tool == "trivy" and (
        not finding.component or "secret" in finding.rule.lower() or "secret" in finding.location.lower()
    ):
        data.update(location="[redacted]", explanation=None, exception=None, rule="secret-scan")
    return data

class DemoServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 32

    def __init__(self, address, store, verification, policy, live=None):
        self.live = live  # set in live mode: releases come from the Yaqidh API
        self.store = store
        self.verification = verification
        self.policy = policy
        self.sessions = {}
        self.read = {}
        self.audit = []
        self.threads = {} if live else {"deadline-128": {"id": "deadline-128", "release": "portal-128", "build": 128,
            "subject": "deadline-demo", "commit": "a3f82c1", "members": ["security", "developer"], "finding": "semgrep-demo-001",
            "deadline": {"original": "2026-11-10", "requested": "2026-11-12", "status": "pending", "reason": "deadline-reason-demo"},
            "messages": [{"by": "security", "role": "security", "text": "deadline-message-demo", "at": "2026-11-08T09:00:00+00:00"}]}}
        if not live:
            self.threads["qa-return-133"] = {"id": "qa-return-133", "release": "portal-133", "build": 133,
            "subject": "developer-inbox-demo", "members": ["qa", "developer"], "finding": "playwright-demo-001",
            "messages": [{"by": "qa", "role": "qa", "text": "developer-message-demo", "at": "2026-11-08T10:00:00+00:00"}]}
        self.lock = threading.RLock()
        super().__init__(address, Handler)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_data(self, status, body, content_type, headers=()):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        for key, value in headers:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def json(self, status, value, headers=()):
        self.send_data(status, json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8", headers)

    def fail(self, status, code):
        self.json(status, {"error": code})

    def auth(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except Exception:
            return None, None
        sid = cookies["yaqidh_session"].value if "yaqidh_session" in cookies else None
        account = self.server.sessions.get(sid)
        return sid, account if account and ACCOUNTS[account]["active"] else None

    def refresh_live(self):
        if self.server.live:
            self.server.live.refresh(RELEASES, RUNS, DEMO_RUN_DATES)

    def visible(self, account, key):
        meta = RELEASES.get(key)
        if not meta or meta["project"] not in ACCOUNTS[account]["projects"]:
            return False
        role = ACCOUNTS[account]["role"]
        if role == "developer":
            return meta["owner"] == account
        if role == "security":
            return meta["active"] == "security"
        return role == "qa"

    def release_view(self, account, key):
        role = ACCOUNTS[account]["role"]
        record = self.server.store.get(key)
        meta = RELEASES[key]
        stage_name = meta["active"] if role == "developer" else role
        stage = next((item for item in record.stages if item.name.value == stage_name), None)
        decisions = [item.model_dump(mode="json") for item in record.human_decisions if item.stage.value == stage_name]
        qa = [item.model_dump(mode="json") for item in record.human_decisions if item.stage.value == "qa"]
        outcome = stage.decision.model_dump() if stage and stage.decision else None
        requirements_entries, requirements_source = load_requirements(getattr(record, "repo", None) if self.server.live else None)
        runs = [] if role == "developer" else RUNS.get(key, {}).get(stage_name, [])
        completed = bool(runs) and all(run["state"] == "completed" for run in runs)
        approved = bool(decisions) and decisions[-1]["decision"] == "approve"
        previous_qa = qa[-1] if qa else None
        live = self.server.live
        status = live.status_report(key) if live else None
        return {
            "qaChecks": qa_checks(stage) if stage_name == "qa" else [],
            "requirements": requirement_status(qa_checks(stage), requirements_entries) if stage_name == "qa" else [],
            "requirementsSource": requirements_source,
            "gate": {"status": status["status"], "staging": status["can_merge_to_staging"], "main": status["can_merge_to_main"],
                     "reasons": status["reasons"]} if status else None,
            "id": key, **{k: v for k, v in meta.items() if k != "owner"}, "demo": True,
            "stage": stage_name, "outcome": outcome, "runs": runs,
            "findings": [clean_finding(finding) for finding in stage.findings] if stage else [],
            "blockerIds": [finding.fingerprint for finding in stage.findings
                if evaluate_policy([finding], self.server.policy).result == "fail"] if stage and outcome else [],
            "toolVersions": stage.tool_versions if stage and role != "developer" else {},
            "decisions": decisions, "previousQA": previous_qa if role == "security" else None,
            "verification": self.server.verification if key == "portal-129" and stage_name == "security" else None,
            "prior": {"id": "portal-128", "build": 128, "commit": "a3f82c1"} if key == "portal-129" and stage_name == "security" else None,
            # In live mode the Yaqidh API decides when a release is waiting for this person (it also knows that an
            # approval only covers the scan it was made on); in the demo the local rules below apply.
            "canApprove": (role == stage_name == meta["active"] and live.can_decide(key, role)) if live else (
                role == stage_name == meta["active"] and completed and not approved and outcome is not None
                and outcome["result"] == "pass" and (role != "security" or bool(previous_qa and previous_qa["decision"] == "approve"))),
            "canReject": (role == stage_name == meta["active"] and live.can_decide(key, role)) if live else (
                role == stage_name == meta["active"] and bool(outcome) and not approved),
            "exceptionEligible": [finding.fingerprint for finding in stage.findings
                if stage_name == "security" and finding.status.value == "open"
                and (not self.server.policy.exceptions.allowed_for
                     or finding.reported_as in self.server.policy.exceptions.allowed_for)] if stage else [],
            "requestDecisions": [item.model_dump(mode="json") for item in record.review_request_decisions]
                if stage_name == "security" and hasattr(record, "review_request_decisions") else [],
        }

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in {"/", "/about", "/login", "/signup", "/dashboard", "/communication"} or path in STATIC:
            target = ROOT / "web" / STATIC.get(path, "index.html")
            self.send_data(200, target.read_bytes(), MIME[target.suffix])
            return
        if path == "/admin":
            _, account = self.auth()
            if not account:
                self.send_data(303, b"", "text/plain", [("Location", "/login?account=company-admin")])
                return
            if ACCOUNTS[account]["role"] != "company-admin":
                return self.fail(403, "forbidden")
            return self.send_data(200, (ROOT / "web/index.html").read_bytes(), "text/html; charset=utf-8")
        if path.startswith("/api/admin/"):
            return self.fail(404, "not_found")
        with self.server.lock:
            self.refresh_live()
            _, account = self.auth()
            if not account:
                return self.fail(401, "sign_in_required")
            role = ACCOUNTS[account]["role"]
            if path == "/api/qa/review-alerts":
                if role != "qa":
                    return self.fail(403, "forbidden")
                return self.json(200, self.qa_review_alerts(account))
            if path == "/api/threads":
                return self.json(200, self.thread_list(account))
            if path == "/api/dashboard":
                if role == "company-admin":
                    return self.json(200, {"account": account, "display": ACCOUNTS.get(account, {}).get("display", ""), "role": role, "demo": True, "live": bool(self.server.live),
                        "accounts": [{"name": name, "role": data["role"], "active": data["active"]}
                            for name, data in ACCOUNTS.items() if not data.get("deleted")],
                        "audit": self.server.audit,
                        "liveError": self.server.live.error if self.server.live else ""})
                releases = []
                for key, meta in RELEASES.items():
                    if self.visible(account, key):
                        view = self.release_view(account, key)
                        releases.append({"id": key, "build": meta["build"], "commit": meta["commit"], "pr": meta["pr"],
                            "active": meta["active"], "day": DEMO_RUN_DATES.get(key), "outcome": view["outcome"]["result"] if view["outcome"] else None,
                            "returnReason": view["decisions"][-1]["reason"] if role == "developer" and view["decisions"] and view["decisions"][-1]["decision"] == "reject" else None,
                            "pendingReview": view["canApprove"], "gate": (view.get("gate") or {}).get("status"), "failedRuns": sum(run["state"] == "error" for run in view["runs"])})
                return self.json(200, {"account": account, "display": ACCOUNTS.get(account, {}).get("display", ""), "role": role, "demo": True, "live": bool(self.server.live), "releases": releases,
                    "reviewAlerts": self.qa_review_alerts(account) if role == "qa" else [],
                    "liveError": self.server.live.error if self.server.live else ""})
            parts = path.strip("/").split("/")
            if len(parts) in {3, 4} and parts[:2] == ["api", "releases"]:
                key = parts[2]
                if not self.visible(account, key):
                    return self.fail(403, "forbidden")
                view = self.release_view(account, key)
                if self.server.live:
                    view["log"] = self.server.live.history(key)
                if len(parts) == 3:
                    return self.json(200, view)
                if parts[3] == "evidence":
                    return self.json(200, view, [("Content-Disposition", f'attachment; filename="{key}-evidence.json"')])
            self.fail(404, "not_found")

    def grant_exception_request(self, account, key, data):
        """A security reviewer grants an exception for an eligible finding. Live mode only: the Yaqidh API records it and the
        policy engine decides whether it counts."""
        if not self.server.live:
            return self.fail(404, "not_found")
        if ACCOUNTS[account]["role"] != "security" or not self.visible(account, key) or RELEASES[key]["active"] != "security":
            return self.fail(403, "forbidden")
        finding_id, why = data.get("fingerprint"), data.get("justification")
        if not isinstance(finding_id, str) or not isinstance(why, str) or not 3 <= len(why.strip()) <= 1000:
            return self.fail(400, "invalid_input")
        if finding_id not in self.release_view(account, key)["exceptionEligible"]:
            return self.fail(409, "decision_unavailable")
        from live import LiveError
        try:
            self.server.live.grant_exception(key, finding_id, why.strip(), account)
        except LiveError:
            return self.fail(409, "decision_unavailable")
        self.refresh_live()
        return self.json(200, self.release_view(account, key))

    def qa_review_alerts(self, account):
        alerts = []
        for key, meta in RELEASES.items():
            if meta["active"] != "security" or not self.visible(account, key):
                continue
            approved = [item for item in self.server.store.get(key).review_request_decisions
                if item.status == "approved" and item.commit == meta["commit"]]
            deadlines = {item.finding: item for item in approved if item.kind == "deadline"}
            for item in approved:
                deadline = item if item.kind == "deadline" else deadlines.get(item.finding)
                alerts.append({"id": item.request_id, "kind": item.kind, "build": meta["build"],
                    "commit": item.commit, "by": item.by, "at": item.timestamp.isoformat(),
                    "approvedDeadline": (deadline.approved_deadline or deadline.requested) if deadline else None})
        return sorted(alerts, key=lambda alert: alert["at"], reverse=True)

    def decide_review_request(self, account, thread, data):
        if not thread or not self.thread_allowed(account, thread) or ACCOUNTS[account]["role"] != "security":
            return self.fail(403, "forbidden")
        key = thread.get("release")
        if not key or not self.visible(account, key):
            return self.fail(403, "forbidden")
        kind = "exception" if "exceptionRequest" in thread else "deadline"
        request = thread.get("exceptionRequest" if kind == "exception" else "deadline")
        choice = data.get("decision")
        if choice not in ("approve", "reject"):
            return self.fail(400, "invalid_input")
        meta = RELEASES[key]
        if not request or request["status"] != "pending" or thread.get("commit") != meta["commit"]:
            return self.fail(409, "decision_unavailable")
        record = self.server.store.get(key)
        stage = record.stage("security")
        finding_id = thread.get("finding")
        approved_deadline = None
        if "approvedDeadline" in data and (kind != "deadline" or choice != "approve"):
            return self.fail(400, "invalid_input")
        if kind == "deadline" and choice == "approve":
            approved_deadline = data.get("approvedDeadline", request["requested"])
            if not isinstance(approved_deadline, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?", approved_deadline):
                return self.fail(400, "invalid_input")
            previous = next((item.approved_deadline or item.requested for item in reversed(record.review_request_decisions)
                if item.kind == "deadline" and item.status == "approved" and item.finding == (finding_id or "")
                and item.commit == meta["commit"]), request["original"])
            try:
                if datetime.fromisoformat(approved_deadline) <= datetime.fromisoformat(previous):
                    return self.fail(409, "decision_unavailable")
            except ValueError:
                return self.fail(400, "invalid_input")
        if kind == "exception" and choice == "approve":
            if finding_id not in self.release_view(account, key)["exceptionEligible"]:
                return self.fail(409, "decision_unavailable")
            if self.server.live:  # the Yaqidh API records the exception and asks the policy engine again
                from live import LiveError
                try:
                    self.server.live.grant_exception(key, finding_id, request["reason"], account)
                except LiveError:
                    return self.fail(409, "decision_unavailable")
            else:
                finding = next(item for item in stage.findings if item.fingerprint == finding_id)
                finding.status = "excepted"
                finding.exception = ExceptionRecord(justification=request["reason"], approved_by=account)
                stage.decision = evaluate_policy(stage.findings, self.server.policy)
        status = "approved" if choice == "approve" else "rejected"
        decision = ReviewRequestDecision(request_id=thread["id"], commit=meta["commit"], finding=finding_id or "",
            kind=kind, status=status, by=account, reason=request["reason"],
            original=request.get("original"), requested=request.get("requested"), approved_deadline=approved_deadline)
        if self.server.live:
            from live import LiveError
            try:
                self.server.live.record_review_request(key, decision.model_dump(mode="json"))
            except LiveError:
                return self.fail(409, "decision_unavailable")
        else:
            record.review_request_decisions.append(decision)
            self.server.store.save(record)
        request.update(status=status, by=account)
        if approved_deadline:
            request["approvedDeadline"] = approved_deadline
        return self.json(200, {"status": status})

    def thread_allowed(self, account, thread):
        if account not in thread["members"]:
            return False
        if thread.get("kind") == "administrative":
            return True
        return ACCOUNTS[account]["role"] != "company-admin" and RELEASES[thread["release"]]["project"] in ACCOUNTS[account]["projects"]

    def thread_list(self, account):
        return [{**thread, "unread": any(message["by"] != account for message in
            thread["messages"][self.server.read.get((account, thread["id"]), 0):]),
            "evidenceAllowed": thread.get("kind") != "administrative" and self.visible(account, thread["release"])}
            for thread in self.server.threads.values() if self.thread_allowed(account, thread)]

    def post_thread(self, account, path, data):
        body = data.get("message", "")
        if path.endswith("/review-decision"):
            return self.decide_review_request(account, self.server.threads.get(path.split("/")[-2]), data)
        if path.endswith("/read"):
            key = path.split("/")[-2]
            thread = self.server.threads.get(key)
            if not thread or not self.thread_allowed(account, thread):
                return self.fail(403, "forbidden")
            self.server.read[(account, key)] = len(thread["messages"])
            return self.json(200, {"ok": True})
        if not isinstance(body, str) or not 1 <= len(body.strip()) <= 1500:
            return self.fail(400, "invalid_input")
        if path == "/api/threads" and "recipient" in data:
            if ACCOUNTS[account]["role"] != "company-admin":
                return self.fail(403, "forbidden")
            recipient, subject = data.get("recipient"), data.get("subject")
            if set(data) != {"recipient", "subject", "message"} or not isinstance(recipient, str) or not isinstance(subject, str) or not 1 <= len(subject.strip()) <= 100:
                return self.fail(400, "invalid_input")
            employee = ACCOUNTS.get(recipient)
            if not employee or not employee["active"] or employee["role"] == "company-admin":
                return self.fail(403, "forbidden")
            key = secrets.token_hex(8)
            self.server.threads[key] = thread = {"id": key, "kind": "administrative", "subject": subject.strip(),
                "members": [account, recipient], "messages": []}
        elif path == "/api/threads":
            release = data.get("release")

            subject = data.get("subject")
            if not isinstance(release, str) or not isinstance(subject, str) or not 1 <= len(subject.strip()) <= 100:
                return self.fail(400, "invalid_input")
            meta = RELEASES.get(release)
            is_admin = ACCOUNTS[account]["role"] == "company-admin"
            if is_admin or not meta or not self.visible(account, release):
                return self.fail(403, "forbidden")
            sender_role = ACCOUNTS[account]["role"]
            exception_request = data.get("requestType") == "exception"
            if exception_request and (sender_role != "developer" or meta["active"] != "security"
                    or data.get("finding") not in self.release_view(account, release)["exceptionEligible"]
                    or data.get("original") or data.get("requested")):
                return self.fail(403, "forbidden")
            if exception_request and any(t.get("release") == release and t.get("finding") == data.get("finding")
                    and t.get("exceptionRequest", {}).get("status") == "pending" for t in self.server.threads.values()):
                return self.fail(409, "decision_unavailable")
            if sender_role == "security" or (sender_role == "developer" and meta["active"] == "security"
                    and not exception_request and (not data.get("original") or not data.get("requested")
                         or data.get("finding") not in self.release_view(account, release)["blockerIds"])):
                return self.fail(403, "forbidden")
            owner = meta["owner"]
            if sender_role == "developer":
                members = [name for name, user in ACCOUNTS.items()
                    if name != account and user["active"] and user["role"] == meta["active"]
                    and meta["project"] in user["projects"]]
            else:
                members = [owner] if (owner != account and owner in ACCOUNTS
                    and ACCOUNTS[owner]["active"] and ACCOUNTS[owner]["role"] == "developer"
                    and meta["project"] in ACCOUNTS[owner]["projects"]) else []
            if not members:
                return self.fail(409, "recipient_unavailable")
            finding = data.get("finding")
            if finding and not any(item["fingerprint"] == finding for item in self.release_view(account, release)["findings"]):
                return self.fail(403, "forbidden")
            deadline = None
            original, requested = data.get("original"), data.get("requested")
            if original or requested:
                if not isinstance(original, str) or not isinstance(requested, str):
                    return self.fail(400, "invalid_input")
                try:
                    if date.fromisoformat(requested) <= date.fromisoformat(original):
                        return self.fail(400, "invalid_input")
                except ValueError:
                    return self.fail(400, "invalid_input")
                deadline = {"original": original, "requested": requested, "status": "pending", "reason": body.strip()}
            key = secrets.token_hex(8)
            thread = {"id": key, "release": release, "build": RELEASES[release]["build"],
                "subject": subject.strip(), "commit": meta["commit"], "finding": finding or None, "members": [account, *members], "messages": []}
            if deadline:
                thread["deadline"] = deadline
            if exception_request:
                thread["exceptionRequest"] = {"status": "pending", "reason": body.strip()}
            self.server.threads[key] = thread
        else:
            key = path.split("/")[-1]
            thread = self.server.threads.get(key)
            if not thread or not self.thread_allowed(account, thread):
                return self.fail(403, "forbidden")
        thread["messages"].append({"by": account, "role": ACCOUNTS[account]["role"], "text": body.strip(), "at": datetime.now(timezone.utc).isoformat()})
        self.server.read[(account, key)] = len(thread["messages"])
        return self.json(200, {"id": key})

    def update_account(self, account, data):
        target = data.get("account")
        role = data.get("role")
        active = data.get("active")
        if ACCOUNTS[account]["role"] != "company-admin":
            return self.fail(403, "forbidden")
        if not isinstance(target, str) or target not in ACCOUNTS or ACCOUNTS[target].get("deleted") or target == account or role not in ("developer", "qa", "security") or type(active) is not bool:
            return self.fail(400, "invalid_input")
        ACCOUNTS[target].update(role=role, active=active)
        for token, owner in list(self.server.sessions.items()):
            if owner == target:
                del self.server.sessions[token]
        self.server.audit.append({"by": account, "target": target, "role": role, "active": active,
            "at": datetime.now(timezone.utc).isoformat()})
        return self.json(200, {"ok": True})

    def delete_account(self, account, data):
        if ACCOUNTS[account]["role"] != "company-admin":
            return self.fail(403, "forbidden")
        target = data.get("account")
        if not isinstance(target, str) or target == account:
            return self.fail(400, "invalid_input")
        user = ACCOUNTS.get(target)
        if not user or user.get("deleted"):
            return self.fail(404, "not_found")
        if user["role"] == "company-admin" or not set(user["projects"]).issubset(ACCOUNTS[account]["projects"]):
            return self.fail(403, "forbidden")
        if user["active"]:
            return self.fail(409, "disable_account_first")
        ACCOUNTS[target] = {"role": user["role"], "active": False, "projects": [], "deleted": True}
        for token, owner in list(self.server.sessions.items()):
            if owner == target:
                del self.server.sessions[token]
        self.server.audit.append({"by": account, "target": target, "role": user["role"], "active": False,
            "action": "deleted", "at": datetime.now(timezone.utc).isoformat()})
        return self.json(200, {"ok": True})


    def create_account(self, data):
        name, password, role = (data.get(key) for key in ("account", "password", "role"))
        name = name.strip().lower() if isinstance(name, str) else name
        display = data.get("display", "")
        if not isinstance(display, str) or len(display.strip()) > 40 or any(ch in display for ch in "<>") or any(ord(ch) < 32 for ch in display):
            return self.fail(400, "invalid_input")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9._-]{2,31}", name) or not isinstance(password, str) or not 10 <= len(password) <= 128 or role not in ("developer", "qa", "security"):
            return self.fail(400, "invalid_input")
        if name in ACCOUNTS:
            return self.fail(409, "account_exists")
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
        ACCOUNTS[name] = {"role": role, "salt": salt, "digest": digest, "projects": [], "active": True, "display": display.strip()}
        return self.json(201, {"status": "active"})

    def password_matches(self, name, password):
        if not isinstance(name, str) or name not in ACCOUNTS or not isinstance(password, str) or len(password) > 128:
            return False
        user = ACCOUNTS[name]
        if not user["active"]:
            return False
        if "digest" not in user:
            return hmac.compare_digest(password.encode(), PASSWORD.encode())
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), user["salt"], 200_000)
        return hmac.compare_digest(digest, user["digest"])

    def body(self):
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 4096:
            raise ValueError("invalid body size")
        data = json.loads(self.rfile.read(size))
        if not isinstance(data, dict):
            raise ValueError("invalid body")
        return data

    def do_POST(self):
        path = urlsplit(self.path).path
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if host not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
            return self.fail(403, "forbidden")
        if origin != f"http://{host}" or self.headers.get_content_type() != "application/json":
            return self.fail(403, "forbidden")
        try:
            data = self.body()
        except (ValueError, UnicodeError):
            return self.fail(400, "invalid_input")
        with self.server.lock:
            self.refresh_live()
            sid, account = self.auth()
            if path == "/api/signup":
                return self.create_account(data)
            if path == "/api/login":
                name, password = data.get("account"), data.get("password")
                name = name.strip().lower() if isinstance(name, str) else name
                if not self.password_matches(name, password):
                    return self.fail(401, "invalid_credentials")
                self.server.sessions.pop(sid, None)
                token = secrets.token_urlsafe(32)
                self.server.sessions[token] = name
                return self.json(200, {"ok": True}, [("Set-Cookie", f"yaqidh_session={token}; Path=/; HttpOnly; SameSite=Strict")])
            if not account:
                return self.fail(401, "sign_in_required")
            if path == "/api/logout":
                self.server.sessions.pop(sid, None)
                return self.json(200, {"ok": True}, [("Set-Cookie", "yaqidh_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict")])
            if path == "/api/company/accounts/delete":
                return self.delete_account(account, data)
            if path == "/api/company/accounts":
                return self.update_account(account, data)
            if path == "/api/threads" or path.startswith("/api/threads/"):
                return self.post_thread(account, path, data)
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "releases"] and parts[3] == "exception":
                return self.grant_exception_request(account, parts[2], data)
            if len(parts) != 4 or parts[:2] != ["api", "releases"] or parts[3] != "decision":
                return self.fail(404, "not_found")
            key = parts[2]
            role = ACCOUNTS[account]["role"]
            if role not in {"qa", "security"} or not self.visible(account, key) or RELEASES[key]["active"] != role:
                return self.fail(403, "forbidden")
            view = self.release_view(account, key)
            choice, reason = data.get("decision"), data.get("reason")
            if choice not in ("approve", "reject") or not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 1000:
                return self.fail(400, "invalid_input")
            if data.get("commit") != view["commit"] or not view["canApprove" if choice == "approve" else "canReject"]:
                return self.fail(409, "decision_unavailable")
            if self.server.live:
                from live import LiveError
                try:
                    self.server.live.decide(key, role, choice, reason.strip(), account)
                except LiveError as e:
                    return self.fail(409 if e.status in (409, 422) else 502, "decision_unavailable")
                self.refresh_live()
                return self.json(200, self.release_view(account, key))
            evidence = self.server.store.get(key)
            evidence.human_decisions.append(HumanDecision(stage=role, decision=choice, by=account, reason=reason.strip()))
            self.server.store.save(evidence)
            self.json(200, self.release_view(account, key))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--live", action="store_true", help="read releases from the Yaqidh API instead of demo data")
    parser.add_argument("--api-url", help="the Yaqidh API address (or YAQIDH_API_URL); the token is YAQIDH_API_TOKEN")
    args = parser.parse_args()
    if args.live:
        import live as live_module
        if args.api_url:
            os.environ["YAQIDH_API_URL"] = args.api_url
        policy = load_policy(ROOT.parent / "config/policy.yaml")
        ACCOUNTS["company-admin"]["projects"] = ["portal"]  # the demo's second project ("research") does not exist in live mode
        backend = live_module.from_env(Evidence, [n for n, a in ACCOUNTS.items() if a["role"] == "developer"])
        with DemoServer(("127.0.0.1", args.port), live_module.LiveStore(backend), {}, policy, backend) as server:
            print(f"YAQIDH dashboard (live, API {backend.base_url}): http://127.0.0.1:{server.server_port}/dashboard", flush=True)
            server.serve_forever()
        return
    policy = load_policy(ROOT / "backend/config/policy.yaml")
    with tempfile.TemporaryDirectory(prefix="yaqidh-demo-") as directory:
        store = EvidenceStore(Path(directory))
        verification = seed(store, policy)
        with DemoServer(("127.0.0.1", args.port), store, verification, policy) as server:
            print(f"YAQIDH local demo: http://127.0.0.1:{server.server_port}/dashboard", flush=True)
            server.serve_forever()

if __name__ == "__main__":
    main()
