#!/usr/bin/env python3
"""
AI/ML API完整实现
6个顶级模型的完整调用接口
"""

import asyncio
import aiohttp
import json
import os
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AIML_API")

@dataclass
class ModelConfig:
    """模型配置"""
    model_id: str
    provider: str
    cost_per_1k_tokens: float
    max_tokens: int
    temperature: float
    timeout_seconds: int

class AIMLAPIClient:
    """AI/ML API完整客户端"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('AIML_API_KEY')
        self.base_url = "https://api.aimlapi.com/v1"
        
        if not self.api_key:
            raise ValueError("❌ 请设置AIML_API_KEY环境变量")
        
        # 6个顶级模型配置
        self.models = {
            "gpt-5": ModelConfig(
                model_id="gpt-5",
                provider="OpenAI",
                cost_per_1k_tokens=0.06,
                max_tokens=4000,
                temperature=0.1,
                timeout_seconds=60
            ),
            "claude-4.1-opus": ModelConfig(
                model_id="claude-4.1-opus", 
                provider="Anthropic",
                cost_per_1k_tokens=0.075,
                max_tokens=4000,
                temperature=0.1,
                timeout_seconds=60
            ),
            "gemini-2.5-pro": ModelConfig(
                model_id="gemini-2.5-pro",
                provider="Google", 
                cost_per_1k_tokens=0.035,
                max_tokens=3000,
                temperature=0.2,
                timeout_seconds=45
            ),
            "deepseek-r1": ModelConfig(
                model_id="deepseek-r1",
                provider="DeepSeek",
                cost_per_1k_tokens=0.014,
                max_tokens=4000,
                temperature=0.1,
                timeout_seconds=90
            ),
            "qwen3-235b-a22b": ModelConfig(
                model_id="qwen3-235b-a22b",
                provider="Alibaba",
                cost_per_1k_tokens=0.02,
                max_tokens=8000,
                temperature=0.2,
                timeout_seconds=120
            ),
            "gemini-2.5-flash": ModelConfig(
                model_id="gemini-2.5-flash",
                provider="Google",
                cost_per_1k_tokens=0.015,
                max_tokens=2000,
                temperature=0.3,
                timeout_seconds=30
            )
        }
        
        logger.info(f"AI/ML API客户端初始化完成，API密钥: {self.api_key[:10]}...")
    
    async def call_model(self, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """调用指定模型"""
        if model_id not in self.models:
            raise ValueError(f"未知模型: {model_id}")
        
        model_config = self.models[model_id]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": kwargs.get("temperature", model_config.temperature),
            "max_tokens": kwargs.get("max_tokens", model_config.max_tokens)
        }
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=model_config.timeout_seconds)
                ) as response:
                    
                    latency_ms = (time.time() - start_time) * 1000
                    
                    if response.status == 200:
                        response_data = await response.json()
                        
                        # 提取响应内容
                        content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        tokens_used = response_data.get("usage", {}).get("total_tokens", 0)
                        cost = (tokens_used / 1000) * model_config.cost_per_1k_tokens
                        
                        return {
                            "success": True,
                            "model_id": model_id,
                            "provider": model_config.provider,
                            "content": content,
                            "tokens_used": tokens_used,
                            "cost": cost,
                            "latency_ms": latency_ms,
                            "timestamp": time.time()
                        }
                    else:
                        error_data = await response.text()
                        return {
                            "success": False,
                            "model_id": model_id,
                            "error": f"HTTP {response.status}: {error_data}",
                            "latency_ms": latency_ms
                        }
                        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "model_id": model_id,
                "error": str(e),
                "latency_ms": latency_ms
            }
    
    async def test_all_models(self) -> Dict[str, Any]:
        """测试所有6个模型的连接"""
        print("🧪 测试AI/ML API所有模型连接...")
        
        test_messages = [
            {"role": "system", "content": "你是PC28分析专家"},
            {"role": "user", "content": "简单测试：分析数字序列[15,8,12]，只需一句话"}
        ]
        
        results = {}
        total_cost = 0.0
        
        for model_id in self.models.keys():
            print(f"   🧠 测试 {model_id}...")
            
            result = await self.call_model(model_id, test_messages, max_tokens=50)
            results[model_id] = result
            
            if result["success"]:
                print(f"      ✅ 成功 - {result['latency_ms']:.0f}ms, ${result['cost']:.4f}")
                print(f"      💬 响应: {result['content'][:60]}...")
                total_cost += result["cost"]
            else:
                print(f"      ❌ 失败 - {result['error']}")
        
        successful_models = sum(1 for r in results.values() if r["success"])
        
        summary = {
            "test_time": time.time(),
            "total_models": len(self.models),
            "successful_models": successful_models,
            "success_rate": successful_models / len(self.models),
            "total_cost": total_cost,
            "model_results": results
        }
        
        print(f"\n📊 测试总结:")
        print(f"   成功模型: {successful_models}/{len(self.models)}")
        print(f"   成功率: {summary['success_rate']:.1%}")
        print(f"   总成本: ${total_cost:.4f}")
        
        return summary
    
    async def explain_pc28_issue(self, issue_description: str, data_context: Dict[str, Any]) -> Dict[str, Any]:
        """使用AI模型解释PC28问题"""
        print(f"🧠 使用AI模型分析PC28问题...")
        
        # 构建分析提示
        context_str = json.dumps(data_context, ensure_ascii=False, indent=2)
        
        messages = [
            {
                "role": "system",
                "content": """你是PC28系统专家。请基于提供的真实数据分析问题：

