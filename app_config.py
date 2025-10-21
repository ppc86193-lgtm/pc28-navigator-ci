import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # Google Cloud
    project: str = os.getenv(
        "GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "wprojectl")
    )
    location: str = os.getenv("GCP_LOCATION", "us-central1")

    # BigQuery resources
    table_heartbeats: str = os.getenv(
        "HEARTBEAT_TABLE", "wprojectl.pc28_monitor.heartbeats"
    )
    view_draws: str = os.getenv("DRAWS_VIEW", "wprojectl.pc28.draws_14w_dedup_v")
    table_kpi_daily: str = os.getenv("KPI_TABLE", "wprojectl.pc28.kpi_daily_base")
    table_push_logs: str = os.getenv(
        "PUSH_LOGS_TABLE", "wprojectl.pc28_monitor.push_logs"
    )

    # Health thresholds
    freshness_minutes_ok: int = int(os.getenv("FRESHNESS_MINUTES_OK", "60"))

    # Feature flags
    disable_push: bool = os.getenv("DISABLE_PUSH", "0") == "1"
