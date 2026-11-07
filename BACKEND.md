# Yaqidh backend (setup and layout)

An AI agent that accompanies a product through release stages
(`qa -> security`). It reads, explains and writes evidence text.
It never decides: pass/fail and finding status come only from plain code
(policy engine, verifier). Humans approve the final release.

## Layout

```
config/        policy.yaml (pass/fail rules), semgrep-rules/ (official, fetched, gitignored)
scripts/       fetch_semgrep_rules.sh
data/releases/ evidence JSON per release (gitignored)
src/
  settings.py  reads .env
  schema.py    data shapes: Finding, Evidence, Decision
  storage.py   saves and loads the evidence file
  policy.py    decides pass/fail
  tools/       base.py, finding_id.py, security/semgrep.py + trivy.py, qa/ (Playwright, planned)
  verifier.py  checks a finding was closed  (planned)
  phases/      qa_phase.py, security_phase.py (planned)
  mcp_server.py, agent/, github.py, api.py   (planned)
tests/         mirrors src/
demo_app/      small project with a planted vulnerability (later)
dashboard/     UI (later)
```

Rule: `policy`, `verifier`, `tools` and `storage` never import from `agent/`.

## Setup

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env   # then fill in LLM_API_KEY, LLM_BASE_URL, LLM_MODEL (free-tier cloud provider)
./scripts/fetch_semgrep_rules.sh   # official Semgrep rules, pinned to one commit
brew install trivy
trivy fs --download-db-only        # Trivy vulnerability DB (scans never update it by themselves)
```

The Semgrep rules are Semgrep's official ones (no custom rules). They are pinned so the same
code always gives the same findings; the pinned commit is recorded as the rules version.


## Tests

```bash
pytest
```

## Status

Phases 0-4 done (skeleton, schema and storage, Semgrep, Trivy, policy engine). Next: the verifier (re-scan and decide closed / still_open / new).
