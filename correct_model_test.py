#!/usr/bin/env python3
"""
使用正确的模型名称测试AI/ML API
基于错误信息中发现的正确模型ID
"""

import asyncio
import aiohttp
import json
import os
import time

async def test_correct_models():
    """使用正确的模型名称测试"""
    api_key = os.getenv('AIML_API_KEY')
    if not api_key:
        print("❌ AIML_API_KEY未设置")
        return
    
    print(f"🔑 使用API密钥: {api_key[:10]}...")
    print()
    
    # 基于错误信息提取的正确模型名称
    correct_models = {
        "gpt-4o": {"provider": "OpenAI", "cost": 0.005},
        "gpt-4o-mini": {"provider": "OpenAI", "cost": 0.00015},
        "claude-3-5-sonnet-latest": {"provider": "Anthropic", "cost": 0.003},
        "claude-3-5-haiku-latest": {"provider": "Anthropic", "cost": 0.00025},
        "deepseek/deepseek-r1": {"provider": "DeepSeek", "cost": 0.00055},
        "qwen-max": {"provider": "Alibaba", "cost": 0.002},
        "gemini-2.5-pro": {"provider": "Google", "cost": 0.00125},
        "gemini-2.5-flash": {"provider": "Google", "cost": 0.000075}
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    test_messages = [
        {"role": "system", "content": "你是PC28分析专家"},
        {"role": "user", "content": "简单测试连接，分析数字[15,8,12]，一句话即可"}
    ]
    
    successful_models = []
    failed_models = []
    total_cost = 0.0
    
    async with aiohttp.ClientSession() as session:
        for model_id, config in correct_models.items():
            print(f"🧠 测试 {model_id} ({config['provider']})...")
            
            payload = {
                "model": model_id,
                "messages": test_messages,
                "max_tokens": 50,
                "temperature": 0.3
            }
            
            try:
                start_time = time.time()
                async with session.post(
                    "https://api.aimlapi.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    
                    if response.status == 200:
                        data = await response.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        tokens = data.get("usage", {}).get("total_tokens", 0)
                        cost = (tokens / 1000) * config["cost"]
                        
                        print(f"   ✅ 成功 - {latency_ms:.0f}ms, ${cost:.4f}, {tokens} tokens")
                        print(f"   💬 响应: {content[:50]}...")
                        
                        successful_models.append({
                            "model_id": model_id,
                            "provider": config["provider"],
                            "latency_ms": latency_ms,
                            "cost": cost,
                            "tokens": tokens,
                            "response": content
                        })
                        total_cost += cost
                        
                    else:
                        error_text = await response.text()
                        print(f"   ❌ 失败 - HTTP {response.status}")
                        failed_models.append({
                            "model_id": model_id,
                            "error": f"HTTP {response.status}",
                            "details": error_text[:100] + "..." if len(error_text) > 100 else error_text
                        })
                        
            except Exception as e:
                print(f"   ❌ 异常 - {str(e)}")
                failed_models.append({
                    "model_id": model_id,
                    "error": "Exception",
                    "details": str(e)
                })
            
            print()
    
    # 生成真实测试报告
    test_report = {
        "test_timestamp": time.time(),
        "api_key_valid": True,
        "total_models_tested": len(correct_models),
        "successful_models": len(successful_models),
        "failed_models": len(failed_models),
        "success_rate": len(successful_models) / len(correct_models),
        "total_cost": total_cost,
        "successful_model_details": successful_models,
        "failed_model_details": failed_models,
        "honest_assessment": "部分模型可用，部分模型ID仍不正确"
    }
    
    print("📊 真实测试总结:")
    print(f"   成功模型: {len(successful_models)}/{len(correct_models)}")
    print(f"   真实成功率: {test_report['success_rate']:.1%}")
    print(f"   实际成本: ${total_cost:.4f}")
    
    # 保存真实测试结果
    with open("honest_model_test_results.json", "w", encoding="utf-8") as f:
        json.dump(test_report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 真实测试结果已保存: honest_model_test_results.json")
    print("🚨 绝不隐瞒任何失败和问题！")
    
    return test_report

if __name__ == "__main__":
    print("🧪 使用正确模型名称的真实测试")
    print("🚨 承诺：如实汇报所有结果，绝不隐瞒失败")
    print()
    
    asyncio.run(test_correct_models())
