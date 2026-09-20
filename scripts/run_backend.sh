#!/usr/bin/env bash
# Start the DreamCoder FastAPI backend and ensure the local Ollama runtime is online.
set -e
cd "$(dirname "$0")/../"

export OLLAMA_MODEL="tinyllama:latest"
export DREAMCODER_OLLAMA_PRIMARY_MODEL="tinyllama:latest"
export DREAMCODER_LOCAL_BACKEND="ollama"
export OLLAMA_BASE_URL="http://localhost:11434"
export DREAMCODER_OLLAMA_PRIMARY_URL="http://localhost:11434"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed. Install it first from https://ollama.com/download"
  exit 1
fi

if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "→ Starting local Ollama server…"
  ollama serve >/tmp/dreamcoder_ollama.log 2>&1 &
  for _ in $(seq 1 30); do
    if curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
      break
    fi
    python - <<'PY'
import time
time.sleep(0.5)
PY
  done
fi

if ! curl -fsS http://localhost:11434/api/tags | grep -q 'tinyllama'; then
  echo "→ Pulling the default local model: tinyllama:latest"
  ollama pull tinyllama:latest
fi

cd backend

echo "→ Installing dependencies (if needed)…"
pip install -q -r ../requirements.txt
echo "→ Starting DreamCoder API on http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
exec uvicorn main:app --reload --host 0.0.0.0 --port 8000
