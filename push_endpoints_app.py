"""
Deprecated: endpoints moved into cloud_app.py

This file remains as a shim to keep backwards compatibility.
"""

import os

from cloud_app import app  # re-export Flask app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
