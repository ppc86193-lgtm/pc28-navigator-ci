#!/usr/bin/env python3
"""
Agent: realtime_monitor
任务: 实时监控生产环境状态，生成真实可审计回执
监督者: 项目总指挥大人
"""

import json
from datetime import datetime

from google.cloud import bigquery


class RealtimeMonitorAgent:
    """实时监控Agent"""

    def __init__(self):
        self.agent_id = "realtime_monitor"
        self.task_name = "实时监控"
        self.priority = "HIGH"
        self.supervisor = "项目总指挥大人"

        # 配置
        self.project_id = "wprojectl"
        self.ds_lab = "pc28_lab"
        self.ds_draw = "pc28"
        self.location = "us-central1"
        self.timezone = "Asia/Shanghai"

        print(f"🤖 Agent {self.agent_id} 已就位")
        print(f"👑 监督者: {self.supervisor}")

    def monitor_production_status(self):
        """监控生产状态"""
        print(f"\n📊 {self.agent_id} 开始监控生产环境...")

        try:
            bq_client = bigquery.Client(project=self.project_id, location=self.location)

            # 1. 监控开奖数据新鲜度
            draws_query = f"""
            SELECT
              COUNT(*) as today_draws,
              MAX(timestamp) as latest_draw,
              MIN(timestamp) as first_draw,
              TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(timestamp), MINUTE) as minutes_since_last
            FROM `{self.project_id}.{self.ds_draw}.draws_14w_dedup_v`
            WHERE DATE(timestamp, '{self.timezone}') = CURRENT_DATE('{self.timezone}')
            """

            draws_results = list(bq_client.query(draws_query).result())
            draws_status = draws_results[0] if draws_results else None

            # 2. 监控预测数据状态
            predictions_query = f"""
            SELECT
              COUNT(*) as prediction_count,
              AVG(p_star_ens) as avg_p_star,
              MIN(p_star_ens) as min_p_star,
              MAX(p_star_ens) as max_p_star,
              MAX(timestamp) as latest_prediction
            FROM `{self.project_id}.{self.ds_draw}.p_ensemble_today_norm_v`
            WHERE DATE(timestamp, '{self.timezone}') = CURRENT_DATE('{self.timezone}')
            """

            pred_results = list(bq_client.query(predictions_query).result())
            pred_status = pred_results[0] if pred_results else None

            # 3. 监控候选信号状态
            candidates_query = f"""
            SELECT
              COUNT(*) as total_candidates,
              COUNT(CASE WHEN tier_candidate IS NOT NULL THEN 1 END) as valid_candidates,
              COUNT(CASE WHEN keyB = TRUE THEN 1 END) as b_key_passed,
              STRING_AGG(DISTINCT tier_candidate) as tier_levels
            FROM `{self.project_id}.{self.ds_draw}.candidates_today_dedup_v`
            WHERE day_id = CURRENT_DATE('{self.timezone}')
            """

            cand_results = list(bq_client.query(candidates_query).result())
            cand_status = cand_results[0] if cand_results else None

            # 生成监控报告
            monitor_report = {
                "monitor_time": datetime.now().isoformat(),
                "agent_id": self.agent_id,
                "supervisor": self.supervisor,
                "data_freshness": {
                    "today_draws": int(draws_status.today_draws) if draws_status else 0,
                    "latest_draw": (
                        draws_status.latest_draw.isoformat()
                        if draws_status and draws_status.latest_draw
                        else None
                    ),
                    "minutes_since_last": (
                        int(draws_status.minutes_since_last) if draws_status else None
                    ),
                    "freshness_status": (
                        "FRESH"
                        if draws_status and draws_status.minutes_since_last < 10
                        else "STALE"
                    ),
                },
                "prediction_status": {
                    "prediction_count": (
                        int(pred_status.prediction_count) if pred_status else 0
                    ),
                    "avg_p_star": (
                        float(pred_status.avg_p_star)
                        if pred_status and pred_status.avg_p_star
                        else 0
                    ),
                    "p_star_range": [
                        (
                            float(pred_status.min_p_star)
                            if pred_status and pred_status.min_p_star
                            else 0
                        ),
                        (
                            float(pred_status.max_p_star)
                            if pred_status and pred_status.max_p_star
                            else 0
                        ),
                    ],
                    "latest_prediction": (
                        pred_status.latest_prediction.isoformat()
                        if pred_status and pred_status.latest_prediction
                        else None
                    ),
                },
                "signal_status": {
                    "total_candidates": (
                        int(cand_status.total_candidates) if cand_status else 0
                    ),
                    "valid_candidates": (
                        int(cand_status.valid_candidates) if cand_status else 0
                    ),
                    "b_key_passed": int(cand_status.b_key_passed) if cand_status else 0,
                    "tier_levels": cand_status.tier_levels if cand_status else None,
                    "signal_generation_status": (
                        "WORKING"
                        if cand_status and cand_status.valid_candidates > 0
                        else "STOPPED"
                    ),
                },
            }

            return monitor_report

        except Exception as e:
            return {
                "monitor_time": datetime.now().isoformat(),
                "agent_id": self.agent_id,
                "error": str(e),
                "status": "MONITORING_FAILED",
            }

    def run_task(self):
        """执行监控任务"""
        print(f"🚀 Agent {self.agent_id} 开始执行真实监控任务")

        # 执行监控
        monitor_result = self.monitor_production_status()

        # 保存真实回执
        receipt_file = (
            f"monitor_receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(receipt_file, "w", encoding="utf-8") as f:
            json.dump(monitor_result, f, indent=2, ensure_ascii=False)

        # 显示监控结果
        if "error" not in monitor_result:
            data_fresh = monitor_result["data_freshness"]
            pred_status = monitor_result["prediction_status"]
            signal_status = monitor_result["signal_status"]

            print("\n📊 监控结果:")
            print(
                f"   📈 开奖数据: {data_fresh['today_draws']}期, 新鲜度: {data_fresh['freshness_status']}"
            )
            print(
                f"   🎯 预测数据: {pred_status['prediction_count']}条, 平均p_star: {pred_status['avg_p_star']:.3f}"
            )
            print(
                f"   🚨 信号状态: {signal_status['valid_candidates']}个有效信号, 状态: {signal_status['signal_generation_status']}"
            )

            print(f"\n📄 真实回执已保存: {receipt_file}")
            print("✅ 监控任务执行成功，数据真实可审计")

            return "COMPLETED"
        else:
            print(f"\n❌ 监控失败: {monitor_result['error']}")
            return "FAILED"


if __name__ == "__main__":
    agent = RealtimeMonitorAgent()
    result = agent.run_task()
    print(f"\n👑 向项目总指挥大人汇报: 监控任务{result}")
