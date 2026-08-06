#!/usr/bin/env bash
# One-command local run: sets up a venv, installs deps, creates .env if missing, starts the server.
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "Created .env from .env.example."
  echo "Add your ANTHROPIC_API_KEY (and optionally SLACK_WEBHOOK_URL) to .env before processing a meeting."
  echo ""
fi

mkdir -p data

echo "Starting server at http://localhost:8000"
uvicorn app.main:app --reload --port 8000
