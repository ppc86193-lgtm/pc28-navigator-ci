#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR" || exit 1

# Prefer local venv python if available
if [[ -x .venv/bin/python ]]; then
  PY=.venv/bin/python
else
  PY=$(command -v python3 || command -v python)
fi

echo "Using Python: $($PY -V 2>&1)"

# Ensure pytest tooling is available
echo "Installing core test deps (pytest, pytest-asyncio) ..."
$PY -m pip install -q --upgrade pip >/dev/null 2>&1 || true
$PY -m pip install -q pytest pytest-asyncio >/dev/null 2>&1 || true
if [[ "${COVERAGE:-0}" == "1" ]]; then
  echo "Installing coverage plugin (pytest-cov) ..."
  $PY -m pip install -q pytest-cov >/dev/null 2>&1 || true
fi

# Try to install project requirements, but don't fail the run if a wheel is unavailable
if [[ -f requirements.txt ]]; then
  echo "Installing requirements.txt (best-effort) ..."
  $PY -m pip install -q -r requirements.txt >/dev/null 2>&1 || echo "requirements install had non-critical issues; continuing"
fi

export PYTHONPATH="${ROOT_DIR}:$PYTHONPATH"

# Optionally start local MCP mock server if ENABLE_MCP_TESTS=1
MCP_PID=""
cleanup() {
  if [[ -n "$MCP_PID" ]]; then
    kill "$MCP_PID" 2>/dev/null || true
    wait "$MCP_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [[ "${ENABLE_MCP_TESTS:-0}" == "1" ]]; then
  echo "MCP tests enabled; ensuring FastAPI/uvicorn/requests are installed ..."
  $PY -m pip install -q fastapi uvicorn requests >/dev/null 2>&1 || true
  echo "Launching local Mock MCP server ..."
  $PY mcp_mock_server.py &
  MCP_PID=$!
  # Wait for server to be healthy
  for i in {1..30}; do
    if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
      echo "Mock MCP server is healthy."
      break
    fi
    sleep 1
  done
fi

echo "Running pytest on tests/ ..."
if [[ "${COVERAGE:-0}" == "1" ]]; then
  # Generate XML for CI upload, print missing lines (skip covered)
  $PY -m pytest --cov=. --cov-report=term-missing:skip-covered --cov-report=xml tests
else
  $PY -m pytest -q tests
fi
