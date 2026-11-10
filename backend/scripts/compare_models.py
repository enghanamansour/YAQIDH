"""Runs the same findings through several models and puts the answers side by side.

Why: the choice of the explaining model should come from looking at real answers,
not from guessing. The script uses the project's own explainer, grouping and
checks, so what you see is what the backend would do.

Run it from the `backend` folder:

    python scripts/compare_models.py
    python scripts/compare_models.py --models openai/gpt-oss-120b,openai/gpt-oss-20b
    python scripts/compare_models.py --dialect
    python scripts/compare_models.py --file path/to/team_findings.json

It reads LLM_API_KEY / LLM_BASE_URL / DIALECT_MODEL from the local `.env` by itself
(the values are never printed). The full answers are written to a Markdown file
(default: data/compare_results.md, which is git-ignored), because Arabic text
displays badly in a Windows console. Open that file in VS Code to read it.

Use demo data only: the findings are sent to the model provider.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import httpx  # noqa: E402

from app.adapters import from_team_findings, from_tool_output  # noqa: E402
from app.config import load_env  # noqa: E402
from app.explainer import (  # noqa: E402
    DialectRewriter,
    LLMExplainer,
    TemplateExplainer,
    explain_group,
    meaning_problem,
)
from app.models import Explanation  # noqa: E402
from app.grouping import Group, group_findings  # noqa: E402
from app.models import Finding  # noqa: E402

SAMPLE = BACKEND / "tests" / "fixtures" / "team_findings_sample.json"
DEFAULT_MODELS = "openai/gpt-oss-120b,openai/gpt-oss-20b"
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"


def demo_findings() -> list[Finding]:
    """Three made-up findings that cover cases the real sample does not."""
    return [
        # a rich finding: description and CWE are given
        Finding(rule_id="demo.hardcoded-secret", title="Hard-coded credential", severity="high",
                file="config.py", line=5, cwe="CWE-798", confidence="high",
                description="A password-like string is assigned directly in the source code."),
        # no line number, like a vulnerable library
        Finding(rule_id="demo.vulnerable-dependency", title="Vulnerable dependency", severity="critical",
                file="requirements.txt",
                description="The pinned version flask==0.12.2 is reported by the scanner as having known vulnerabilities."),
        # the tool itself is unsure: the answer should say so
        Finding(rule_id="demo.possible-path-traversal", title="Possible path traversal", severity="low",
                file="files.py", line=31, cwe="CWE-22", confidence="low",
                description="User input may reach a file path."),
    ]


def load_findings(paths: list[str] | None) -> tuple[list[Finding], str]:
    """Team-format files (a JSON list) and the raw JSON of Semgrep or Trivy can be mixed."""
    if paths:
        findings: list[Finding] = []
        for path in paths:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            findings += from_team_findings(data) if isinstance(data, list) else from_tool_output(data)
        return findings, "files: " + ", ".join(Path(p).name for p in paths)
    items = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return from_team_findings(items) + demo_findings(), "the team's real sample (4) + 3 made-up demo findings"


def diagnose(llm: LLMExplainer, finding: Finding, lang: str) -> str:
    """Asks once more, only to learn WHY an answer was rejected. Never prints the key."""
    try:
        resp = llm.client.post(
            f"{llm.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {llm.api_key}"},
            json=llm._payload(finding, lang),
        )
    except httpx.HTTPError as exc:
        return f"network error ({type(exc).__name__})"
    if resp.status_code >= 400:
        return f"HTTP {resp.status_code}: {resp.text[:200]}"
    try:
        choice = resp.json()["choices"][0]
        text = (choice["message"].get("content") or "").strip()
    except (KeyError, IndexError, ValueError):
        return "unexpected response shape"
    reason = choice.get("finish_reason")
    if not text:
        return f"empty answer (finish_reason={reason}); a reasoning model may have spent its tokens thinking"
    return (f"answer not accepted (finish_reason={reason}, {len(text)} chars): "
            "not a JSON object with the 3 keys, or it contained code/backticks")


def diagnose_dialect(rewriter: DialectRewriter, exp: Explanation) -> str:
    """Asks the dialect model once more to learn WHY the rewrite was rejected.

    Output can vary between calls, so this tells what happens on a second try,
    which is usually the same reason. Never prints the key.
    """
    try:
        resp = rewriter.client.post(
            f"{rewriter.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {rewriter.api_key}"},
            json={"model": rewriter.model, "temperature": 0, "messages": rewriter.build_messages(exp)},
        )
    except httpx.HTTPError as exc:
        return f"network error ({type(exc).__name__})"
    if resp.status_code >= 400:
        return f"HTTP {resp.status_code}: {resp.text[:200]}"
    try:
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.strip("`").removeprefix("json").strip()
        out = Explanation(**json.loads(content))
    except (KeyError, IndexError, ValueError, TypeError):
        return "the answer was not a JSON object with the 3 expected keys"
    return meaning_problem(exp, out) or "passed the checks on the second try (output varies between calls)"


class Probe:
    """Stands in for the explainer so we can time each call and see why it failed."""

    def __init__(self, llm: LLMExplainer):
        self.llm = llm
        self.last: dict = {}

    def explain(self, finding: Finding, lang: str):
        start = time.perf_counter()
        exp, attempts = None, 0
        for _ in range(2):  # same as the real explainer: one retry
            attempts += 1
            exp = self.llm._ask(finding, lang)
            if exp is not None:
                break
        secs = time.perf_counter() - start
        self.last = {"exp": exp, "secs": secs, "attempts": attempts,
                     "why": None if exp else diagnose(self.llm, finding, lang)}
        return exp


def one_line(text: str) -> str:
    return " ".join(text.split())


def fmt_exp(exp) -> list[str]:
    return [
        f"- **problem:** {one_line(exp.problem)}",
        f"- **why_dangerous:** {one_line(exp.why_dangerous)}",
        f"- **direction:** {one_line(exp.direction)}",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=DEFAULT_MODELS, help="comma-separated model names to compare")
    ap.add_argument("--lang", choices=["ar", "en"], default="ar")
    ap.add_argument("--file", action="append",
                    help="findings JSON: the team's format or the raw Semgrep / Trivy output. Repeat to combine")
    ap.add_argument("--only", help="comma-separated texts: keep only the problems whose rule or file contains one of them")
    ap.add_argument("--dialect", action="store_true", help="also run the Saudi dialect step (DIALECT_MODEL)")
    ap.add_argument("--pause", type=float, default=2.0, help="seconds to wait between calls (rate limits)")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--out", default=str(BACKEND.parent / "data" / "compare_results.md"))
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    used = load_env()
    print(f".env found: {'yes' if used else 'no'} (values are never printed)")
    key = os.environ.get("LLM_API_KEY")
    if not key:
        print("LLM_API_KEY is empty. Put your key in .env (you fill it yourself), then run again.")
        return 1
    base_url = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL)
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    dialect_model =os.environ.get("DIALECT_MODEL", "").strip() or "allam-2-7b"

    findings, source = load_findings(args.file)
    groups: list[Group] = group_findings(findings)
    merged = len(groups)
    if args.only:
        wanted = [t.strip() for t in args.only.split(",") if t.strip()]
        groups = [g for g in groups if any(t in r or t in g.representative.file for r in g.rules for t in wanted)]
    print(f"findings: {len(findings)} -> {merged} problems after merging duplicates ({source})")
    if len(groups) != merged:
        print(f"running only {len(groups)} of them (--only)")
    print(f"models: {', '.join(models)}" + (f" | dialect: {dialect_model}" if args.dialect else ""))
    print("note: the findings are sent to the provider. Demo data only.")

    client = httpx.Client(timeout=args.timeout)
    template = TemplateExplainer()
    rewriter = DialectRewriter(base_url, key, dialect_model, client=client) if args.dialect else None
    probes = {m: Probe(LLMExplainer(base_url, key, m, client=client)) for m in models}
    stats = {m: {"ok": 0, "failed": 0, "secs": 0.0, "dialect_ok": 0, "dialect_rejected": 0} for m in models}

    lines = [
        "# Model comparison",
        "",
        f"- source: {source}",
        f"- language: {args.lang}",
        f"- models: {', '.join(models)}",
        "- The template answer is the fixed fallback: it uses only the finding's own fields.",
        "- Judge each answer yourself: is it technically right, does it invent facts, is it clear?",
        "",
    ]

    for number, group in enumerate(groups, start=1):
        main_finding = group.representative
        where = f"{main_finding.file}:{main_finding.line}" if main_finding.line else main_finding.file
        print(f"[{number}/{len(groups)}] {where}")
        lines += [
            f"## {number}. {main_finding.title} ({where})",
            "",
            f"- severity: {group.severity} | rules: {', '.join(group.rules)}",
            f"- cwe: {main_finding.cwe or 'not given'} | tool confidence: {main_finding.confidence or 'not given'}",
            f"- description given to the model: {one_line(main_finding.description) or 'none (rule name only)'}",
            "",
            "### Fixed template",
            *fmt_exp(explain_group(template, group, args.lang)),
            "",
        ]
        for model in models:
            probe = probes[model]
            time.sleep(args.pause)
            explain_group(probe, group, args.lang)
            result = probe.last
            lines.append(f"### {model}")
            if result["exp"] is None:
                stats[model]["failed"] += 1
                lines += [f"- **FAILED** after {result['attempts']} attempts ({result['secs']:.1f}s): {result['why']}", ""]
                print(f"   {model}: FAILED - {result['why'][:90]}")
                continue
            stats[model]["ok"] += 1
            stats[model]["secs"] += result["secs"]
            lines += [f"- time: {result['secs']:.1f}s, attempts: {result['attempts']}", *fmt_exp(result["exp"]), ""]
            print(f"   {model}: ok in {result['secs']:.1f}s")
            if rewriter:
                time.sleep(args.pause)
                rewritten = rewriter.rewrite(result["exp"])
                lines.append(f"#### {model} then {dialect_model} (Saudi dialect)")
                if rewritten is None:
                    stats[model]["dialect_rejected"] += 1
                    why = diagnose_dialect(rewriter, result["exp"])
                    lines += [f"- rejected or failed: {why}", "- the real system would keep the answer above as it is", ""]
                    print(f"   {model} + dialect: rejected")
                else:
                    stats[model]["dialect_ok"] += 1
                    lines += [*fmt_exp(rewritten), ""]

    lines += ["## Summary", "", "| model | answered | failed (fell back to template) | avg seconds |"
              + (" dialect accepted | dialect rejected |" if rewriter else ""),
              "|---|---|---|---|" + ("---|---|" if rewriter else "")]
    print("\nmodel | answered | failed | avg seconds")
    for model, s in stats.items():
        avg = s["secs"] / s["ok"] if s["ok"] else 0.0
        row = f"| {model} | {s['ok']} | {s['failed']} | {avg:.1f} |"
        if rewriter:
            row += f" {s['dialect_ok']} | {s['dialect_rejected']} |"
        lines.append(row)
        print(f"{model} | {s['ok']} | {s['failed']} | {avg:.1f}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nfull answers written to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
