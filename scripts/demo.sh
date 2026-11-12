#!/usr/bin/env bash
# One-command demo (Mac/Linux): starts a private API and dashboard, opens the browser, then plays a developer
# through the whole loop (pull request, QA, security, approvals) while the dashboard shows it.
#
#   scripts/demo.sh              people press approve / return / exception in the dashboard (best for showing it)
#   scripts/demo.sh auto         the script presses them too (a fast check that the loop works)
#   scripts/demo.sh template     (or "auto template") explanations come from the fixed template: no model, no tokens
#
# It uses its own ports (API 8010, dashboard 8770) and its own temporary data folder, so a dashboard you already
# run on 8765 and its data are not touched. No GitHub token is set: nothing is posted to GitHub.
# demo_app is put back with `git checkout` before and after, so it must have no uncommitted changes.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$(pwd)/.venv/bin/python}"
API_PORT=8010
DASH_PORT=8770

MODE_AUTO=0
for arg in "$@"; do
  case "$arg" in
    auto) MODE_AUTO=1 ;;
    template) export AGENT_MODE=template ;;
    *) echo "unknown option: $arg (use: auto, template)" >&2; exit 1 ;;
  esac
done

if [ ! -x "$PY" ]; then
  echo "The Python environment is missing. Run once: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' flask semgrep" >&2
  exit 1
fi
for port in $API_PORT $DASH_PORT; do
  if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop whatever uses it and run again." >&2
    exit 1
  fi
done
if [ -n "$(git status --porcelain demo_app)" ]; then
  echo "demo_app has uncommitted changes; the demo resets it. Commit or stash them first." >&2
  exit 1
fi

API_TOKEN="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(24))')"
export API_TOKEN
export YAQIDH_API_TOKEN="$API_TOKEN"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/yaqidh-demo.XXXXXX")"
export DATA_DIR="$WORK/releases"
export HISTORY_DIR="$WORK/history"
export EVIDENCE_PATH="$WORK/evidence.jsonl"
export SCAN_SOURCE=local
export GITHUB_TOKEN=""
export GITHUB_MCP=0
export PYTHONUTF8=1

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  "$PY" scripts/demo_fix.py reset >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT INT TERM

echo "Putting the demo app back to its starting state..."
"$PY" scripts/demo_fix.py reset

echo "Starting the API on port $API_PORT..."
"$PY" -m uvicorn src.api.main:app --port "$API_PORT" >"$WORK/api.log" 2>&1 &
PIDS+=($!)
for _ in $(seq 1 30); do
  if curl -s "http://127.0.0.1:$API_PORT/health" 2>/dev/null | grep -q ok; then break; fi
  sleep 1
done
curl -s "http://127.0.0.1:$API_PORT/health" | grep -q ok || { echo "The API did not start. See $WORK/api.log" >&2; cat "$WORK/api.log" >&2; exit 1; }

echo "Starting the dashboard on port $DASH_PORT..."
"$PY" frontend-preview/server.py --live --api-url "http://127.0.0.1:$API_PORT" --port "$DASH_PORT" >"$WORK/dashboard.log" 2>&1 &
PIDS+=($!)
sleep 3
URL="http://127.0.0.1:$DASH_PORT/dashboard"
command -v open >/dev/null 2>&1 && open "$URL" || true

echo
echo "The dashboard: $URL"
echo "Accounts: developer, qa, security (the demo password is in frontend-preview/server.py, PASSWORD)."
echo
if [ "$MODE_AUTO" = 0 ]; then
  read -r -p "Open the dashboard and sign in as qa, then press Enter to start the demo... " _
  HUMAN=(--human-approvals --exception-in-dashboard)
else
  HUMAN=()
fi

# When people run the demo, the developer's fix waits for them: they show the problems first, then press Enter.
if [ "$MODE_AUTO" = 0 ]; then
  ASK_QA="printf '\n      >>> اعرضي مشاكل الجودة للجنة. اضغطي Enter لما تبين المطوّر يصلحها... '; read -r _ </dev/tty; "
  ASK_SEC="printf '\n      >>> اعرضي ملاحظات الأمن للجنة. اضغطي Enter لما تبين المطوّر يصلحها... '; read -r _ </dev/tty; "
else
  ASK_QA=""; ASK_SEC=""
fi

cd backend
"$PY" scripts/walkthrough.py --url "http://127.0.0.1:$API_PORT" ${HUMAN[@]+"${HUMAN[@]}"} \
  --on-fix-qa "${ASK_QA}'$PY' ../scripts/demo_fix.py qa" \
  --on-fix-security "${ASK_SEC}'$PY' ../scripts/demo_fix.py security" || STATUS=$?
cd ..
echo
echo "Putting the demo app back as it was..."
"$PY" scripts/demo_fix.py reset
echo "Done (exit ${STATUS:-0}). Press Enter to stop the servers."
read -r _ || true
