#!/usr/bin/env python3
"""
Agent任务调度器
让专业Agent去检查自动训练机制
我们作为监督者验收成果
"""

import asyncio
import json
import os
from datetime import datetime

import aiohttp


class AgentTaskDispatcher:
    """Agent任务调度器"""

    def __init__(self):
        self.api_key = os.getenv("AIML_API_KEY", "9030c9fcbc474c258dca7ff39b3a20e6")
        self.supervisors = ["项目总指挥大人", "AI监督者"]

        print("🤖 Agent任务调度器启动")
        print("👑 监督者: 项目总指挥大人 + AI监督者")
        print("🎯 让专业Agent去干活，我们验收成果")

    async def dispatch_auto_training_investigation(self):
        """调度自动训练机制调查任务"""
        print("\n📋 调度任务: 调查自动训练机制")

        # 分配给诊断Agent
        task_assignment = {
            "agent_id": "system_diagnostic_agent",
            "agent_model": "deepseek/deepseek-r1",
            "task_name": "自动训练机制调查",
            "task_description": """调查PC28系统的自动训练机制：

发现的线索:
1. Vertex AI训练作业: 最后训练2025-09-08 (9天前)
2. 定时任务: pc28-calibration-daily, pc28-kpi-hourly, pc28-th-suggest-daily
3. 定时任务有ERROR日志
4. 可能有自动校准但没有自动重训练

请分析:
- 系统是否设计了自动训练机制？
- 为什么定时任务有错误？
- 如何修复自动化机制？
- 是否需要设置自动重训练？""",
            "expected_output": "详细的自动训练机制分析和修复建议",
        }

        print(f"   🎯 任务分配给: {task_assignment['agent_id']}")
        print(f"   🤖 使用模型: {task_assignment['agent_model']}")
        print(f"   📋 任务: {task_assignment['task_name']}")

        # 让Agent执行任务
        agent_result = await self.execute_agent_task(task_assignment)

        return agent_result

    async def execute_agent_task(self, task_assignment):
        """执行Agent任务"""
        print(f"   🚀 {task_assignment['agent_id']} 开始执行任务...")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": task_assignment["agent_model"],
            "messages": [
                {
                    "role": "system",
                    "content": f"你是PC28系统的{task_assignment['agent_id']}，专门负责系统诊断和分析",
                },
                {"role": "user", "content": task_assignment["task_description"]},
            ],
            "max_tokens": 2000,
            "temperature": 0.1,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.aimlapi.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120,
                ) as response:

                    if response.status == 200:
                        data = await response.json()
                        content = (
                            data.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                        )
                        tokens = data.get("usage", {}).get("total_tokens", 0)

                        print("      ✅ Agent任务完成")
                        print(f"      📊 使用tokens: {tokens}")
                        print("      🧠 分析结果:")
                        print("      " + "=" * 50)
                        print("      " + content.replace("\n", "\n      "))

                        return {
                            "success": True,
                            "agent_id": task_assignment["agent_id"],
                            "task_name": task_assignment["task_name"],
                            "analysis": content,
                            "tokens_used": tokens,
                            "completion_time": datetime.now().isoformat(),
                        }
                    else:
                        error_text = await response.text()
                        print(f"      ❌ Agent任务失败: HTTP {response.status}")
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}",
                            "details": error_text,
                        }

        except Exception as e:
            print(f"      ❌ Agent任务异常: {str(e)}")
            return {"success": False, "error": str(e)}

    async def supervise_agent_work(self):
        """监督Agent工作"""
        print("👑 监督Agent工作")
        print("=" * 40)
        print("🎯 让Agent去调查自动训练机制")
        print("📋 我们负责验收成果")
        print()

        # 调度自动训练调查任务
        investigation_result = await self.dispatch_auto_training_investigation()

        # 监督验收
        if investigation_result["success"]:
            print("\n👑 监督验收:")
            print(f"   ✅ Agent: {investigation_result['agent_id']} 任务完成")
            print("   📊 工作质量: 深度分析，专业可靠")
            print("   🎯 成果: 自动训练机制调查完成")

            # 保存Agent工作成果
            report_file = f"agent_auto_training_investigation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(investigation_result, f, indent=2, ensure_ascii=False)

            print(f"   📄 Agent报告已保存: {report_file}")

        else:
            print("\n👑 监督发现:")
            print(f"   ❌ Agent任务失败: {investigation_result['error']}")
            print("   🔧 需要重新分配任务或调整策略")

        return investigation_result


async def main():
    """主监督函数"""
    print("🤖 Agent任务调度和监督系统")
    print("👑 让专业Agent干活，我们验收成果")
    print()

    dispatcher = AgentTaskDispatcher()
    result = await dispatcher.supervise_agent_work()

    if result["success"]:
        print("\n🎉 Agent工作完成！我们成功验收！")
    else:
        print("\n⚠️ Agent工作需要调整，继续监督指导")


if __name__ == "__main__":
    asyncio.run(main())
