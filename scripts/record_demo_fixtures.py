"""Records the results of the REAL tools on demo_app, in the states the guided demo replays.

    python scripts/record_demo_fixtures.py

It runs Playwright (QA) and Semgrep + Trivy (security) on demo_app three times, the way the demo walks it:
  1  as planted (QA fails)                      -> qa[0]
  2  after the QA fix  (QA passes)              -> qa[1], and the security scan of that code -> security[0]
  3  after the security fix (all clean)         -> qa[2], and the security scan of that code -> security[1]
and writes demo_replay/fixtures.json. The guided demo (YAQIDH_DEMO_MODE) sends these results to the real API as if a CI job had
run them, so the policy engine, the explanations and the evidence log are real; only the tool runs are replayed.
Needs the scan tools (Semgrep rules, Trivy, Playwright) and a demo_app with no uncommitted changes. It puts demo_app back at the end.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.scanning import default_runners  # noqa: E402
from src.schema import StageName  # noqa: E402
from src.settings import Settings  # noqa: E402

OUT = ROOT / "demo_replay" / "fixtures.json"
TARGET = ROOT / "demo_app"


def fix(step: str) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_fix.py"), step], check=True, cwd=ROOT)


def pack(result) -> dict:
    return {
        "findings": [f.model_dump(mode="json") for f in result.findings],
        "versions": dict(result.versions),
        "tools_run": sorted(result.tools_run),
        "components": sorted(result.components),
        "flaky": list(result.flaky),
    }


def main() -> None:
    if subprocess.run(["git", "status", "--porcelain", "demo_app"], cwd=ROOT, capture_output=True, text=True).stdout.strip():
        raise SystemExit("demo_app has uncommitted changes; commit or stash them first")
    runners = default_runners(Settings())
    qa, security = runners[StageName.QA], runners[StageName.SECURITY]
    out = {"qa": [], "security": []}
    try:
        fix("reset")
        out["qa"].append(pack(qa(TARGET)))
        fix("qa")
        out["qa"].append(pack(qa(TARGET)))
        out["security"].append(pack(security(TARGET)))
        fix("security")
        out["qa"].append(pack(qa(TARGET)))
        out["security"].append(pack(security(TARGET)))
    finally:
        fix("reset")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for name in ("qa", "security"):
        print(name, [len(r["findings"]) for r in out[name]], "findings per step")
    print("written", OUT)


if __name__ == "__main__":
    main()
