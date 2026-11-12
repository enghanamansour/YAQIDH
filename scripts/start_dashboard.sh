#!/usr/bin/env bash
# Starts the dashboard in live mode (port 8765). It talks to the Yaqidh API on port 8000 and uses the SAME API_TOKEN
# as the API (read from .env, or from the environment). If no API is running on port 8000 yet, this starts one.
# Stop with Ctrl-C.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"

# the token: environment first, then .env. A random token here would never match the real API (everything would look empty).
if [ -z "${API_TOKEN:-}" ]; then
  API_TOKEN="$("$PY" -c 'from src.envfile import parse; from pathlib import Path; print(parse(Path(".env").read_text()).get("API_TOKEN", ""))' 2>/dev/null || true)"
fi
if [ -z "${API_TOKEN:-}" ]; then
  echo "API_TOKEN is not set (in the environment or .env). Add it to .env first." >&2
  exit 1
fi
export API_TOKEN
export YAQIDH_API_TOKEN="$API_TOKEN"

API_PID=""
if curl -s --max-time 3 http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "using the Yaqidh API that is already running on port 8000"
else
  "$PY" -m uvicorn src.api.main:app --port 8000 &
  API_PID=$!
  trap 'kill $API_PID 2>/dev/null || true' EXIT
  sleep 3
fi
"$PY" frontend-preview/server.py --live --api-url http://127.0.0.1:8000 --port 8765
