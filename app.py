"""
Deprecated: prefer using cloud_app.app
This module re-exports the Flask app for compatibility.
"""

from cloud_app import app  # noqa: F401

if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
