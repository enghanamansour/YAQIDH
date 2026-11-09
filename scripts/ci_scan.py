"""Runs in CI (GitHub Actions) on the pull request's code: scans with our own tools and sends the results to Yaqidh.

    python scripts/ci_scan.py --target . [--out results.json]      (without YAQIDH_URL it only writes the file)

Needs, from the workflow: YAQIDH_URL (e.g. https://host), YAQIDH_TOKEN (the API_TOKEN), GITHUB_REPOSITORY,
PR_NUMBER and PR_HEAD_SHA (the pull request's head commit, not the merge commit GITHUB_SHA).
The fingerprints are made here, where the code is, with the same tools the server would use.
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from src.github_sync import release_id_for  # noqa: E402
from src.scanning import ScanResult, security_runner  # noqa: E402


def build_submission(result: ScanResult, commit: str) -> dict:
    """The JSON body the server's /scan-results route expects."""
    return {
        "commit": commit,
        "findings": [f.model_dump(mode="json") for f in result.findings],
        "versions": result.versions,
        "tools_run": sorted(result.tools_run),
        "components": sorted(result.components),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=".")
    ap.add_argument("--rules", default=str(ROOT / "config" / "semgrep-rules"))
    ap.add_argument("--out")
    args = ap.parse_args()

    from src.tools.security.semgrep import SemgrepTool
    from src.tools.security.trivy import TrivyTool

    result = security_runner(SemgrepTool(Path(args.rules)), TrivyTool())(Path(args.target))
    commit = os.environ.get("PR_HEAD_SHA", "")
    body = build_submission(result, commit)
    if args.out:
        Path(args.out).write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    url, token = os.environ.get("YAQIDH_URL"), os.environ.get("YAQIDH_TOKEN")
    if not url:
        print(f"scanned: {len(result.findings)} findings (no YAQIDH_URL, nothing sent)")
        return 0
    if not (token and commit and os.environ.get("GITHUB_REPOSITORY") and os.environ.get("PR_NUMBER")):
        print("YAQIDH_TOKEN, PR_HEAD_SHA, GITHUB_REPOSITORY and PR_NUMBER are required to send results", file=sys.stderr)
        return 2
    release_id = release_id_for(os.environ["GITHUB_REPOSITORY"], int(os.environ["PR_NUMBER"]))
    resp = httpx.post(f"{url.rstrip('/')}/releases/{release_id}/scan-results", json=body,
                      headers={"X-API-Token": token}, timeout=60)
    print(f"sent {len(result.findings)} findings for {release_id}: HTTP {resp.status_code} {resp.text[:200]}")
    return 0 if resp.status_code < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
