from __future__ import annotations

from typing import Any, Dict, Optional

from google.cloud import bigquery

from app_config import Config


def get_client(cfg: Optional[Config] = None) -> bigquery.Client:
    cfg = cfg or Config()
    return bigquery.Client(project=cfg.project, location=cfg.location)


def query(
    client: bigquery.Client, sql: str, job_config: Optional[bigquery.QueryJobConfig] = None
):
    return list(client.query(sql, job_config=job_config).result())


def insert_push_log(
    client: bigquery.Client,
    cfg: Config,
    *,
    endpoint: str,
    message_type: str,
    status: str,
    message_id: str,
):
    sql = f"""
    INSERT INTO `{cfg.table_push_logs}` (timestamp, endpoint, message_type, status, message_id)
    VALUES (CURRENT_TIMESTAMP(), @endpoint, @message_type, @status, @message_id)
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("endpoint", "STRING", endpoint),
            bigquery.ScalarQueryParameter("message_type", "STRING", message_type),
            bigquery.ScalarQueryParameter("status", "STRING", status),
            bigquery.ScalarQueryParameter("message_id", "STRING", message_id),
        ]
    )
    client.query(sql, job_config=job_config).result()


def get_kpi_today(client: bigquery.Client, cfg: Config) -> Optional[Dict[str, Any]]:
    sql = f"""
    SELECT acc_global, ev_global, coverage_global, traffic_light
    FROM `{cfg.table_kpi_daily}`
    WHERE day_id = CURRENT_DATE('Asia/Shanghai')
    LIMIT 1
    """
    rows = query(client, sql)
    if not rows:
        return None
    row = rows[0]
    return {
        "accuracy": float(row.acc_global) if getattr(row, "acc_global", None) is not None else 0.0,
        "expected_value": float(row.ev_global) if getattr(row, "ev_global", None) is not None else 0.0,
        "coverage": float(row.coverage_global)
        if getattr(row, "coverage_global", None) is not None
        else 0.0,
        "traffic_light": getattr(row, "traffic_light", None),
    }


def get_latest_battle(client: bigquery.Client, cfg: Config) -> Optional[Dict[str, Any]]:
    sql = f"""
    SELECT issue, timestamp, a, b, c, (a + b + c) AS sum
    FROM `{cfg.view_draws}`
    ORDER BY timestamp DESC
    LIMIT 1
    """
    rows = query(client, sql)
    if not rows:
        return None
    row = rows[0]
    total = int(row.sum) if getattr(row, "sum", None) is not None else None
    return {
        "issue": getattr(row, "issue", None),
        "timestamp": row.timestamp.isoformat() if getattr(row, "timestamp", None) else None,
        "numbers": [int(row.a), int(row.b), int(row.c)],
        "sum": total,
        "size": "BIG" if (total is not None and total >= 14) else "SMALL",
        "odd_even": "ODD" if (total is not None and total % 2 == 1) else "EVEN",
    }

