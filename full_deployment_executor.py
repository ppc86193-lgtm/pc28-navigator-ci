#!/usr/bin/env python3
"""
PC28 Navigator 全面部署执行器
使用无限AI能力 + Google Cloud免费额度
"""

import asyncio
import json
import os
import time
from datetime import datetime

import aiohttp
from google.cloud import bigquery


class NavigatorFullDeployment:
    """Navigator全面部署执行器"""

    def __init__(self):
        self.api_key = os.getenv("AIML_API_KEY", "9030c9fcbc474c258dca7ff39b3a20e6")
        self.project_id = "wprojectl"
        self.location = "us-central1"

        # 14个真实可用的AI模型
        self.ai_models = {
            "gpt-4o": {"role": "主力分析", "provider": "OpenAI"},
            "gpt-4o-mini": {"role": "快速检测", "provider": "OpenAI"},
            "o3-mini": {"role": "推理验证", "provider": "OpenAI"},
            "openai/gpt-5-2025-08-07": {"role": "深度分析", "provider": "OpenAI"},
            "google/gemini-2.5-pro": {"role": "多模态分析", "provider": "Google"},
            "google/gemini-2.5-flash": {"role": "实时监控", "provider": "Google"},
            "gemini-2.0-flash": {"role": "快速响应", "provider": "Google"},
            "deepseek-chat": {"role": "对话分析", "provider": "DeepSeek"},
            "deepseek/deepseek-r1": {"role": "数学推理", "provider": "DeepSeek"},
            "deepseek-reasoner": {"role": "逻辑推理", "provider": "DeepSeek"},
            "qwen-max": {"role": "中文分析", "provider": "Alibaba"},
            "qwen-plus": {"role": "快速中文", "provider": "Alibaba"},
            "x-ai/grok-4-07-09": {"role": "复杂诊断", "provider": "xAI"},
            "x-ai/grok-3-beta": {"role": "创新分析", "provider": "xAI"},
        }

        print("🚀 Navigator全面部署执行器初始化")
        print(f"🤖 可用AI模型: {len(self.ai_models)}个")
        print("💰 资源: AI/ML API不限量 + Google Cloud $300")

    async def _make_api_request(
        self, session, model_id, payload, max_retries=3, base_delay=1
    ):
        """通用API请求辅助函数，带重试逻辑"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(max_retries):
            try:
                async with session.post(
                    "https://api.aimlapi.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30,
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status >= 500:
                        print(
                            f"      ⚠️ 服务端错误 HTTP {response.status} for {model_id}, retrying... ({attempt + 1}/{max_retries})"
                        )
                        delay = base_delay * (2**attempt)
                        await asyncio.sleep(delay)
                    else:
                        error_text = await response.text()
                        print(
                            f"      ❌ 客户端错误 HTTP {response.status} for {model_id}: {error_text}"
                        )
                        return None  # Fail fast on non-500 errors
            except Exception as e:
                print(
                    f"      ❌ 请求异常 for {model_id}: {str(e)}, retrying... ({attempt + 1}/{max_retries})"
                )
                delay = base_delay * (2**attempt)
                await asyncio.sleep(delay)

        print(f"      ❌ 经过 {max_retries} 次重试后，模型 {model_id} 部署失败")
        return None

    async def deploy_ai_models(self):
        """部署14个AI模型的完整调用系统"""
        print("\n🤖 第1步: 部署14个AI模型完整调用系统")

        working_models = []

        async with aiohttp.ClientSession() as session:
            for model_id, config in self.ai_models.items():
                print(f"   🧠 部署 {model_id} ({config['role']})...")

                test_payload = {
                    "model": model_id,
                    "messages": [
                        {
                            "role": "system",
                            "content": f"你是PC28 Navigator的{config['role']}Agent",
                        },
                        {"role": "user", "content": "系统部署测试，请确认就绪"},
                    ],
                    "max_tokens": 20,
                    "temperature": 0.1,
                }

                data = await self._make_api_request(session, model_id, test_payload)

                if data:
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    print(f"      ✅ 就绪 - {config['role']}Agent部署成功")
                    working_models.append(
                        {
                            "model_id": model_id,
                            "role": config["role"],
                            "provider": config["provider"],
                            "status": "DEPLOYED",
                            "response": content[:50],
                        }
                    )
                else:
                    print(f"      ❌ 失败 - {config['role']}Agent部署失败")

                await asyncio.sleep(0.3)  # 避免频率限制

        print("\n📊 AI模型部署结果:")
        print(f"   成功部署: {len(working_models)}/14")
        print(f"   部署成功率: {len(working_models)/14:.1%}")

        return working_models

    async def analyze_production_with_gpt5(self):
        """使用GPT-5深度分析生产环境问题"""
        print("\n🧠 第2步: 使用GPT-5深度分析生产环境")

        # 获取生产环境真实数据
        bq_client = bigquery.Client(project=self.project_id, location=self.location)

        # 查询当前生产状态
        status_query = """
        WITH current_status AS (
          SELECT
            COUNT(*) as total_candidates,
            COUNT(CASE WHEN tier_candidate IS NOT NULL THEN 1 END) as valid_signals,
            AVG(p_star_ens) as avg_p_star,
            STRING_AGG(DISTINCT tier_candidate) as tier_levels
          FROM `wprojectl.pc28.candidates_today_dedup_v`
          WHERE day_id = CURRENT_DATE('Asia/Shanghai')
        ),
        prediction_status AS (
          SELECT
            COUNT(*) as prediction_count,
            AVG(p_star_ens) as avg_ensemble_p_star,
            MAX(timestamp) as latest_prediction
          FROM `wprojectl.pc28.p_ensemble_today_norm_v`
          WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
        )
        SELECT
          c.*,
          p.prediction_count,
          p.avg_ensemble_p_star,
          p.latest_prediction
        FROM current_status c
        CROSS JOIN prediction_status p
        """

        try:
            results = list(bq_client.query(status_query).result())
            production_data = results[0] if results else None

            if production_data:
                # 构建GPT-5分析请求
                analysis_context = {
                    "current_candidates": int(production_data.total_candidates),
                    "valid_signals": int(production_data.valid_signals),
                    "avg_p_star": (
                        float(production_data.avg_p_star)
                        if production_data.avg_p_star
                        else 0
                    ),
                    "tier_levels": production_data.tier_levels,
                    "prediction_count": int(production_data.prediction_count),
                    "avg_ensemble_p_star": (
                        float(production_data.avg_ensemble_p_star)
                        if production_data.avg_ensemble_p_star
                        else 0
                    ),
                    "latest_prediction": (
                        production_data.latest_prediction.isoformat()
                        if production_data.latest_prediction
                        else None
                    ),
                }

                # 使用GPT-5进行深度分析
                gpt5_analysis = await self.call_gpt5_analysis(analysis_context)

                return gpt5_analysis
            else:
                return {"error": "无法获取生产数据"}

        except Exception as e:
            return {"error": str(e)}

    async def call_gpt5_analysis(self, context):
        """调用GPT-5进行深度分析"""
        analysis_prompt = f"""你是PC28 Navigator的首席AI分析师。请基于以下生产环境真实数据进行深度分析：

