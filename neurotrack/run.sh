#!/usr/bin/env bash
# Lance le backend (FastAPI) + le frontend (Vite). Ctrl-C arrete les deux.
set -e
cd "$(dirname "$0")"

./.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8077 --log-level warning &
BACK=$!
trap "kill $BACK 2>/dev/null" EXIT

cd frontend
npm run dev -- --port 5173 --host 127.0.0.1
