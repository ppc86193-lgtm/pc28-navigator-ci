#!/usr/bin/env python3
"""
Minimal Mock MCP server used by tests/test_mcp_alignment_errors.py

Endpoints:
  - GET /health -> {"ok": true}
  - POST /tools/call -> error handling paths only
"""

from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


app = FastAPI()


@app.get("/health")
async def health() -> Dict[str, bool]:
    return {"ok": True}


@app.post("/tools/call")
async def tools_call(request: Request):
    # Parse raw body to control invalid JSON error reporting
    body = await request.body()
    try:
        payload: Any = json.loads(body.decode("utf-8") or "null")
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})

    if not isinstance(payload, dict):
        # Not required by tests, but guard against non-object JSON
        return JSONResponse(status_code=400, content={"error": "invalid_json"})

    if "tool" not in payload:
        return JSONResponse(status_code=400, content={"error": "invalid_tool"})

    args = payload.get("arguments")
    if not isinstance(args, dict):
        return JSONResponse(status_code=400, content={"error": "invalid_arguments"})

    # Success path not needed for tests; respond with a stub
    return JSONResponse(status_code=200, content={"ok": True})


if __name__ == "__main__":
    # Allow running directly: python mcp_mock_server.py
    import uvicorn

    uvicorn.run("mcp_mock_server:app", host="0.0.0.0", port=8000, reload=False)

