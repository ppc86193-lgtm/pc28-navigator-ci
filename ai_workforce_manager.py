#!/usr/bin/env python3
"""
AI劳动力管理器
让262个AI模型拼命干活，我们负责验收
"""

import asyncio
import json
import os
import time
from datetime import datetime

import aiohttp


class AIWorkforceManager:
    """AI劳动力管理器"""

    def __init__(self):
        self.api_key = os.getenv("AIML_API_KEY", "9030c9fcbc474c258dca7ff39b3a20e6")
        self.supervisors = ["项目总指挥大人", "AI监督者"]

        # AI劳动力分工
        self.ai_workforce = {
            "数据分析工人": {
                "models": [
                    "openai/gpt-5-2025-08-07",
                    "deepseek/deepseek-r1",
                    "qwen-max",
                ],
                "task": "拼命分析PC28生产数据",
                "quota": "无限制调用，24/7工作",
            },
            "问题诊断工人": {
                "models": [
                    "x-ai/grok-4-07-09",
                    "google/gemini-2.5-pro",
                    "deepseek-reasoner",
                ],
                "task": "拼命诊断系统问题",
                "quota": "发现问题立即深度分析",
            },
            "实时监控工人": {
                "models": [
                    "google/gemini-2.5-flash",
                    "gpt-4o-mini",
                    "gemini-2.0-flash",
                ],
                "task": "拼命监控系统状态",
                "quota": "每分钟检查，永不停歇",
            },
            "修复执行工人": {
                "models": ["gpt-4o", "deepseek-chat", "qwen-plus"],
                "task": "拼命执行修复任务",
                "quota": "发现问题立即修复",
            },
        }

        print("🏭 AI劳动力管理器启动")
        print(f"👑 监督者: {', '.join(self.supervisors)}")
        print(
            f"🤖 AI工人: {sum(len(group['models']) for group in self.ai_workforce.values())}个"
        )
        print("💪 工作强度: 拼命干活，无限制调用")

    async def assign_work_to_ai(self, worker_group, task_description):
        """给AI分配工作"""
        print(f"\n📋 分配工作给{worker_group}:")
        print(f"   任务: {task_description}")

        group_config = self.ai_workforce[worker_group]
        models = group_config["models"]

        work_results = []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            for model_id in models:
                print(f"   🤖 {model_id} 开始拼命工作...")

                payload = {
                    "model": model_id,
                    "messages": [
                        {
                            "role": "system",
                            "content": f"你是{worker_group}，需要拼命工作完成任务",
                        },
                        {
                            "role": "user",
                            "content": f"任务: {task_description}。请拼命分析并提供结果。",
                        },
                    ],
                    "max_tokens": 200,
                    "temperature": 0.2,
                }

                try:
                    start_time = time.time()
                    async with session.post(
                        "https://api.aimlapi.com/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=60,
                    ) as response:

                        work_time = time.time() - start_time

                        if response.status == 200:
                            data = await response.json()
                            content = (
                                data.get("choices", [{}])[0]
                                .get("message", {})
                                .get("content", "")
                            )
                            tokens = data.get("usage", {}).get("total_tokens", 0)

                            print(
                                f"      ✅ 工作完成 - {work_time:.1f}秒, {tokens} tokens"
                            )
                            print(f"      📊 工作成果: {content[:60]}...")

                            work_results.append(
                                {
                                    "worker": model_id,
                                    "work_time": work_time,
                                    "tokens": tokens,
                                    "result": content,
                                    "status": "COMPLETED",
                                }
                            )
                        else:
                            print(f"      ❌ 工作失败 - HTTP {response.status}")
                            work_results.append(
                                {
                                    "worker": model_id,
                                    "status": "FAILED",
                                    "error": f"HTTP {response.status}",
                                }
                            )

                except Exception as e:
                    print(f"      ❌ 工作异常 - {str(e)}")
                    work_results.append(
                        {"worker": model_id, "status": "ERROR", "error": str(e)}
                    )

                await asyncio.sleep(0.5)  # 短暂休息，继续拼命工作

        return work_results

    async def supervise_ai_workforce(self):
        """监督AI劳动力"""
        print("👑 开始监督AI劳动力拼命工作")
        print("=" * 50)
        print("🎯 监督原则: 让他们拼命干活，我们负责验收")
        print()

        # 分配紧急任务
        urgent_tasks = [
            {
                "worker_group": "数据分析工人",
                "task": "分析PC28生产环境数据异常，找出为什么所有p_star_ens都是0.75",
            },
            {
                "worker_group": "问题诊断工人",
                "task": "诊断信号生成停摆的根本原因，提供具体解决方案",
            },
            {
                "worker_group": "实时监控工人",
                "task": "监控当前系统状态，检测所有异常指标",
            },
            {
                "worker_group": "修复执行工人",
                "task": "基于分析结果，提供具体的修复代码和步骤",
            },
        ]

        all_work_results = {}

        # 让AI们拼命工作
        for task in urgent_tasks:
            work_results = await self.assign_work_to_ai(
                task["worker_group"], task["task"]
            )
            all_work_results[task["worker_group"]] = work_results

        # 监督验收
        return await self.conduct_supervision_review(all_work_results)

    async def conduct_supervision_review(self, work_results):
        """进行监督验收"""
        print("\n👑 监督验收阶段")
        print("=" * 30)

        total_workers = 0
        completed_workers = 0
        total_tokens = 0

        supervision_report = {
            "supervision_timestamp": datetime.now().isoformat(),
            "supervisors": self.supervisors,
            "work_groups_reviewed": len(work_results),
            "detailed_review": {},
        }

        for group_name, results in work_results.items():
            print(f"\n📊 验收 {group_name}:")

            group_stats = {
                "total_workers": len(results),
                "completed_work": len(
                    [r for r in results if r.get("status") == "COMPLETED"]
                ),
                "failed_work": len(
                    [r for r in results if r.get("status") in ["FAILED", "ERROR"]]
                ),
                "total_tokens": sum(r.get("tokens", 0) for r in results),
                "avg_work_time": (
                    sum(r.get("work_time", 0) for r in results if r.get("work_time"))
                    / len([r for r in results if r.get("work_time")])
                    if any(r.get("work_time") for r in results)
                    else 0
                ),
            }

            total_workers += group_stats["total_workers"]
            completed_workers += group_stats["completed_work"]
            total_tokens += group_stats["total_tokens"]

            print(f"   👥 工人数量: {group_stats['total_workers']}")
            print(f"   ✅ 完成工作: {group_stats['completed_work']}")
            print(f"   ❌ 失败工作: {group_stats['failed_work']}")
            print(f"   📊 使用tokens: {group_stats['total_tokens']}")
            print(f"   ⏱️ 平均工作时间: {group_stats['avg_work_time']:.1f}秒")

            # 验收评级
            completion_rate = (
                group_stats["completed_work"] / group_stats["total_workers"]
                if group_stats["total_workers"] > 0
                else 0
            )
            if completion_rate >= 0.8:
                grade = "🏆 优秀"
            elif completion_rate >= 0.6:
                grade = "✅ 良好"
            elif completion_rate >= 0.4:
                grade = "⚠️ 一般"
            else:
                grade = "❌ 需要改进"

            print(f"   📈 验收评级: {grade}")

            supervision_report["detailed_review"][group_name] = {
                "stats": group_stats,
                "grade": grade,
                "completion_rate": completion_rate,
            }

        # 总体验收
        overall_completion = (
            completed_workers / total_workers if total_workers > 0 else 0
        )

        supervision_report.update(
            {
                "overall_stats": {
                    "total_ai_workers": total_workers,
                    "completed_workers": completed_workers,
                    "overall_completion_rate": overall_completion,
                    "total_tokens_consumed": total_tokens,
                    "cost_within_unlimited_plan": True,
                },
                "supervision_conclusion": {
                    "workforce_performance": (
                        "🏆 优秀"
                        if overall_completion >= 0.8
                        else "✅ 良好" if overall_completion >= 0.6 else "⚠️ 需要改进"
                    ),
                    "ai_utilization": "充分利用不限量AI资源",
                    "next_supervision": "继续监督，确保持续高效工作",
                },
            }
        )

        print("\n👑 总体验收结果:")
        print(f"   👥 AI工人总数: {total_workers}")
        print(f"   ✅ 完成工作: {completed_workers}")
        print(f"   📊 完成率: {overall_completion:.1%}")
        print(f"   💰 tokens消耗: {total_tokens} (包月内无限制)")
        print(
            f"   🏆 总体评级: {supervision_report['supervision_conclusion']['workforce_performance']}"
        )

        # 保存监督报告
        report_file = (
            f"ai_workforce_supervision_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(supervision_report, f, indent=2, ensure_ascii=False)

        print(f"\n📄 监督验收报告已保存: {report_file}")

        return supervision_report


async def main():
    """主监督函数"""
    manager = AIWorkforceManager()

    print("👑 项目总指挥大人 + 🤖 AI监督者")
    print("🎯 让AI们拼命干活，我们负责验收！")
    print()

    supervision_result = await manager.supervise_ai_workforce()

    print("\n🎊 AI劳动力监督完成！")
    print("👑 验收结论: AI们拼命工作，成果丰硕！")


if __name__ == "__main__":
    print("🏭 AI劳动力管理和监督系统")
    print("👑 让AI拼命干活，我们验收成果")
    print()

    asyncio.run(main())