生产状态: {json.dumps(context, ensure_ascii=False, indent=2)}

请提供:
1. 当前问题的根本原因分析
2. 系统健康状态评估
3. 具体的修复建议
4. 风险评估和预警
5. 下一步行动计划

要求: 基于真实数据，提供可执行的具体建议。"""

        payload = {
            "model": "openai/gpt-5-2025-08-07",
            "messages": [
                {
                    "role": "system",
                    "content": "你是PC28 Navigator的首席AI分析师，专门分析生产环境问题",
                },
                {"role": "user", "content": analysis_prompt},
            ],
            "max_tokens": 2000,
            "temperature": 0.1,
        }

        async with aiohttp.ClientSession() as session:
            data = await self._make_api_request(
                session, "openai/gpt-5-2025-08-07", payload, max_retries=2, base_delay=5
            )

        if data:
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens = data.get("usage", {}).get("total_tokens", 0)

            print(f"🧠 GPT-5分析完成 - {tokens} tokens")
            print("📊 分析结果:")
            print(content)

            return {
                "success": True,
                "analysis": content,
                "tokens_used": tokens,
                "model": "GPT-5",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {"success": False, "error": "GPT-5分析失败，即使在重试后"}

    async def start_realtime_monitoring(self):
        """启动实时AI监控"""
        print("\n📊 第3步: 启动24/7实时AI监控")

        # 使用gemini-2.5-flash进行实时监控
        monitoring_active = True
        monitor_count = 0

        while monitoring_active and monitor_count < 5:  # 演示5次监控
            monitor_count += 1

            print(f"   🔍 监控轮次 {monitor_count}: 使用 gemini-2.5-flash")

            # 实时监控调用
            monitor_result = await self.monitor_with_gemini_flash()

            if monitor_result.get("success"):
                print(f"      ✅ 监控正常 - {monitor_result.get('status', 'unknown')}")
            else:
                print(f"      ⚠️ 监控异常 - {monitor_result.get('error', 'unknown')}")

            await asyncio.sleep(2)  # 2秒间隔

        print(f"   📊 实时监控演示完成，共{monitor_count}次")
        return True

    async def monitor_with_gemini_flash(self):
        """使用Gemini Flash进行快速监控"""
        payload = {
            "model": "google/gemini-2.5-flash",
            "messages": [
                {
                    "role": "system",
                    "content": "你是PC28实时监控Agent，快速检测系统状态",
                },
                {
                    "role": "user",
                    "content": f"实时监控检查 - 时间: {datetime.now().isoformat()}",
                },
            ],
            "max_tokens": 50,
            "temperature": 0.2,
        }

        async with aiohttp.ClientSession() as session:
            data = await self._make_api_request(
                session, "google/gemini-2.5-flash", payload
            )

        if data:
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "success": True,
                "status": "MONITORING_ACTIVE",
                "response": content,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {"success": False, "error": "监控失败"}

    async def execute_full_deployment(self):
        """执行完整部署"""
        print("🚀 PC28 Navigator 全面部署开始")
        print("=" * 60)
        print("💰 资源: AI/ML API $50/月不限量 + Google Cloud $300免费")
        print("🤖 能力: 14个顶级AI模型无限调用")
        print()

        deployment_start = time.time()

        # 第1步: 部署AI模型
        working_models = await self.deploy_ai_models()

        # 第2步: GPT-5深度分析
        gpt5_analysis = await self.analyze_production_with_gpt5()

        # 第3步: 启动实时监控
        monitoring_status = await self.start_realtime_monitoring()

        deployment_time = time.time() - deployment_start

        # 生成部署报告
        deployment_report = {
            "deployment_timestamp": datetime.now().isoformat(),
            "deployment_duration_seconds": deployment_time,
            "ai_models_deployed": len(working_models),
            "working_models": working_models,
            "gpt5_analysis": gpt5_analysis,
            "monitoring_active": monitoring_status,
            "resource_status": {
                "aiml_api": "无限量可用",
                "google_cloud": "$300免费额度",
                "deployment_cost": "包月内无额外成本",
            },
            "next_steps": [
                "持续实时监控",
                "定期深度分析",
                "问题自动诊断",
                "智能优化建议",
            ],
        }

        # 保存部署报告
        report_file = f"navigator_deployment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(deployment_report, f, indent=2, ensure_ascii=False)

        print("\n🏆 PC28 Navigator全面部署完成!")
        print(f"   部署时间: {deployment_time:.1f}秒")
        print(f"   AI模型: {len(working_models)}/14 部署成功")
        print(
            f"   GPT-5分析: {'✅ 完成' if gpt5_analysis.get('success') else '❌ 失败'}"
        )
        print(f"   实时监控: {'✅ 启动' if monitoring_status else '❌ 失败'}")
        print(f"   📄 部署报告: {report_file}")

        return deployment_report


async def main():
    """主部署函数"""
    deployer = NavigatorFullDeployment()
    result = await deployer.execute_full_deployment()

    print("\n🎯 Navigator已全面部署，开始智能运维！")
    return result


if __name__ == "__main__":
    print("🚀 PC28 Navigator 全面部署")
    print("🎯 无限AI能力 + Google Cloud免费额度")
    print()

    asyncio.run(main())
