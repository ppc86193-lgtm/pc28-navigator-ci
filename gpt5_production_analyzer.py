#!/usr/bin/env python3
"""
使用GPT-5深度分析PC28生产环境问题
立即行动，解决信号停摆问题
"""

import asyncio
import aiohttp
import json
import os
from datetime import datetime
from google.cloud import bigquery

class GPT5ProductionAnalyzer:
    """GPT-5生产环境分析器"""
    
    def __init__(self):
        self.api_key = os.getenv('AIML_API_KEY', '9030c9fcbc474c258dca7ff39b3a20e6')
        self.gpt5_model = "openai/gpt-5-2025-08-07"
        
        print("🧠 GPT-5生产环境深度分析器启动")
        print(f"🔑 使用API密钥: {self.api_key[:10]}...")
        print(f"🤖 分析模型: {self.gpt5_model}")
    
    async def collect_production_data(self):
        """收集生产环境真实数据"""
        print(f"\n📊 收集PC28生产环境真实数据...")
        
        try:
            bq_client = bigquery.Client(project="wprojectl", location="us-central1")
            
            # 收集关键数据
            data_queries = {
                "current_signals": """
                SELECT 
                  COUNT(*) as total_candidates,
                  COUNT(CASE WHEN tier_candidate IS NOT NULL THEN 1 END) as valid_signals,
                  COUNT(CASE WHEN keyB = TRUE THEN 1 END) as b_key_passed,
                  AVG(p_star_ens) as avg_p_star,
                  STRING_AGG(DISTINCT tier_candidate) as tier_levels
                FROM `wprojectl.pc28.candidates_today_dedup_v`
                WHERE day_id = CURRENT_DATE('Asia/Shanghai')
                """,
                
                "prediction_status": """
                SELECT 
                  COUNT(*) as prediction_count,
                  AVG(p_star_ens) as avg_ensemble_p_star,
                  MIN(p_star_ens) as min_p_star,
                  MAX(p_star_ens) as max_p_star,
                  MAX(timestamp) as latest_prediction,
                  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(timestamp), HOUR) as hours_since_last
                FROM `wprojectl.pc28.p_ensemble_today_norm_v`
                WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
                """,
                
                "historical_performance": """
                WITH recent_data AS (
                  SELECT 
                    d.issue,
                    (d.a + d.b + d.c) as actual_sum,
                    CASE WHEN (d.a + d.b + d.c) >= 14 THEN 'big' ELSE 'small' END as actual_size,
                    e.p_star_ens,
                    CASE WHEN e.p_star_ens >= 0.5 THEN 'big' ELSE 'small' END as predicted_size
                  FROM `wprojectl.pc28.draws_14w_dedup_v` d
                  LEFT JOIN `wprojectl.pc28.p_ensemble_today_norm_v` e ON d.issue = e.period
                  WHERE DATE(d.timestamp, 'Asia/Shanghai') >= DATE_SUB(CURRENT_DATE('Asia/Shanghai'), INTERVAL 3 DAY)
                    AND e.p_star_ens IS NOT NULL
                    AND d.a IS NOT NULL
                )
                SELECT 
                  COUNT(*) as total_samples,
                  AVG(p_star_ens) as avg_confidence,
                  COUNT(CASE WHEN predicted_size = actual_size THEN 1 END) as correct_predictions,
                  SAFE_DIVIDE(COUNT(CASE WHEN predicted_size = actual_size THEN 1 END), COUNT(*)) as accuracy_rate
                FROM recent_data
                """
            }
            
            production_data = {}
            
            for query_name, sql in data_queries.items():
                print(f"   📊 查询 {query_name}...")
                try:
                    results = list(bq_client.query(sql).result())
                    if results:
                        row = results[0]
                        production_data[query_name] = {k: v for k, v in row.items()}
                    else:
                        production_data[query_name] = {"error": "无数据"}
                except Exception as e:
                    production_data[query_name] = {"error": str(e)}
            
            print(f"   ✅ 生产数据收集完成")
            return production_data
            
        except Exception as e:
            print(f"   ❌ 数据收集失败: {e}")
            return {"error": str(e)}
    
    async def gpt5_deep_analysis(self, production_data):
        """GPT-5深度分析"""
        print(f"\n🧠 GPT-5深度分析PC28生产环境...")
        
        # 构建详细分析提示
        analysis_prompt = f"""作为PC28系统的首席AI分析师，请基于以下真实生产数据进行深度分析：

生产环境数据:
{json.dumps(production_data, ensure_ascii=False, indent=2)}

请提供：
1. 根本问题诊断 - 为什么信号生成停摆？
2. 数据质量评估 - 预测模型性能如何？
3. 系统健康分析 - 哪些环节有问题？
4. 具体修复方案 - 如何恢复正常运行？
5. 风险评估 - 有什么潜在风险？
6. 优化建议 - 如何提升系统性能？

要求：
- 基于真实数据分析，不做假设
- 提供可执行的具体建议
- 识别关键问题和解决优先级
- 评估修复的可行性和风险

请用专业的量化分析视角，结合PC28的业务特点，给出深度洞察。"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.gpt5_model,
            "messages": [
                {"role": "system", "content": "你是PC28系统的首席AI分析师，拥有深度分析和问题诊断的专业能力"},
                {"role": "user", "content": analysis_prompt}
            ],
            "max_tokens": 3000,
            "temperature": 0.1
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.aimlapi.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        tokens = data.get("usage", {}).get("total_tokens", 0)
                        
                        print(f"🧠 GPT-5深度分析完成")
                        print(f"📊 使用tokens: {tokens}")
                        print(f"💰 成本: 包月内无限制")
                        
                        return {
                            "success": True,
                            "analysis": content,
                            "tokens_used": tokens,
                            "model": self.gpt5_model,
                            "timestamp": datetime.now().isoformat()
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}",
                            "details": error_text
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def execute_analysis(self):
        """执行完整分析"""
        print("🎯 GPT-5深度分析PC28生产环境")
        print("=" * 50)
        print("🎯 目标: 立即诊断并解决生产问题")
        print()
        
        # 收集生产数据
        production_data = await self.collect_production_data()
        
        if "error" in production_data:
            print(f"❌ 数据收集失败: {production_data['error']}")
            return
        
        # GPT-5深度分析
        analysis_result = await self.gpt5_deep_analysis(production_data)
        
        if analysis_result["success"]:
            print(f"\n📋 GPT-5深度分析结果:")
            print("=" * 50)
            print(analysis_result["analysis"])
            
            # 保存分析报告
            report = {
                "analysis_timestamp": datetime.now().isoformat(),
                "production_data": production_data,
                "gpt5_analysis": analysis_result,
                "next_actions": "基于GPT-5分析制定具体行动计划"
            }
            
            report_file = f"gpt5_production_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"\n📄 完整分析报告已保存: {report_file}")
            print(f"🎯 下一步: 基于GPT-5分析执行具体修复行动")
            
        else:
            print(f"❌ GPT-5分析失败: {analysis_result['error']}")

async def main():
    """主分析函数"""
    analyzer = GPT5ProductionAnalyzer()
    await analyzer.execute_analysis()

if __name__ == "__main__":
    print("🧠 使用GPT-5深度分析PC28生产环境")
    print("🎯 立即行动，解决生产问题")
    print()
    
    asyncio.run(main())
