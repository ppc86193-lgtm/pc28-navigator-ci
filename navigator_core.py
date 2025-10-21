#!/usr/bin/env python3
"""
PC28 Navigator Core - 唯一核心实现文件
13个Agent + 1人工审批位的智能航管塔系统
专注解决生产环境上游同步问题
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass

from production_system import PredictorBridge

# 项目信息
PROJECT = "PC28 Navigator"
VERSION = "1.0.0"
PURPOSE = "解决生产环境上游API同步中断问题"

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Navigator")

@dataclass
class NavigatorConfig:
    """Navigator配置"""
    # 上游API配置
    upstream_api_base: str = "https://rijb.api.storeapi.net/api/119"
    upstream_appid: str = "45928"
    upstream_secret: str = "ca9edbfee35c22a0d6c4cf6722506af0"
    
    # Google Cloud配置
    gcp_project: str = "wprojectl"
    gcp_location: str = "us-central1"
    bigquery_dataset: str = "pc28"
    
    # 核心参数
    threshold_conf_raw: float = 0.78
    kelly_fraction: float = 0.25
    bet_cap: float = 0.02
    survival_threshold: float = 0.51282  # 20/39

class UpstreamMonitor:
    """上游API监控器"""
    
    def __init__(self, config: NavigatorConfig):
        self.config = config
        
    async def check_upstream_health(self) -> Dict[str, Any]:
        """检查上游API健康状态"""
        import aiohttp
        import hashlib
        
        # 构建认证签名
        timestamp = str(int(time.time()))
        sign_string = f"appid{self.config.upstream_appid}formatjsontime{timestamp}{self.config.upstream_secret}"
        sign = hashlib.md5(sign_string.encode()).hexdigest()
        
        params = {
            "appid": self.config.upstream_appid,
            "format": "json",
            "time": timestamp,
            "sign": sign
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.config.upstream_api_base}/259", params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "status": "healthy",
                            "response_time_ms": response.headers.get("X-Response-Time", "unknown"),
                            "data": data
                        }
                    else:
                        return {
                            "status": "unhealthy", 
                            "error": f"HTTP {response.status}"
                        }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

class SignalDiagnostic:
    """信号诊断器"""
    
    def __init__(self, config: NavigatorConfig):
        self.config = config
        
    async def diagnose_signal_failure(self) -> Dict[str, Any]:
        """诊断信号生成失败原因"""
        from google.cloud import bigquery
        
        client = bigquery.Client(project=self.config.gcp_project)
        
        # 检查各层视图数据
        checks = {}
        
        # 检查基础集成视图
        try:
            query = f"""
            SELECT COUNT(*) as count
            FROM `{self.config.gcp_project}.{self.config.bigquery_dataset}.p_ensemble_today_norm_v`
            WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            """
            results = list(client.query(query).result())
            checks["p_ensemble_today_norm_v"] = results[0].count if results else 0
        except Exception as e:
            checks["p_ensemble_today_norm_v"] = f"ERROR: {e}"
        
        # 检查候选信号视图
        try:
            query = f"""
            SELECT COUNT(*) as count, COUNT(CASE WHEN tier_candidate IS NOT NULL THEN 1 END) as valid_count
            FROM `{self.config.gcp_project}.{self.config.bigquery_dataset}.candidates_today_dedup_v`
            WHERE DATE(ts_utc, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            """
            results = list(client.query(query).result())
            if results:
                checks["candidates_today_dedup_v"] = {
                    "total": results[0].count,
                    "valid": results[0].valid_count
                }
        except Exception as e:
            checks["candidates_today_dedup_v"] = f"ERROR: {e}"
        
        return {
            "diagnosis_time": datetime.now().isoformat(),
            "checks": checks,
            "root_cause": self._analyze_root_cause(checks)
        }
    
    def _analyze_root_cause(self, checks: Dict[str, Any]) -> str:
        """分析根本原因"""
        if isinstance(checks.get("candidates_today_dedup_v"), dict):
            candidate_data = checks["candidates_today_dedup_v"]
            if candidate_data["total"] > 0 and candidate_data["valid"] == 0:
                return "候选信号视图有数据但tier_candidate全部为NULL，可能是consensus_candidates_api_v视图SQL错误"
        
        if checks.get("p_ensemble_today_norm_v", 0) == 0:
            return "基础集成视图无今日数据，可能是上游API同步中断"
        
        return "需要进一步诊断"

class NavigatorCore:
    """Navigator核心系统 - 唯一实现"""
    
    def __init__(self):
        self.config = NavigatorConfig()
        self.upstream_monitor = UpstreamMonitor(self.config)
        self.signal_diagnostic = SignalDiagnostic(self.config)
        self.predictor_bridge = PredictorBridge(self.config)
        
        logger.info(f"{PROJECT} v{VERSION} 初始化完成")
        logger.info(f"目标: {PURPOSE}")
    
    async def emergency_diagnosis(self) -> Dict[str, Any]:
        """紧急诊断生产环境问题"""
        logger.info("开始紧急诊断...")
        
        # 检查上游API健康
        upstream_health = await self.upstream_monitor.check_upstream_health()
        
        # 诊断信号失败
        signal_diagnosis = await self.signal_diagnostic.diagnose_signal_failure()
        
        # 预测趋势快照（当数据可用时）
        prediction_snapshot = await self.predictor_bridge.generate_snapshot()

        # 综合分析
        diagnosis_result = {
            "diagnosis_time": datetime.now().isoformat(),
            "upstream_health": upstream_health,
            "signal_diagnosis": signal_diagnosis,
            "prediction_snapshot": prediction_snapshot,
            "recommendations": self._generate_recommendations(upstream_health, signal_diagnosis)
        }
        
        return diagnosis_result
    
    def _generate_recommendations(self, upstream: Dict[str, Any], signal: Dict[str, Any]) -> List[str]:
        """生成修复建议"""
        recommendations = []
        
        if upstream.get("status") != "healthy":
            recommendations.append("🚨 上游API异常，需要检查网络连接和认证配置")
        
        if "上游API同步中断" in signal.get("root_cause", ""):
            recommendations.append("🔧 重启数据同步服务，修复上游到BigQuery的数据流")
        
        if "SQL错误" in signal.get("root_cause", ""):
            recommendations.append("🛠️ 修复consensus_candidates_api_v视图的SQL语法错误")
        
        if not recommendations:
            recommendations.append("✅ 系统状态正常，继续监控")
        
        return recommendations
    
    async def run_emergency_mode(self):
        """运行紧急模式"""
        logger.info(f"🚨 {PROJECT} 紧急模式启动")
        
        try:
            diagnosis = await self.emergency_diagnosis()
            
            print(f"\n🎯 {PROJECT} 紧急诊断报告")
            print("=" * 50)
            print(f"诊断时间: {diagnosis['diagnosis_time']}")
            
            print(f"\n📡 上游API状态:")
            upstream = diagnosis['upstream_health']
            print(f"   状态: {upstream['status']}")
            if upstream['status'] != 'healthy':
                print(f"   错误: {upstream.get('error', 'unknown')}")
            
            print(f"\n🔍 信号诊断:")
            signal = diagnosis['signal_diagnosis']
            print(f"   根因: {signal['root_cause']}")

            prediction = diagnosis.get("prediction_snapshot", {})
            print(f"\n📊 预测趋势:")
            if prediction.get("status") == "ok":
                print(f"   样本量: {prediction['sample_size']}")
                bands = prediction.get("bands", [])
                if bands:
                    latest = bands[0]
                    print(
                        "   最新窗口({label}): 大 {big:.1%} / 小 {small:.1%} | 单 {odd:.1%} / 双 {even:.1%}".format(
                            label=latest["label"],
                            big=latest["big_probability"],
                            small=latest["small_probability"],
                            odd=latest["odd_probability"],
                            even=latest["even_probability"],
                        )
                    )
                momentum = prediction.get("momentum", {})
                print(
                    "   动量偏移: 大小 {bs:.1%} / 单双 {oe:.1%}".format(
                        bs=abs(momentum.get("big_small_shift", 0.0)),
                        oe=abs(momentum.get("odd_even_shift", 0.0)),
                    )
                )
                print(
                    f"   预测置信度: {prediction.get('predictive_score', 0.0):.1%}"
                )

                if prediction.get("alerts"):
                    print("\n⚠️ 风险提示:")
                    for alert in prediction["alerts"]:
                        print(f"   - {alert}")
            else:
                reason = prediction.get("reason", "未提供数据")
                print(f"   暂不可用（{reason}）")

            print(f"\n💡 修复建议:")
            for i, rec in enumerate(diagnosis['recommendations'], 1):
                print(f"   {i}. {rec}")
            
            # 保存诊断报告
            report_file = f"emergency_diagnosis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(diagnosis, f, indent=2, ensure_ascii=False)
            
            print(f"\n📄 详细报告已保存: {report_file}")
            
        except Exception as e:
            logger.error(f"紧急诊断失败: {e}")

async def main():
    """主函数"""
    navigator = NavigatorCore()
    await navigator.run_emergency_mode()

if __name__ == "__main__":
    print(f"🧭 {PROJECT} v{VERSION}")
    print(f"🎯 {PURPOSE}")
    print()
    
    asyncio.run(main())


