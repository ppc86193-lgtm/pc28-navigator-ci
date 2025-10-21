"""
Deprecated: unified under FastAPI `ai_service.app`.
This module re-exports the ASGI app for backward compatibility.
"""
from ai_service import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
