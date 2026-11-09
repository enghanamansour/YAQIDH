# Yaqidh backend (setup and layout)

An AI agent that accompanies a product through release stages
(`qa -> security`). It reads, explains and writes evidence text.
It never decides: pass/fail and finding status come only from plain code
(policy engine, verifier). Humans approve the final release.

## Layout

```
config/        policy.yaml (pass/fail rules), semgrep-rules/ (official, fetched, gitignored)
scripts/       fetch_semgrep_rules.sh
data/          releases/ (evidence JSON per release) and history/ (hash-chained event log); both gitignored
src/
  settings.py, envfile.py   settings; the one reader of .env (also used by backend/)
  schema.py, storage.py     data shapes and the evidence file
  policy.py, verifier.py    pass/fail and "is it closed" (plain code)
  tools/                    semgrep, trivy, playwright (qa)
  service.py, scanning.py   the operations the agent may use; the runners per stage
  mcp_server.py             the six tools (the agent's only door)
  agent/                    loop.py (tool-calling loop), prompt.py, skills.py + skills/ (7 SKILL.md)
  phases/                   status.py (where a release stands), workflow.py (human gates)
  gate.py, history.py       commit-bound merge gate; append-only hash-chained log
  api/                      app.py (FastAPI), main.py (uvicorn entry)
  github_sync.py, github_mcp.py   PR comment (through the GitHub MCP server) + commit statuses
frontend-preview/  the dashboard (from branch mohammed): server.py + web/; live.py reads our API
scripts/ci_scan.py, .github/workflows/yaqidh.yml   the CI job that scans the PR and sends the results
backend/       the team's FastAPI explainer/GitHub code (merged from branch hana); its Gate is superseded by src/gate.py
qa_checks/     the Playwright security checks; demo_app/ the site that is tested
tests/         mirrors src/
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

Phases 0-11 are built and tested (269 tests in `tests/`, 69 in `backend/tests/`). Not done yet: the full demo cycle (12), the dashboard (13), and a live run against a real GitHub repository.

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


## The agent (phase 9)

`python -m src.agent <release_id> [pull_request_opened|push|approved]` plays a GitHub event. `src/agent/loop.py` is a
tool-calling loop: the model (any OpenAI-compatible endpoint; Groq `openai/gpt-oss-120b` was used) chooses which tool to call.
Safety is in the tools, not the loop: the MCP server has no tool that decides, closes, approves or merges.
The code adds: an allow-list, argument checks against each tool's schema, a step limit, "words only" (no backticks) and
"never explain the same finding twice" checks on `append_evidence`, small batches of findings per request, and old steps
dropped from the conversation (the Groq free tier allows 8000 tokens per minute; a 429 is waited out).

- `run_scan` / `verify_fix` for the security stage are refused until QA passed and a QA reviewer approved, checked inside
  `service.py` so the model cannot skip a stage.
- Skills (`src/agent/skills/<name>/SKILL.md`, header with `name` and `description`) are written from the OWASP Cheat Sheets.
  The model lists them and reads the one that fits; an invented name is refused. Adding a folder adds a skill.
- Findings now carry `fixed_version` (Trivy), `cwe` and `confidence` (Semgrep). Rules that flag the same line are merged into one finding.
- `LLM_MODEL=llama-3.3-70b-versatile` is no longer available on the free Groq tier: set `LLM_MODEL=openai/gpt-oss-120b` in `.env`.

## The API, the gate and the history (phase 10)

`uvicorn src.api.main:app` (needs `API_TOKEN`; every route except `/health` needs the `X-API-Token` header; with no token configured nothing is allowed).

- `POST /releases/{id}/events` starts the agent. `GET /releases`, `/releases/{id}`, `/status`, `/findings?stage=`, `/history`, `/history/verify` are for the dashboard.
- `POST /releases/{id}/stages/{qa|security}/approve|reject|exceptions` are the people's decisions (a rejection needs a reason; an exception needs a justification and an approver).
- `GET /gate?release_id=&commit=&target=staging|main`: allowed only if the commit is the newest one, the needed stages were scanned on exactly that commit, and the status (policy + human approvals) allows it. A push after an approval closes the gate until the new commit is scanned.
- History (`data/history/<id>.jsonl`): every event, scan, policy decision, explanation and human decision, each line hashed with the one before it. `/history/verify` shows where the chain breaks. This detects edits; it does not stop someone who rewrites the whole file.

## GitHub (phase 11)

`POST /github/webhook` accepts only events signed with `GITHUB_WEBHOOK_SECRET` (no secret configured = refuse all). It handles
`pull_request` opened/reopened/synchronize, starts the agent, then posts one comment that is edited in place, and two commit
statuses, `yaqidh/staging` and `yaqidh/main`, taken from the same gate. Require those two statuses in the branch protection and GitHub
itself refuses a merge the gate would refuse. A failed post is logged and never changes a decision. Tested with a fake GitHub only.


## CI results, GitHub MCP and the dashboard

- **CI sends the security results** (`SCAN_SOURCE=ci`): `.github/workflows/yaqidh.yml` runs `scripts/ci_scan.py` on the pull request's own code with our Semgrep/Trivy tools (so fingerprints are made where the code is) and POSTs to `/releases/{id}/scan-results`.
  The server keeps them for the head commit; they are used when security's turn comes (after the QA approval) or at once if it is already its turn. Results for an old commit, from one tool only, or without versions are refused, and a closure/exception/explanation inside them is wiped. Workflow file not run on a real runner yet.
- **GitHub MCP:** with `GITHUB_MCP=1` the PR comment is written through the official GitHub MCP server (`issue_read`, `add_issue_comment`, `update_issue_comment`); the agent has a `post_pr_comment` tool that takes only a release id, the text is built by our code. That server has no tool for commit statuses, so `yaqidh/staging` and `yaqidh/main` still use the direct API client. Tested against a stand-in server with the same tool names, not the real one.
- **Dashboard live mode:** `python frontend-preview/server.py --live --api-url http://127.0.0.1:8000` (token in `YAQIDH_API_TOKEN`). Login, roles, discussions and admin are the dashboard's own (in memory); releases, findings, explanations and decisions come from our API, and approve/reject are POSTed to it with the logged-in account as the person. Without `--live` the seeded demo is unchanged. The dashboard's old copy of the backend in `frontend-preview/backend/` is only used by the demo.
