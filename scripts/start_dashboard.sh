#!/usr/bin/env bash
# Starts the Yaqidh API (port 8000) and the dashboard in live mode (port 8765) on the real data folders (data/).
# Empty folders mean the dashboard shows zeros until a real release arrives. Stop both with Ctrl-C.
# If API_TOKEN is not set (in the environment) a random one is made for this session.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"
export API_TOKEN="${API_TOKEN:-$($PY -c 'import secrets;print(secrets.token_urlsafe(24))')}"
export YAQIDH_API_TOKEN="$API_TOKEN"

"$PY" -m uvicorn src.api.main:app --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT
sleep 3
"$PY" frontend-preview/server.py --live --api-url http://127.0.0.1:8000 --port 8765
