#!/usr/bin/env python3
"""
PC28 Navigator 整合系统
本地代码逻辑 + 生产环境数据 = 统一系统
解决生产问题，验证准确率和覆盖率
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List

import aiohttp
from google.cloud import bigquery

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("PC28Navigator")


class PC28IntegratedSystem:
    """PC28整合系统 - 本地逻辑+生产数据"""

    def __init__(self):
        # 生产环境配置
        self.project_id = "wprojectl"
        self.dataset = "pc28"
        self.location = "us-central1"

        # 上游API配置
        self.upstream_base = "https://rijb.api.storeapi.net/api/119"
        self.upstream_appid = "45928"
        self.upstream_secret = "ca9edbfee35c22a0d6c4cf6722506af0"

        # 核心参数 (从本地代码继承)
        self.threshold_conf_raw = 0.78
        self.kelly_fraction = 0.25
        self.bet_cap = 0.02
        self.survival_threshold = 20 / 39  # 51.282%

        # 初始化BigQuery客户端
        self.bq_client = bigquery.Client(
            project=self.project_id, location=self.location
        )

        logger.info("PC28整合系统初始化完成")

    async def check_upstream_api(self) -> Dict[str, Any]:
        """检查上游API状态"""
        timestamp = str(int(time.time()))
        sign_string = (
            f"appid{self.upstream_appid}formatjsontime{timestamp}{self.upstream_secret}"
        )
        sign = hashlib.md5(sign_string.encode()).hexdigest()

        params = {
            "appid": self.upstream_appid,
            "format": "json",
            "time": timestamp,
            "sign": sign,
        }

        try:
            async with aiohttp.ClientSession() as session:
                start_time = time.time()
                async with session.get(
                    f"{self.upstream_base}/259", params=params, timeout=10
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000

                    if response.status == 200:
                        data = await response.json()
                        return {
                            "status": "healthy",
                            "latency_ms": latency_ms,
                            "response": data,
                            "current_issue": data.get("long_issue"),
                            "next_issue": data.get("next_issue"),
                            "award_time": data.get("award_time"),
                        }
                    else:
                        return {
                            "status": "error",
                            "error": f"HTTP {response.status}",
                            "latency_ms": latency_ms,
                        }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def analyze_historical_performance(self, days: int = 7) -> Dict[str, Any]:
        """分析历史性能"""
        logger.info(f"分析最近{days}天的历史性能...")

        # 查询历史数据和预测结果
        query = f"""
        WITH historical_data AS (
          SELECT
            d.issue,
            d.timestamp,
            (d.a + d.b + d.c) as actual_sum,
            CASE WHEN (d.a + d.b + d.c) >= 14 THEN 'big' ELSE 'small' END as actual_size,
            CASE WHEN MOD(d.a + d.b + d.c, 2) = 0 THEN 'even' ELSE 'odd' END as actual_oe,
            e.p_star_ens,
            e.vote_ratio,
            e.n_votes
          FROM `{self.project_id}.{self.dataset}.draws_14w_dedup_v` d
          LEFT JOIN `{self.project_id}.{self.dataset}.p_ensemble_today_norm_v` e
            ON d.issue = e.period
          WHERE DATE(d.timestamp, 'Asia/Shanghai') >= DATE_SUB(CURRENT_DATE('Asia/Shanghai'), INTERVAL {days} DAY)
            AND e.p_star_ens IS NOT NULL
          ORDER BY d.timestamp DESC
        ),
        performance_analysis AS (
          SELECT
            COUNT(*) as total_periods,
            AVG(p_star_ens) as avg_p_star,
            COUNT(CASE WHEN p_star_ens >= {self.threshold_conf_raw} THEN 1 END) as high_confidence_count,
            AVG(vote_ratio) as avg_vote_ratio,
            AVG(n_votes) as avg_n_votes,
            -- 计算如果降低阈值的覆盖率
            COUNT(CASE WHEN p_star_ens >= 0.6 THEN 1 END) as coverage_at_60,
            COUNT(CASE WHEN p_star_ens >= 0.5 THEN 1 END) as coverage_at_50,
            COUNT(CASE WHEN p_star_ens >= 0.4 THEN 1 END) as coverage_at_40
          FROM historical_data
        )
        SELECT
          *,
          SAFE_DIVIDE(high_confidence_count, total_periods) as coverage_rate_78,
          SAFE_DIVIDE(coverage_at_60, total_periods) as coverage_rate_60,
          SAFE_DIVIDE(coverage_at_50, total_periods) as coverage_rate_50,
          SAFE_DIVIDE(coverage_at_40, total_periods) as coverage_rate_40
        FROM performance_analysis
        """

        try:
            results = list(self.bq_client.query(query).result())
            if results:
                row = results[0]
                return {
                    "analysis_period": f"最近{days}天",
                    "total_periods": row.total_periods,
                    "avg_p_star": float(row.avg_p_star),
                    "avg_vote_ratio": (
                        float(row.avg_vote_ratio) if row.avg_vote_ratio else 0
                    ),
                    "avg_n_votes": float(row.avg_n_votes) if row.avg_n_votes else 0,
                    "coverage_analysis": {
                        "at_78_threshold": float(row.coverage_rate_78 or 0),
                        "at_60_threshold": float(row.coverage_rate_60 or 0),
                        "at_50_threshold": float(row.coverage_rate_50 or 0),
                        "at_40_threshold": float(row.coverage_rate_40 or 0),
                    },
                    "threshold_recommendation": self._recommend_threshold(row),
                }
        except Exception as e:
            logger.error(f"历史性能分析失败: {e}")
            return {"error": str(e)}

    def _recommend_threshold(self, data) -> Dict[str, Any]:
        """基于历史数据推荐阈值"""
        avg_p_star = float(data.avg_p_star)

        # 基于生存线理论推荐
        if avg_p_star >= self.survival_threshold:
            # 如果平均p_star高于生存线，可以适当降低阈值提高覆盖率
            recommended_threshold = max(
                self.survival_threshold + 0.05, avg_p_star - 0.1
            )
            reasoning = (
                f"平均p_star({avg_p_star:.3f})高于生存线，建议降低阈值提高覆盖率"
            )
        else:
            # 如果平均p_star低于生存线，需要提高模型质量
            recommended_threshold = self.threshold_conf_raw
            reasoning = (
                f"平均p_star({avg_p_star:.3f})低于生存线，需要优化模型而非降低阈值"
            )

        return {
            "current_threshold": self.threshold_conf_raw,
            "recommended_threshold": round(recommended_threshold, 3),
            "reasoning": reasoning,
            "risk_assessment": (
                "低风险"
                if recommended_threshold >= self.survival_threshold
                else "高风险"
            ),
        }

    def analyze_signal_chain_breakdown(self) -> Dict[str, Any]:
        """分析信号链路故障点"""
        logger.info("分析信号处理链路故障点...")

        chain_checks = {}

        # 检查各个环节
        tables_to_check = [
            "p_ensemble_today_norm_v",
            "ensemble_today_enhanced",
            "ensemble_today_guarded",
            "candidates_today_dedup_v",
        ]

        for table in tables_to_check:
            try:
                query = f"""
                SELECT
                  COUNT(*) as total_count,
                  COUNT(CASE WHEN period IS NOT NULL THEN 1 END) as valid_periods,
                  MAX(timestamp) as latest_timestamp
                FROM `{self.project_id}.{self.dataset}.{table}`
                WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
                """

                results = list(self.bq_client.query(query).result())
                if results:
                    row = results[0]
                    chain_checks[table] = {
                        "total_count": row.total_count,
                        "valid_periods": row.valid_periods,
                        "latest_timestamp": (
                            row.latest_timestamp.isoformat()
                            if row.latest_timestamp
                            else None
                        ),
                        "status": "OK" if row.total_count > 0 else "EMPTY",
                    }
                else:
                    chain_checks[table] = {"status": "NO_DATA"}

            except Exception as e:
                chain_checks[table] = {"status": "ERROR", "error": str(e)}

        # 分析故障点
        breakdown_analysis = self._analyze_breakdown_point(chain_checks)

        return {
            "chain_checks": chain_checks,
            "breakdown_analysis": breakdown_analysis,
            "repair_recommendations": self._generate_repair_plan(breakdown_analysis),
        }

    def _analyze_breakdown_point(self, checks: Dict[str, Any]) -> Dict[str, Any]:
        """分析故障点"""
        working_stages = []
        failed_stages = []

        for table, result in checks.items():
            if result.get("status") == "OK":
                working_stages.append(table)
            else:
                failed_stages.append(table)

        if "candidates_today_dedup_v" in failed_stages:
            breakdown_point = "最终候选信号生成失败"
        elif "ensemble_today_guarded" in failed_stages:
            breakdown_point = "守护机制处理失败"
        elif "ensemble_today_enhanced" in failed_stages:
            breakdown_point = "增强处理失败"
        elif "p_ensemble_today_norm_v" in failed_stages:
            breakdown_point = "基础集成失败"
        else:
            breakdown_point = "信号链路正常，问题在阈值设置"

        return {
            "working_stages": working_stages,
            "failed_stages": failed_stages,
            "breakdown_point": breakdown_point,
            "severity": (
                "CRITICAL"
                if len(failed_stages) > 2
                else "HIGH" if failed_stages else "MEDIUM"
            ),
        }

    def _generate_repair_plan(self, breakdown: Dict[str, Any]) -> List[str]:
        """生成修复计划"""
        recommendations = []

        if "candidates_today_dedup_v" in breakdown["failed_stages"]:
            recommendations.append("🔧 修复candidates_today_dedup_v视图SQL语法")
            recommendations.append("🔍 检查consensus_candidates_api_v视图定义")

        if breakdown["breakdown_point"] == "信号链路正常，问题在阈值设置":
            recommendations.append("📊 基于历史数据调整threshold_conf_raw阈值")
            recommendations.append("🎯 实施分层阈值策略 (CL3/CL2/CL1)")

        if breakdown["severity"] == "CRITICAL":
            recommendations.append("🚨 启动紧急修复模式")
            recommendations.append("📞 立即通知运维团队")

        return recommendations

    async def run_integrated_diagnosis(self):
        """运行整合诊断"""
        print("🧭 PC28 Navigator 整合系统启动")
        print("=" * 50)
        print("本地代码逻辑 + 生产环境数据 = 统一诊断")
        print()

        # 1. 检查上游API
        print("📡 第1步: 检查上游API状态...")
        upstream_result = await self.check_upstream_api()

        print(f"   上游API状态: {upstream_result['status']}")
        if upstream_result["status"] == "healthy":
            print(f"   当前期号: {upstream_result.get('current_issue', 'unknown')}")
            print(f"   下期期号: {upstream_result.get('next_issue', 'unknown')}")
            print(f"   响应延迟: {upstream_result.get('latency_ms', 0):.1f}ms")
        else:
            print(f"   错误信息: {upstream_result.get('error', 'unknown')}")

        # 2. 分析历史性能
        print("\n📊 第2步: 分析历史性能...")
        performance = self.analyze_historical_performance(days=7)

        if "error" not in performance:
            print(f"   分析周期: {performance['analysis_period']}")
            print(f"   总期数: {performance['total_periods']}")
            print(f"   平均p_star: {performance['avg_p_star']:.3f}")
            print(f"   平均投票数: {performance['avg_n_votes']:.1f}")

            print("\n   📈 不同阈值下的覆盖率:")
            coverage = performance["coverage_analysis"]
            print(f"   0.78阈值: {coverage['at_78_threshold']:.1%}")
            print(f"   0.60阈值: {coverage['at_60_threshold']:.1%}")
            print(f"   0.50阈值: {coverage['at_50_threshold']:.1%}")
            print(f"   0.40阈值: {coverage['at_40_threshold']:.1%}")

            # 阈值推荐
            threshold_rec = performance["threshold_recommendation"]
            print("\n   💡 阈值建议:")
            print(f"   当前阈值: {threshold_rec['current_threshold']}")
            print(f"   建议阈值: {threshold_rec['recommended_threshold']}")
            print(f"   推荐理由: {threshold_rec['reasoning']}")
            print(f"   风险评估: {threshold_rec['risk_assessment']}")
        else:
            print(f"   ❌ 分析失败: {performance['error']}")

        # 3. 诊断信号链路
        print("\n🔍 第3步: 诊断信号处理链路...")
        chain_analysis = self.analyze_signal_chain_breakdown()

        print(
            f"   工作正常: {len(chain_analysis['breakdown_analysis']['working_stages'])}个环节"
        )
        print(
            f"   故障环节: {len(chain_analysis['breakdown_analysis']['failed_stages'])}个"
        )
        print(f"   故障点: {chain_analysis['breakdown_analysis']['breakdown_point']}")
        print(f"   严重程度: {chain_analysis['breakdown_analysis']['severity']}")

        print("\n   🔧 修复建议:")
        for i, rec in enumerate(chain_analysis["repair_recommendations"], 1):
            print(f"   {i}. {rec}")

        # 4. 生成整合报告
        integrated_report = {
            "diagnosis_time": datetime.now().isoformat(),
            "upstream_api": upstream_result,
            "historical_performance": performance,
            "signal_chain": chain_analysis,
            "integration_summary": self._generate_integration_summary(
                upstream_result, performance, chain_analysis
            ),
        }

        # 保存报告
        report_file = (
            f"integrated_diagnosis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(integrated_report, f, indent=2, ensure_ascii=False)

        print(f"\n📄 完整诊断报告已保存: {report_file}")

        return integrated_report

    def _generate_integration_summary(
        self, upstream: Dict, performance: Dict, chain: Dict
    ) -> Dict[str, Any]:
        """生成整合总结"""
        summary = {
            "overall_health": "HEALTHY",
            "critical_issues": [],
            "immediate_actions": [],
            "long_term_optimizations": [],
        }

        # 检查上游API
        if upstream.get("status") != "healthy":
            summary["overall_health"] = "CRITICAL"
            summary["critical_issues"].append("上游API异常")
            summary["immediate_actions"].append("修复上游API连接")

        # 检查性能
        if "error" not in performance:
            avg_p_star = performance.get("avg_p_star", 0)
            if avg_p_star < self.survival_threshold:
                summary["overall_health"] = "CRITICAL"
                summary["critical_issues"].append(
                    f"平均p_star({avg_p_star:.3f})低于生存线"
                )
                summary["immediate_actions"].append("优化模型或调整策略")

            coverage_78 = performance.get("coverage_analysis", {}).get(
                "at_78_threshold", 0
            )
            if coverage_78 == 0:
                summary["critical_issues"].append("当前阈值下覆盖率为0")
                summary["immediate_actions"].append("调整阈值或优化模型")

        # 检查信号链路
        if chain["breakdown_analysis"]["severity"] in ["CRITICAL", "HIGH"]:
            summary["overall_health"] = "CRITICAL"
            summary["critical_issues"].append(
                chain["breakdown_analysis"]["breakdown_point"]
            )
            summary["immediate_actions"].extend(chain["repair_recommendations"])

        return summary


async def main():
    """主函数"""
    system = PC28IntegratedSystem()

    print("🎯 PC28 Navigator 整合系统")
    print("📊 本地逻辑 + 生产数据 = 完整诊断")
    print()

    # 运行整合诊断
    result = await system.run_integrated_diagnosis()

    # 显示总结
    summary = result["integration_summary"]
    print("\n🏆 整合诊断总结:")
    print(f"   整体健康度: {summary['overall_health']}")

    if summary["critical_issues"]:
        print("   🚨 关键问题:")
        for issue in summary["critical_issues"]:
            print(f"      • {issue}")

    if summary["immediate_actions"]:
        print("   🔧 立即行动:")
        for action in summary["immediate_actions"]:
            print(f"      • {action}")

    print("\n✅ 整合诊断完成！")


if __name__ == "__main__":
    asyncio.run(main())
