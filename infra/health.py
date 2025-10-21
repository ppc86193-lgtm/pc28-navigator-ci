from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Tuple

from google.cloud import bigquery

from app_config import Config


def basic(service: str, revision: str = "real-cloud-20250918-063639") -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": service,
        "timestamp": datetime.now().isoformat(),
        "revision": revision,
        "evidence": "machine_verified",
    }


def deep(client: bigquery.Client, cfg: Config) -> Tuple[Dict[str, Any], int]:
    checks = []

    # BigQuery connectivity
    list(client.query("SELECT 1 AS test").result())
    checks.append({"component": "bigquery", "status": "ok"})

    # Heartbeat table
    heartbeat_sql = f"""
    SELECT COUNT(*) AS count
    FROM `{cfg.table_heartbeats}`
    WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 10 MINUTE)
    """
    hb_rows = list(client.query(heartbeat_sql).result())
    hb_ok = hb_rows and hb_rows[0].count > 0
    checks.append({"component": "heartbeat", "status": "ok" if hb_ok else "fail"})

    # Data freshness
    fresh_sql = f"""
    SELECT TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(timestamp), MINUTE) AS minutes_ago
    FROM `{cfg.view_draws}`
    """
    fr_rows = list(client.query(fresh_sql).result())
    fresh_ok = fr_rows and fr_rows[0].minutes_ago < cfg.freshness_minutes_ok
    checks.append({"component": "data_freshness", "status": "ok" if fresh_ok else "stale"})

    overall = all(c["status"] == "ok" for c in checks)
    payload = {
        "status": "healthy" if overall else "degraded",
        "mode": "deep",
        "checks": checks,
        "timestamp": datetime.now().isoformat(),
    }
    return payload, (200 if overall else 503)

