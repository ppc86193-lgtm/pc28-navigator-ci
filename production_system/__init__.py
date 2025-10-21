"""Production system package initialization.

This module exposes the core production analysis components so they can be
reused by other entry points (例如 :mod:`navigator_core`).  By keeping the
imports lightweight we avoid importing heavy optional dependencies (e.g.
``google.cloud``) at module import time.  New integrations should be added
here so callers can access them from a single namespace.
"""

from .modules import ProductionFrequencyModule, ProductionTurningPointModule
from .predictor_bridge import PredictorBridge

__all__ = [
    "ProductionFrequencyModule",
    "ProductionTurningPointModule",
    "PredictorBridge",
]


