#!/usr/bin/env python3
"""
获取AI/ML API所有可用模型
基于 https://api.aimlapi.com/models 接口
"""

import asyncio
import aiohttp
import json
import os
from datetime import datetime

class AllModelsRetriever:
    """所有模型获取器"""
    
    def __init__(self):
        self.api_key = os.getenv('AIML_API_KEY', '9030c9fcbc474c258dca7ff39b3a20e6')
        self.models_endpoint = "https://api.aimlapi.com/models"
        
        print("🔍 AI/ML API所有模型获取器")
        print(f"🔑 API密钥: {self.api_key[:10]}...")
        print(f"📡 接口: {self.models_endpoint}")
    
    async def get_all_available_models(self):
        """获取所有可用模型"""
        print(f"\n📊 获取所有可用模型...")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.models_endpoint,
                    headers=headers,
                    timeout=30
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        if "data" in data:
                            models = data["data"]
                            
                            # 分析模型
                            model_analysis = self.analyze_models(models)
                            
                            # 保存完整模型列表
                            complete_models_data = {
                                "retrieval_timestamp": datetime.now().isoformat(),
                                "api_endpoint": self.models_endpoint,
                                "total_models": len(models),
                                "model_analysis": model_analysis,
                                "complete_model_list": models
                            }
                            
                            with open("all_available_models.json", "w", encoding="utf-8") as f:
                                json.dump(complete_models_data, f, indent=2, ensure_ascii=False)
                            
                            print(f"✅ 成功获取 {len(models)} 个模型")
                            print(f"📄 完整列表已保存: all_available_models.json")
                            
                            return model_analysis
                        else:
                            print("❌ 响应格式异常")
                            return None
                    else:
                        print(f"❌ 请求失败: HTTP {response.status}")
                        return None
                        
        except Exception as e:
            print(f"❌ 获取失败: {str(e)}")
            return None
    
    def analyze_models(self, models):
        """分析模型列表"""
        print(f"   🔍 分析 {len(models)} 个模型...")
        
        # 按类型分类
        model_types = {}
        providers = {}
        
        # 高价值模型识别
        premium_models = []
        
        for model in models:
            model_id = model.get("id", "")
            model_type = model.get("type", "unknown")
            info = model.get("info", {})
            developer = info.get("developer", "Unknown")
            name = info.get("name", "")
            
            # 分类统计
            if model_type not in model_types:
                model_types[model_type] = []
            model_types[model_type].append(model_id)
            
            if developer not in providers:
                providers[developer] = []
            providers[developer].append(model_id)
            
            # 识别高价值模型
            if any(keyword in model_id.lower() for keyword in [
                "gpt-5", "gpt-4o", "claude", "gemini", "deepseek", "qwen", "grok"
            ]):
                premium_models.append({
                    "id": model_id,
                    "name": name,
                    "developer": developer,
                    "type": model_type
                })
        
        analysis = {
            "total_models": len(models),
            "model_types": {k: len(v) for k, v in model_types.items()},
            "providers": {k: len(v) for k, v in providers.items()},
            "premium_models": premium_models,
            "model_categories": {
                "chat_completion": len(model_types.get("chat-completion", [])),
                "image_generation": len(model_types.get("image", [])),
                "video_generation": len(model_types.get("video", [])),
                "audio_generation": len(model_types.get("audio", [])),
                "embedding": len(model_types.get("embedding", []))
            }
        }
        
        # 显示分析结果
        print(f"   📊 模型类型分布:")
        for model_type, count in analysis["model_categories"].items():
            print(f"      • {model_type}: {count}个")
        
        print(f"   🏢 提供商分布:")
        top_providers = sorted(analysis["providers"].items(), key=lambda x: x[1], reverse=True)[:5]
        for provider, count in top_providers:
            print(f"      • {provider}: {count}个模型")
        
        print(f"   ⭐ 高价值模型: {len(premium_models)}个")
        for model in premium_models[:10]:  # 显示前10个
            print(f"      • {model['id']} ({model['developer']})")
        
        return analysis
    
    async def test_premium_models(self, analysis):
        """测试高价值模型"""
        print(f"\n🧪 测试高价值模型...")
        
        premium_models = analysis.get("premium_models", [])
        chat_models = [m for m in premium_models if "chat" in m.get("type", "").lower() or m.get("type") == "chat-completion"]
        
        print(f"   🎯 测试 {len(chat_models)} 个对话模型...")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        working_models = []
        
        async with aiohttp.ClientSession() as session:
            for model in chat_models[:10]:  # 测试前10个
                model_id = model["id"]
                print(f"      🧠 测试 {model_id}...")
                
                payload = {
                    "model": model_id,
                    "messages": [
                        {"role": "user", "content": "Hello, test connection"}
                    ],
                    "max_tokens": 10,
                    "temperature": 0.1
                }
                
                try:
                    async with session.post(
                        "https://api.aimlapi.com/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=15
                    ) as response:
                        
                        if response.status == 200:
                            print(f"         ✅ 可用")
                            working_models.append(model)
                        else:
                            print(f"         ❌ 不可用 (HTTP {response.status})")
                            
                except Exception as e:
                    print(f"         ❌ 异常 ({str(e)[:30]}...)")
                
                await asyncio.sleep(0.5)
        
        print(f"   📊 测试结果: {len(working_models)}/{len(chat_models[:10])} 可用")
        
        return working_models

async def main():
    """主函数"""
    retriever = AllModelsRetriever()
    
    # 获取所有模型
    analysis = await retriever.get_all_available_models()
    
    if analysis:
        # 测试高价值模型
        working_models = await retriever.test_premium_models(analysis)
        
        print(f"\n🏆 模型获取完成!")
        print(f"   总模型数: {analysis['total_models']}")
        print(f"   高价值模型: {len(analysis['premium_models'])}")
        print(f"   实际可用: {len(working_models)}")
        
        # 生成可用模型配置
        usable_config = {
            "timestamp": datetime.now().isoformat(),
            "total_available": analysis['total_models'],
            "premium_available": len(analysis['premium_models']),
            "tested_working": len(working_models),
            "working_models": working_models,
            "recommendation": "基于实际测试的可用模型配置"
        }
        
        with open("usable_models_config.json", "w", encoding="utf-8") as f:
            json.dump(usable_config, f, indent=2, ensure_ascii=False)
        
        print(f"📄 可用模型配置已保存: usable_models_config.json")
    else:
        print("❌ 模型获取失败")

if __name__ == "__main__":
    print("🔍 获取AI/ML API所有可用模型")
    print("📡 接口: https://api.aimlapi.com/models")
    print()
    
    asyncio.run(main())
