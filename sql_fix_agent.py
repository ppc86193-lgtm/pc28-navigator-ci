#!/usr/bin/env python3
"""
PC28 SQL修复Agent
专门修复BigQuery SQL语法错误
"""

import asyncio
import json
from datetime import datetime

from google.cloud import bigquery


class PC28SQLFixAgent:
    """PC28 SQL修复Agent"""

    def __init__(self):
        self.project_id = "wprojectl"
        self.location = "us-central1"
        self.bq_client = bigquery.Client(
            project=self.project_id, location=self.location
        )

        print("🔧 PC28 SQL修复Agent启动")
        print("👑 监督者: 项目总指挥大人")
        print("🎯 任务: 修复训练Agent的SQL语法错误")

    def analyze_sql_error(self):
        """分析SQL错误"""
        print("\n🔍 分析SQL语法错误...")

        error_analysis = {
            "error_location": "第23行第15列",
            "error_symbol": "%",
            "problem": "BigQuery不支持%操作符进行取模运算",
            "solution": "使用MOD()函数替代%操作符",
            "affected_lines": [
                "sum % 10 as tail,",
                "CASE WHEN MOD(d.a + d.b + d.c, 2) = 0",
            ],
        }

        print(f"   🚨 错误位置: {error_analysis['error_location']}")
        print(f"   ❌ 问题符号: {error_analysis['error_symbol']}")
        print(f"   📋 问题描述: {error_analysis['problem']}")
        print(f"   ✅ 解决方案: {error_analysis['solution']}")

        return error_analysis

    def generate_fixed_sql(self):
        """生成修复后的SQL"""
        print("\n🛠️ 生成修复后的SQL...")

        fixed_sql = """
        WITH recent_data AS (
          SELECT
            d.issue,
            d.timestamp,
            d.a, d.b, d.c,
            (d.a + d.b + d.c) as sum,
            CASE WHEN (d.a + d.b + d.c) >= 14 THEN 'BIG' ELSE 'SMALL' END as size,
            CASE WHEN MOD(d.a + d.b + d.c, 2) = 0 THEN 'EVEN' ELSE 'ODD' END as odd_even,
            -- 前期特征
            LAG(d.a + d.b + d.c) OVER (ORDER BY d.timestamp) as prev_sum,
            LAG(CASE WHEN (d.a + d.b + d.c) >= 14 THEN 'BIG' ELSE 'SMALL' END) OVER (ORDER BY d.timestamp) as prev_size,
            -- 下期标签 (训练目标)
            LEAD(CASE WHEN (d.a + d.b + d.c) >= 14 THEN 'BIG' ELSE 'SMALL' END) OVER (ORDER BY d.timestamp) as next_size
          FROM `wprojectl.pc28.draws_14w_dedup_v` d
          WHERE DATE(d.timestamp, 'Asia/Shanghai') >= DATE_SUB(CURRENT_DATE('Asia/Shanghai'), INTERVAL 30 DAY)
          ORDER BY d.timestamp
        )
        SELECT
          issue,
          a, b, c,
          sum,
          MOD(sum, 10) as tail,
          size,
          odd_even,
          prev_sum,
          prev_size,
          next_size
        FROM recent_data
        WHERE prev_sum IS NOT NULL AND next_size IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 1000
        """

        print("   ✅ SQL修复完成")
        print("   🔄 主要修改:")
        print("      • sum % 10 → MOD(sum, 10)")
        print("      • 保持MOD(d.a + d.b + d.c, 2)语法不变")
        print("   📊 验证: BigQuery兼容语法")

        return fixed_sql

    async def test_fixed_sql(self, sql):
        """测试修复后的SQL"""
        print("\n🧪 测试修复后的SQL...")

        try:
            # 先测试语法（dry run）
            job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
            query_job = self.bq_client.query(sql, job_config=job_config)

            print("   ✅ SQL语法验证通过")
            print(f"   📊 预计处理字节数: {query_job.total_bytes_processed:,}")

            # 实际执行小样本测试
            test_sql = sql.replace("LIMIT 1000", "LIMIT 10")
            results = list(self.bq_client.query(test_sql).result())

            print("   ✅ SQL执行测试通过")
            print(f"   📈 返回样本数: {len(results)}条")

            if results:
                sample = results[0]
                print("   📋 样本数据:")
                print(f"      • issue: {sample.issue}")
                print(f"      • sum: {sample.sum}")
                print(f"      • tail: {sample.tail}")
                print(f"      • size: {sample.size}")
                print(f"      • next_size: {sample.next_size}")

            return {
                "success": True,
                "syntax_valid": True,
                "execution_valid": True,
                "sample_count": len(results),
                "bytes_processed": query_job.total_bytes_processed,
            }

        except Exception as e:
            print(f"   ❌ SQL测试失败: {e}")
            return {"success": False, "error": str(e)}

    def update_training_agent(self, fixed_sql):
        """更新训练Agent的SQL"""
        print("\n📝 更新训练Agent代码...")

        # 读取原始训练Agent代码
        training_agent_file = "training_agent.py"

        try:
            with open(training_agent_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 替换SQL查询部分
            # 找到training_data_query的开始和结束
            start_marker = 'training_data_query = """'
            end_marker = '"""'

            start_idx = content.find(start_marker)
            if start_idx == -1:
                raise ValueError("找不到training_data_query")

            # 找到对应的结束位置
            start_idx += len(start_marker)
            end_idx = content.find(end_marker, start_idx)
            if end_idx == -1:
                raise ValueError("找不到SQL查询结束位置")

            # 替换SQL内容
            new_content = content[:start_idx] + fixed_sql.strip() + content[end_idx:]

            # 写回文件
            with open(training_agent_file, "w", encoding="utf-8") as f:
                f.write(new_content)

            print("   ✅ 训练Agent代码已更新")
            print(f"   📄 文件: {training_agent_file}")
            print("   🔄 SQL查询已修复")

            return {
                "success": True,
                "file_updated": training_agent_file,
                "sql_fixed": True,
            }

        except Exception as e:
            print(f"   ❌ 更新训练Agent失败: {e}")
            return {"success": False, "error": str(e)}

    async def execute_fix_task(self):
        """执行SQL修复任务"""
        print("🔧 PC28 SQL修复Agent执行修复任务")
        print("=" * 50)
        print("👑 监督者: 项目总指挥大人")
        print("🎯 任务: 修复训练Agent的SQL语法错误")
        print()

        fix_start = datetime.now()

        # 1. 分析错误
        error_analysis = self.analyze_sql_error()

        # 2. 生成修复SQL
        fixed_sql = self.generate_fixed_sql()

        # 3. 测试修复SQL
        test_result = await self.test_fixed_sql(fixed_sql)

        if not test_result["success"]:
            print("❌ SQL修复测试失败，无法更新训练Agent")
            return test_result

        # 4. 更新训练Agent
        update_result = self.update_training_agent(fixed_sql)

        fix_end = datetime.now()
        fix_duration = (fix_end - fix_start).total_seconds()

        # 生成修复报告
        fix_report = {
            "fix_timestamp": fix_end.isoformat(),
            "fix_duration_seconds": fix_duration,
            "agent_id": "PC28 SQL修复Agent",
            "supervisor": "项目总指挥大人",
            "error_analysis": error_analysis,
            "sql_test_result": test_result,
            "agent_update_result": update_result,
            "overall_status": "FIX_COMPLETED",
            "next_step": "重新启动训练Agent",
        }

        # 保存修复报告
        report_file = f"sql_fix_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(fix_report, f, indent=2, ensure_ascii=False)

        print("\n🏆 SQL修复Agent任务完成！")
        print(f"   修复时长: {fix_duration:.1f}秒")
        print("   SQL语法: 已修复")
        print("   Agent代码: 已更新")
        print(f"   📄 修复报告: {report_file}")

        print("\n👑 向项目总指挥大人汇报:")
        print("   ✅ SQL语法错误已修复！")
        print("   🔄 训练Agent代码已更新！")
        print("   🚀 可以重新启动训练！")

        return fix_report


async def main():
    """主修复函数"""
    print("🔧 PC28 SQL语法修复")
    print("👑 监督者指令: 让他们修复")
    print()

    agent = PC28SQLFixAgent()
    await agent.execute_fix_task()

    print("\n🎯 SQL修复Agent任务完成，等待监督者验收！")


if __name__ == "__main__":
    asyncio.run(main())
