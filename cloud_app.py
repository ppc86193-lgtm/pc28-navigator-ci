import logging
import os
from datetime import datetime
from typing import Any, Dict

from flask import Flask, jsonify, request
from google.cloud import bigquery

from app_config import Config
from infra.bq import get_kpi_today, get_latest_battle, insert_push_log
from infra.health import basic as health_basic
from infra.health import deep as health_deep

app = Flask(__name__)

# Logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Config and shared BigQuery client
CFG = Config()
bq_client = bigquery.Client(project=CFG.project, location=CFG.location)


def _json_response(payload: Dict[str, Any], status: int = 200):
    resp = jsonify(payload)
    resp.status_code = status
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


@app.route("/health", methods=["GET"])  # unified basic/deep
def health():
    mode = request.args.get("mode", "basic")
    if mode != "deep":
        return _json_response(health_basic(service="PC28真正的监控服务"))

    # Deep health checks
    try:
        payload, code = health_deep(bq_client, CFG)
        return _json_response(payload, code)
    except Exception as e:
        logger.exception("Deep health error")
        return _json_response(
            {
                "status": "error",
                "mode": "deep",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            500,
        )


@app.route("/webhook", methods=["POST"])
def webhook():
    _ = request.get_json(silent=True)
    # 处理Telegram webhook
    return jsonify({"ok": True, "processed": True})


@app.route("/heartbeat")
def heartbeat():
    # 返回心跳信息

    try:
        query = """
        SELECT
          TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(ts), MINUTE) AS mins_ago,
          ANY_VALUE(rev) as revision,
          MAX(max_period) as latest_period
        FROM `{table}`
        WHERE svc = 'pc28-bot-final' AND ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
        """
        table = CFG.table_heartbeats
        results = list(bq_client.query(query.format(table=table)).result())
        if results:
            row = results[0]
            return _json_response(
                {
                    "heartbeat_status": "active",
                    "minutes_ago": row.mins_ago,
                    "revision": row.revision,
                    "latest_period": row.latest_period,
                    "evidence_source": "bigquery_heartbeat_table",
                }
            )
        else:
            return _json_response({"heartbeat_status": "no_data"})
    except Exception as e:
        logger.exception("Heartbeat error")
        return _json_response({"heartbeat_status": "error", "error": str(e)}, 500)


@app.route("/push/kpi", methods=["POST"])
def push_kpi():
    if CFG.disable_push:
        return _json_response({"status": "disabled"}, 403)
    try:
        kpi = get_kpi_today(bq_client, CFG)
        if not kpi:
            return _json_response({"status": "no_data"}, 404)

        insert_push_log(
            bq_client,
            CFG,
            endpoint="/push/kpi",
            message_type="KPI_REPORT",
            status="SUCCESS",
            message_id=f"kpi_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )

        return _json_response(
            {
                "status": "success",
                "kpi_data": kpi,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.exception("push_kpi error")
        return _json_response({"status": "error", "error": str(e)}, 500)


@app.route("/push/battle", methods=["POST"])
def push_battle():
    if CFG.disable_push:
        return _json_response({"status": "disabled"}, 403)
    try:
        battle = get_latest_battle(bq_client, CFG)
        if not battle:
            return _json_response({"status": "no_data"}, 404)

        insert_push_log(
            bq_client,
            CFG,
            endpoint="/push/battle",
            message_type="BATTLE_RESULT",
            status="SUCCESS",
            message_id=f"battle_{battle['issue']}",
        )

        return _json_response(
            {
                "status": "success",
                "battle_data": battle,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.exception("push_battle error")
        return _json_response({"status": "error", "error": str(e)}, 500)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
