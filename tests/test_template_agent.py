"""AGENT_MODE=template: explanations without any model (a demo that costs no tokens and cannot hit a rate limit)."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = textwrap.dedent("""
    import asyncio, os, tempfile
    from pathlib import Path
    d = tempfile.mkdtemp()
    os.environ.update(DATA_DIR=d + "/r", HISTORY_DIR=d + "/h", API_TOKEN="t", AGENT_MODE="template", YAQIDH_NO_DOTENV="1")
    os.environ.pop("GITHUB_TOKEN", None); os.environ.pop("LLM_API_KEY", None)
    from src.storage import EvidenceStore
    from src.schema import Finding, Severity, StageName
    from src.api import main
    store = EvidenceStore(Path(d) / "r")
    ev = store.create("r1")
    qa = ev.stage(StageName.QA)
    qa.findings = [Finding(fingerprint="F-1", tool="playwright", severity=Severity.HIGH, location="a.py:1", rule="sql")]
    qa.tool_versions = {"playwright": "1"}
    store.save(ev)
    out = asyncio.run(main.template_agent("r1", "pull_request_opened"))
    f = store.get("r1").stage(StageName.QA).findings[0]
    print("RESULT", out["mode"], out["tokens"], len(out["calls"]), f.explanation.source)
""")


def test_the_template_agent_explains_without_a_model():
    env = {**os.environ, "PYTHONUTF8": "1"}
    out = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, env=env, capture_output=True, text=True,
                         encoding="utf-8", timeout=120)
    assert "RESULT template 0 1 Yaqidh" in out.stdout, out.stderr[-500:]
