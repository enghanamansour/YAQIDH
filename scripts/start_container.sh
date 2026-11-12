#!/usr/bin/env bash
# Starts Yaqidh inside the container: the API on a private local port, then the dashboard on $PORT.
# Settings come from the environment:
#   PORT                   where the dashboard listens (default 8080; hosting platforms set it)
#   YAQIDH_DEMO_PASSWORD   the password of the demo accounts (developer, qa, security); set your own
#   YAQIDH_ALLOWED_HOSTS   the public host name(s), comma separated; without it the dashboard only answers on localhost
#   API_PORT               the private port of the API inside the container (default 8010)
#   API_TOKEN              shared secret between the dashboard and the API (a random one is made if it is not set)
#   AGENT_MODE             "template" (default, no AI model and no tokens) or a model mode
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8080}"
API_PORT="${API_PORT:-8010}"
if [ -z "${API_TOKEN:-}" ]; then
  API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(24))')"
fi
export API_TOKEN
export YAQIDH_API_TOKEN="$API_TOKEN"
export DATA_DIR="${DATA_DIR:-/data/releases}"
export HISTORY_DIR="${HISTORY_DIR:-/data/history}"
export EVIDENCE_PATH="${EVIDENCE_PATH:-/data/evidence.jsonl}"
export SCAN_SOURCE=local
export GITHUB_TOKEN=""
export GITHUB_MCP=0
export AGENT_MODE="${AGENT_MODE:-template}"
mkdir -p "$DATA_DIR" "$HISTORY_DIR" "$(dirname "$EVIDENCE_PATH")"

python -m uvicorn src.api.main:app --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
  if curl -s "http://127.0.0.1:$API_PORT/health" 2>/dev/null | grep -q ok; then break; fi
  sleep 1
done
curl -s "http://127.0.0.1:$API_PORT/health" | grep -q ok || { echo "The API did not start." >&2; exit 1; }

python frontend-preview/server.py --live --api-url "http://127.0.0.1:$API_PORT" --host 0.0.0.0 --port "$PORT"
