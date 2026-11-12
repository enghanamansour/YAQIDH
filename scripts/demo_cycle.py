"""Phase 12: one full release cycle on the demo site, with the real tools, from the first push to the last gate check.

    python scripts/demo_cycle.py [--data-dir DIR] [--keep]

A copy of demo_app is the "pull request". A scripted developer fixes it in two pushes. Nothing here uses the AI
model (the agent only adds explanations on top); decisions come from the policy engine, the verifier and two
pretend human reviewers, exactly as in the real flow:

  push 1  QA fails (the planted SQL injection and error leak)           -> back to the developer
  push 2  the developer fixes the SQL query; QA re-runs and passes      -> QA reviewer approves -> staging allowed
          security is scanned: debug mode, a token in the code, old libraries ...
  push 3  the developer fixes debug mode, the token and the libraries   -> QA re-runs by itself (approval still valid),
          security re-scans, the verifier closes what is gone           -> what is still open keeps main closed
"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qa_checks.maktabti_security import CHECKS  # noqa: E402
from src.gate import check_gate  # noqa: E402
from src.history import HistoryLog  # noqa: E402
from src.phases.workflow import Workflow  # noqa: E402
from src.policy import load_policy  # noqa: E402,F401
from src.scanning import qa_runner, security_runner  # noqa: E402
from src.schema import StageName  # noqa: E402
from src.service import ReleaseService  # noqa: E402
from src.storage import EvidenceStore  # noqa: E402
from src.tools.qa.app_server import AppServer  # noqa: E402
from src.tools.qa.playwright_tool import PlaywrightTool  # noqa: E402
from src.tools.security.semgrep import SemgrepTool  # noqa: E402
from src.tools.security.trivy import TrivyTool  # noqa: E402

RELEASE = "demo-cycle"
C1, C2, C3 = "1" * 40, "2" * 40, "3" * 40


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"the demo app changed: cannot find the text to fix in {path.name}: {old[:50]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def fix_sql_query(app: Path) -> None:
    edit(app / "app.py",
         '''    sql = "SELECT * FROM books WHERE title LIKE '%" + q + "%' OR author LIKE '%" + q + "%' ORDER BY title"
    books = db.execute(sql).fetchall()''',
         '''    sql = "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? ORDER BY title"
    books = db.execute(sql, (f"%{q}%", f"%{q}%")).fetchall()''')


def fix_security_issues(app: Path) -> None:
    edit(app / "app.py", "debug=True", "debug=False")
    edit(app / "config.py", 'SHIPPING_API_TOKEN = "ghp_Zq8RtLmN3vXcP5wYb7KdJh2FsA9eUo4GiT1x"  # TODO move to env before launch',
         'SHIPPING_API_TOKEN = os.environ.get("SHIPPING_API_TOKEN", "")')
    (app / "requirements.txt").write_text("flask==3.0.3\njinja2==3.1.4\nrequests==2.32.4\n", encoding="utf-8")


def say(text: str = "") -> None:
    print(text, flush=True)


def stage_line(service: ReleaseService, stage: str) -> str:
    s = service.store.get(RELEASE).stage(StageName(stage))
    opened = [f for f in s.findings if f.status.value == "open"]
    high = sum(1 for f in opened if f.severity.value == "high")
    verdict = s.decision.result.upper() if s.decision else "-"
    return f"{stage}: policy {verdict} | open {len(opened)} (high {high}) | closed {len(s.findings) - len(opened)}"


def gates(service: ReleaseService, commit: str) -> str:
    ev = service.store.get(RELEASE)
    parts = []
    for target in ("staging", "main"):
        g = check_gate(ev, commit, target)
        parts.append(f"{target}: {'ALLOWED' if g.allowed else 'closed'} ({g.reason})")
    return " | ".join(parts)


def push(service: ReleaseService, workflow: Workflow, commit: str, first: bool = False) -> None:
    service.set_head_commit(RELEASE, commit)
    workflow.submit(RELEASE) if first else workflow.push(RELEASE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir")
    ap.add_argument("--keep", action="store_true", help="keep the evidence and history so the dashboard can show them")
    args = ap.parse_args()

    work = Path(tempfile.mkdtemp(prefix="yaqidh-cycle-"))
    data = Path(args.data_dir) if args.data_dir else work / "data"
    shutil.copytree(ROOT / "demo_app", work / "demo_app", ignore=shutil.ignore_patterns("*.db", "__pycache__"))
    app = work / "demo_app"

    runners = {
        StageName.QA: qa_runner(PlaywrightTool(CHECKS), lambda: AppServer("demo_app.app", cwd=work)),
        StageName.SECURITY: security_runner(SemgrepTool(ROOT / "config" / "semgrep-rules"), TrivyTool()),
    }
    history = HistoryLog(data / "history")
    service = ReleaseService(EvidenceStore(data / "releases"), ROOT / "config" / "policy.yaml", runners, app, history)
    workflow = Workflow(service)
    try:
        say("== push 1: a pull request is opened ==")
        push(service, workflow, C1, first=True)
        say("  " + stage_line(service, "qa"))
        say(f"  status: {workflow.status(RELEASE).status.value} | {gates(service, C1)}")

        say("\n== push 2: the developer fixes the SQL query ==")
        fix_sql_query(app)
        push(service, workflow, C2)
        say("  " + stage_line(service, "qa"))
        say(f"  status: {workflow.status(RELEASE).status.value}")
        workflow.approve(RELEASE, "qa", "Sara (QA reviewer)", "checks reviewed")
        say("  QA reviewer approved -> security scanned on the same commit")
        say("  " + stage_line(service, "security"))
        say(f"  status: {workflow.status(RELEASE).status.value} | {gates(service, C2)}")

        say("\n== push 3: the developer fixes debug mode, the token and the libraries ==")
        fix_security_issues(app)
        push(service, workflow, C3)
        say("  " + stage_line(service, "qa") + "   (QA re-ran by itself; the approval still counts)")
        say("  " + stage_line(service, "security"))
        rescan = [e for e in history.entries(RELEASE) if e["event"] == "rescan" and e["data"].get("stage") == "security"][-1]["data"]
        say(f"  verifier: closed {len(rescan['closed'])} | still open {len(rescan['still_open'])} | new {len(rescan['new'])}")
        say(f"  status: {workflow.status(RELEASE).status.value} | {gates(service, C3)}")

        say("\n== history ==")
        for e in history.entries(RELEASE):
            say(f"  {e['seq']:>2} {e['event']:<16} {e['actor']}")
        say(f"  chain: {history.verify(RELEASE)}")
        say(f"\nA push after an approval closes the gate: {gates(service, C2)}   (commit 2 is no longer the newest)")
    finally:
        if args.keep:
            say(f"\nkept: {data}")
        else:
            shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
