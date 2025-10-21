from datetime import datetime

from flask import Flask, jsonify, request
from google.cloud import bigquery

app = Flask(__name__)
bq_client = bigquery.Client(project="wprojectl", location="us-central1")


@app.route("/push/kpi", methods=["POST"])
def push_kpi():
    try:
        # 获取KPI数据并推送
        kpi_query = """
        SELECT acc_global, ev_global, coverage_global, traffic_light
        FROM `wprojectl.pc28.kpi_daily_base`
        WHERE day_id = CURRENT_DATE('Asia/Shanghai')
        LIMIT 1
        """

        results = list(bq_client.query(kpi_query).result())

        if results:
            row = results[0]

            # 记录推送日志
            log_query = f"""
            INSERT INTO `wprojectl.pc28_monitor.push_logs`
            (timestamp, endpoint, message_type, status, message_id)
            VALUES
            (CURRENT_TIMESTAMP(), '/push/kpi', 'KPI_REPORT', 'SUCCESS', 'kpi_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            """

            bq_client.query(log_query).result()

            return jsonify(
                {
                    "status": "success",
                    "kpi_data": {
                        "accuracy": float(row.acc_global) if row.acc_global else 0,
                        "expected_value": float(row.ev_global) if row.ev_global else 0,
                        "coverage": (
                            float(row.coverage_global) if row.coverage_global else 0
                        ),
                        "traffic_light": row.traffic_light,
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return jsonify({"status": "no_data"}), 404

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/push/battle", methods=["POST"])
def push_battle():
    try:
        # 获取最新开奖并推送
        battle_query = """
        SELECT issue, timestamp, a, b, c, (a + b + c) as sum
        FROM `wprojectl.pc28.draws_14w_dedup_v`
        ORDER BY timestamp DESC
        LIMIT 1
        """

        results = list(bq_client.query(battle_query).result())

        if results:
            row = results[0]

            # 记录推送日志
            log_query = f"""
            INSERT INTO `wprojectl.pc28_monitor.push_logs`
            (timestamp, endpoint, message_type, status, message_id)
            VALUES
            (CURRENT_TIMESTAMP(), '/push/battle', 'BATTLE_RESULT', 'SUCCESS', 'battle_{row.issue}')
            """

            bq_client.query(log_query).result()

            return jsonify(
                {
                    "status": "success",
                    "battle_data": {
                        "issue": row.issue,
                        "timestamp": row.timestamp.isoformat(),
                        "numbers": [row.a, row.b, row.c],
                        "sum": row.sum,
                        "size": "BIG" if row.sum >= 14 else "SMALL",
                        "odd_even": "ODD" if row.sum % 2 == 1 else "EVEN",
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return jsonify({"status": "no_data"}), 404

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "mode": "basic"})


@app.route("/health", methods=["GET"])
def health_deep():
    mode = request.args.get("mode", "basic")

    if mode == "deep":
        try:
            # 深度健康检查
            health_checks = []

            # 检查BigQuery连接
            test_query = "SELECT 1 as test"
            list(bq_client.query(test_query).result())
            health_checks.append({"component": "bigquery", "status": "ok"})

            # 检查心跳表
            heartbeat_query = """
            SELECT COUNT(*) as count
            FROM `wprojectl.pc28_monitor.heartbeats`
            WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 10 MINUTE)
            """
            heartbeat_results = list(bq_client.query(heartbeat_query).result())
            heartbeat_ok = (
                heartbeat_results[0].count > 0 if heartbeat_results else False
            )
            health_checks.append(
                {"component": "heartbeat", "status": "ok" if heartbeat_ok else "fail"}
            )

            # 检查数据新鲜度
            freshness_query = """
            SELECT
              TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(timestamp), MINUTE) as minutes_ago
            FROM `wprojectl.pc28.draws_14w_dedup_v`
            """
            freshness_results = list(bq_client.query(freshness_query).result())
            data_fresh = (
                freshness_results[0].minutes_ago < 60 if freshness_results else False
            )
            health_checks.append(
                {
                    "component": "data_freshness",
                    "status": "ok" if data_fresh else "stale",
                }
            )

            overall_health = all(check["status"] == "ok" for check in health_checks)

            return jsonify(
                {
                    "status": "healthy" if overall_health else "degraded",
                    "mode": "deep",
                    "checks": health_checks,
                    "timestamp": datetime.now().isoformat(),
                }
            ), (200 if overall_health else 503)

        except Exception as e:
            return (
                jsonify(
                    {
                        "status": "error",
                        "mode": "deep",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
                500,
            )
    else:
        return jsonify({"status": "healthy", "mode": "basic"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
