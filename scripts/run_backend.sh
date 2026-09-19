#!/usr/bin/env bash
# Start the DreamCoder FastAPI backend
set -e
cd "$(dirname "$0")/../backend"
echo "→ Installing dependencies (if needed)…"
pip install -q -r ../requirements.txt
echo "→ Starting DreamCoder API on http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
exec uvicorn main:app --reload --host 0.0.0.0 --port 8000
