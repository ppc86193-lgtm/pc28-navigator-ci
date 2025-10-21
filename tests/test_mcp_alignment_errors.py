#!/usr/bin/env python3
"""
MCP 文档对齐：错误路径用例（Mock MCP）
仅在 ENABLE_MCP_TESTS=1 时运行。
"""

import os

import pytest
import requests

ENABLED = os.environ.get("ENABLE_MCP_TESTS", "0") == "1"


@pytest.mark.skipif(not ENABLED, reason="ENABLE_MCP_TESTS not set")
def test_tools_call_invalid_json():
    r = requests.post("http://localhost:8000/tools/call", data="not-json", timeout=5)
    assert r.status_code == 400
    assert r.json().get("error") == "invalid_json"


@pytest.mark.skipif(not ENABLED, reason="ENABLE_MCP_TESTS not set")
def test_tools_call_missing_tool():
    payload = {"arguments": {"a": 1}}
    r = requests.post("http://localhost:8000/tools/call", json=payload, timeout=5)
    assert r.status_code == 400
    assert r.json().get("error") == "invalid_tool"


@pytest.mark.skipif(not ENABLED, reason="ENABLE_MCP_TESTS not set")
def test_tools_call_invalid_arguments_type():
    payload = {"tool": "analyze_data", "arguments": "not-a-dict"}
    r = requests.post("http://localhost:8000/tools/call", json=payload, timeout=5)
    assert r.status_code == 400
    assert r.json().get("error") == "invalid_arguments"
