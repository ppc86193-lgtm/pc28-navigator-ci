#!/usr/bin/env bash
set -euo pipefail

echo "==> Emergency actions started"

ACTION=${1:-help}

case "$ACTION" in
  clear-cache)
    echo "-- clearing python caches"
    find . -type d -name __pycache__ -exec rm -rf {} + || true
    ;;
  restart-mock-mcp)
    echo "-- restarting mock mcp servers"
    pkill -f start_mock_mcp_servers.py || true
    sleep 1
    nohup python3 scripts/start_mock_mcp_servers.py >/tmp/mock_mcp.log 2>&1 &
    echo "mock mcp restarted (log: /tmp/mock_mcp.log)"
    ;;
  degrade-mode)
    echo "-- enabling degrade mode (placeholder flag file)"
    mkdir -p .runtime
    echo "degraded" > .runtime/mode
    ;;
  help|*)
    echo "Usage: $0 [clear-cache|restart-mock-mcp|degrade-mode]"
    ;;
esac

echo "==> Done"
