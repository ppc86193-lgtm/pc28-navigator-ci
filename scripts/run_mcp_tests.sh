#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR" || exit 1

export ENABLE_MCP_TESTS=1

# Prefer local venv python if available for installation feedback
if [[ -x .venv/bin/python ]]; then
  PY=.venv/bin/python
else
  PY=$(command -v python3 || command -v python)
fi

echo "Preparing environment for MCP tests ..."
$PY -m pip install -q fastapi uvicorn requests >/dev/null 2>&1 || true

exec ./scripts/run_tests.sh
