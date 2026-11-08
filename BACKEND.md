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
  tools/       base.py, fingerprint.py, security/semgrep.py + trivy.py, qa/ (Playwright, planned)
  verifier.py  checks a finding was closed
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

Phases 0-5 done (skeleton, schema and storage, Semgrep, Trivy, policy engine, verifier). Next: Playwright (QA tool).

## Internal MCP server (phase 7)

`python -m src.mcp_server` starts the only door the agent has into the system. Six tools:
`run_scan`, `verify_fix`, `get_findings`, `evaluate_policy`, `append_evidence`, `get_evidence`.
The logic lives in `src/service.py` (plain code); the server is a thin wrapper.

- The system picks the tools per stage (`src/scanning.py`) and the scan target (`SCAN_TARGET`); the agent picks neither.
- `append_evidence` is the agent's only write: explanation text, always labelled `source: "Yaqidh"`.
- There is no tool for status, closure, exceptions, human decisions or merging.
- A stage with no runner fails loudly instead of passing.
- A re-scan clears the stage's old decision; `evaluate_policy` must be called again.

## QA stage: security checks with Playwright (phase 6)

The `qa` stage runs security expectations written in advance (`qa_checks/maktabti_security.py`) in a real
browser against the running app. `src/tools/qa/app_server.py` starts the app on a free port with a throwaway database.

- A check that fails is retried twice. Passing on a retry = flaky: logged in `flaky_tests`, not a finding.
- A check that fails every time = one high finding. Its fingerprint comes from the check name and file, never from the error message; the message is kept in `detail`.
- If the app does not start or is not reachable, the scan stops with an error instead of reporting findings.
- One-time setup: `playwright install chromium`.

## Release flow (phase 8)

`src/phases/workflow.py` runs the flow; `src/phases/status.py` works out where a release stands from its evidence alone
(no stored status), and the merge gates come from that status.

1. `submit`: QA scan + policy. Fail = back to the developer. Pass = wait for the QA reviewer.
2. `approve(qa)`: merge to staging is allowed and the security scan starts.
3. Security fail = back to the developer. Pass = wait for the security reviewer.
4. `push` (developer fixed it in the same PR): QA re-runs by itself; if it passes, security re-scans and the verifier decides what closed.
   Only the security reviewer approves again. If QA now fails, security does not run.
5. `approve(security)`: merge to main is allowed.

- A human decision only covers the scan it was made on: a newer security scan makes an older approval not count.
- A QA approval stays valid across QA re-runs that still pass.
- Approvals, rejections and exceptions are human-only and are not in the MCP server. A rejection needs a reason.
- An exception needs a justification and an approver, and the policy still decides if it counts (medium only).