核心约束:
- 只基于BigQuery真实数据分析
- 不产生交易信号，只做解释
- 生存线胜率: 51.28% (基于1.95赔率)
- 目标: 覆盖率50%, 准确率80%

输出JSON格式，包含:
- problem_analysis: 问题分析
- root_cause: 根本原因
- recommendations: 具体建议
- risk_assessment: 风险评估
"""
            },
            {
                "role": "user", 
                "content": f"问题描述: {issue_description}\n\n数据上下文: {context_str}"
            }
        ]
        
        # 使用gpt-5进行深度分析
        result = await self.call_model("gpt-5", messages)
        
        if result["success"]:
            try:
                # 尝试解析JSON响应
                content = result["content"]
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    analysis = json.loads(content[json_start:json_end])
                    return {
                        "success": True,
                        "analysis": analysis,
                        "model_used": "gpt-5",
                        "cost": result["cost"],
                        "timestamp": result["timestamp"]
                    }
                else:
                    return {
                        "success": True,
                        "analysis": {"raw_response": content},
                        "model_used": "gpt-5",
                        "cost": result["cost"]
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"解析响应失败: {e}",
                    "raw_response": result["content"]
                }
        else:
            return {
                "success": False,
                "error": result["error"]
            }

# 使用示例和测试
async def main():
    """主函数 - 测试AI/ML API完整实现"""
    print("🔑 AI/ML API完整实现测试")
    print("=" * 50)
    
    # 检查API密钥
    api_key = os.getenv('AIML_API_KEY')
    if not api_key:
        print("❌ 请设置AIML_API_KEY环境变量")
        print("   export AIML_API_KEY=your_actual_api_key")
        return
    
    try:
        # 初始化客户端
        client = AIMLAPIClient(api_key)
        
        # 测试所有模型
        test_results = await client.test_all_models()
        
        # 如果测试成功，进行PC28问题分析
        if test_results["success_rate"] > 0:
            print(f"\n🧠 使用AI模型分析PC28生产问题...")
            
            issue_context = {
                "problem": "生产环境信号生成停摆",
                "symptoms": [
                    "candidates_today_dedup_v全部字段NULL",
                    "覆盖率0%，无任何信号",
                    "Vertex AI预测数据停滞9小时"
                ],
                "recent_data": {
                    "avg_p_star": 0.495,
                    "survival_threshold": 0.51282,
                    "current_threshold": 0.78,
                    "model_accuracy": "51.49%"
                }
            }
            
            analysis_result = await client.explain_pc28_issue(
                "PC28生产环境信号生成停摆分析",
                issue_context
            )
            
            if analysis_result["success"]:
                print(f"✅ AI分析完成，成本: ${analysis_result['cost']:.4f}")
                print(f"🧠 使用模型: {analysis_result['model_used']}")
                
                # 保存分析结果
                with open("ai_analysis_result.json", "w", encoding="utf-8") as f:
                    json.dump(analysis_result, f, indent=2, ensure_ascii=False)
                
                print(f"📄 分析结果已保存: ai_analysis_result.json")
            else:
                print(f"❌ AI分析失败: {analysis_result['error']}")
        
        # 保存测试结果
        with open("aiml_api_test_results.json", "w", encoding="utf-8") as f:
            json.dump(test_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 完整测试结果已保存: aiml_api_test_results.json")
        
    except ValueError as e:
        print(f"❌ 初始化失败: {e}")
    except Exception as e:
        print(f"❌ 执行失败: {e}")

if __name__ == "__main__":
    print("🔑 需要设置AIML_API_KEY才能运行")
    print("   export AIML_API_KEY=your_actual_api_key")
    print("   然后运行: python3 aiml_api_complete_implementation.py")
    
    # 如果有API密钥则运行测试
    if os.getenv('AIML_API_KEY'):
        asyncio.run(main())
    else:
        print("\n⚠️ AIML_API_KEY未设置，无法测试模型连接")
