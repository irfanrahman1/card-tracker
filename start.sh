#!/usr/bin/env bash
# Starts Card Tracker: the FastAPI backend and the React frontend together.
# First run installs everything (takes a minute). Press Ctrl+C to stop both.
set -e
cd "$(dirname "$0")"

# --- Backend ---
if [ ! -d backend/venv ]; then
  echo "▶ Creating Python virtual environment…"
  python3 -m venv backend/venv
fi
echo "▶ Installing backend packages…"
backend/venv/bin/pip install -q -r backend/requirements.txt

# --- Frontend ---
if ! command -v npm >/dev/null; then
  echo "✖ Node.js is not installed. On macOS run: brew install node   (then run ./start.sh again)"
  exit 1
fi
if [ ! -d frontend/node_modules ]; then
  echo "▶ Installing frontend packages (first run only)…"
  (cd frontend && npm install --silent)
fi

# Start the backend in the background and stop it when this script exits.
echo "▶ Starting backend on http://localhost:8000"
(cd backend && exec venv/bin/uvicorn app.main:app --port 8000) &
BACKEND_PID=$!
trap 'echo; echo "Stopping…"; kill $BACKEND_PID 2>/dev/null' EXIT INT TERM

echo "▶ Starting frontend…"
echo ""
echo "   👉 Open http://localhost:5173 in your browser"
echo ""
cd frontend && npm run dev
