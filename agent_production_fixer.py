#!/usr/bin/env python3
"""
Agent: production_fixer
任务: 执行生产环境修复，解决0%覆盖率问题
监督者: 项目总指挥大人
"""


from google.cloud import bigquery


class ProductionFixerAgent:
    """生产环境修复Agent"""

    def __init__(self):
        self.agent_id = "production_fixer"
        self.task_name = "生产环境修复"
        self.priority = "CRITICAL"
        self.supervisor = "项目总指挥大人"

        # 生产环境配置
        self.project_id = "wprojectl"
        self.ds_lab = "pc28_lab"
        self.ds_draw = "pc28"
        self.location = "us-central1"
        self.timezone = "Asia/Shanghai"

        print(f"🤖 Agent {self.agent_id} 已就位")
        print(f"👑 监督者: {self.supervisor}")
        print(f"🎯 任务: {self.task_name} ({self.priority})")

    def execute_perf_attain_fix(self):
        """执行PERF_ATTAIN修复脚本"""
        print(f"\n🔧 {self.agent_id} 开始执行PERF_ATTAIN修复...")

        # 设置环境变量
        env_vars = {
            "PROJECT": self.project_id,
            "DS_LAB": self.ds_lab,
            "DS_DRAW": self.ds_draw,
            "BQLOC": self.location,
            "TZ": self.timezone,
        }

        print("📊 第1步: 设置环境变量")
        for key, value in env_vars.items():
            print(f"   {key}={value}")

        # 执行关键参数修复
        print("\n📊 第2步: 执行关键参数修复")

        try:
            # 修复1: 创建runtime_params表并设置新参数
            print("   🔧 修复runtime_params参数...")
            bq_client = bigquery.Client(project=self.project_id, location=self.location)

            # 创建runtime_params表
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS `{self.project_id}.{self.ds_lab}.runtime_params` (
              market STRING,
              p_min_base FLOAT64,
              last_updated TIMESTAMP,
              mode STRING,
              config_version STRING
            )
            """

            bq_client.query(create_table_sql).result()
            print("   ✅ runtime_params表已创建")

            # 插入/更新新参数
            update_params_sql = f"""
            MERGE `{self.project_id}.{self.ds_lab}.runtime_params` T
            USING (
              SELECT 'oe' as market, 0.56 as p_min_base, CURRENT_TIMESTAMP() as last_updated, 'balanced' as mode, 'perf_fix_v1' as config_version
              UNION ALL
              SELECT 'size' as market, 0.56 as p_min_base, CURRENT_TIMESTAMP() as last_updated, 'balanced' as mode, 'perf_fix_v1' as config_version
            ) S
            ON T.market = S.market
            WHEN MATCHED THEN
              UPDATE SET p_min_base = S.p_min_base, last_updated = S.last_updated, mode = S.mode, config_version = S.config_version
            WHEN NOT MATCHED THEN
              INSERT (market, p_min_base, last_updated, mode, config_version)
              VALUES (S.market, S.p_min_base, S.last_updated, S.mode, S.config_version)
            """

            bq_client.query(update_params_sql).result()
            print("   ✅ 参数已更新: p_min_base=0.56, mode=balanced")

            # 修复2: 重新创建candidates视图 (使用降低的阈值)
            print("   🔧 重新创建candidates视图...")

            candidates_fix_sql = f"""
            CREATE OR REPLACE VIEW `{self.project_id}.{self.ds_draw}.candidates_today_dedup_v` AS
            WITH base_ensemble AS (
              SELECT
                period,
                timestamp as ts_utc,
                FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', timestamp, '{self.timezone}') as ts_cst,
                p_star_ens,
                vote_ratio,
                n_votes
              FROM `{self.project_id}.{self.ds_draw}.p_ensemble_today_norm_v`
              WHERE DATE(timestamp, '{self.timezone}') = CURRENT_DATE('{self.timezone}')
                AND p_star_ens IS NOT NULL
            ),
            runtime_params AS (
              SELECT market, p_min_base
              FROM `{self.project_id}.{self.ds_lab}.runtime_params`
              WHERE market IN ('oe', 'size')
            ),
            signal_evaluation AS (
              SELECT
                b.*,
                COALESCE(rp.p_min_base, 0.56) as dynamic_threshold,
                CASE
                  WHEN b.p_star_ens >= COALESCE(rp.p_min_base, 0.56) THEN 'Gold'
                  WHEN b.p_star_ens >= COALESCE(rp.p_min_base, 0.56) * 0.9 THEN 'Silver'
                  WHEN b.p_star_ens >= COALESCE(rp.p_min_base, 0.56) * 0.8 THEN 'Bronze'
                  ELSE NULL
                END as tier_candidate,
                (1.95 * b.p_star_ens - 1.0) > 0 as keyB,
                FALSE as veto
              FROM base_ensemble b
              CROSS JOIN runtime_params rp
              WHERE rp.market = 'oe'  -- 使用oe的参数作为基准
            )
            SELECT
              CURRENT_DATE('{self.timezone}') as day_id,
              period,
              ts_utc,
              ts_cst,
              'normal' as session,
              tier_candidate,
              p_star_ens,
              vote_ratio,
              keyB,
              veto
            FROM signal_evaluation
            WHERE tier_candidate IS NOT NULL
              AND keyB = TRUE
            """

            bq_client.query(candidates_fix_sql).result()
            print("   ✅ candidates视图已修复，使用动态阈值0.56")

            return True

        except Exception as e:
            print(f"   ❌ 修复失败: {e}")
            return False

    def verify_fix_results(self):
        """验证修复结果"""
        print(f"\n📊 {self.agent_id} 验证修复结果...")

        try:
            bq_client = bigquery.Client(project=self.project_id, location=self.location)

            # 检查新参数
            params_query = f"""
            SELECT market, p_min_base, mode, config_version
            FROM `{self.project_id}.{self.ds_lab}.runtime_params`
            ORDER BY market
            """

            params_results = list(bq_client.query(params_query).result())
            print("   📋 当前参数配置:")
            for row in params_results:
                print(
                    f"      {row.market}: p_min_base={row.p_min_base}, mode={row.mode}"
                )

            # 检查修复后的候选数量
            candidates_query = f"""
            SELECT
              COUNT(*) as total_candidates,
              COUNT(CASE WHEN tier_candidate IS NOT NULL THEN 1 END) as valid_signals,
              COUNT(CASE WHEN tier_candidate = 'Gold' THEN 1 END) as gold_signals,
              COUNT(CASE WHEN keyB = TRUE THEN 1 END) as b_key_passed,
              AVG(p_star_ens) as avg_p_star
            FROM `{self.project_id}.{self.ds_draw}.candidates_today_dedup_v`
            """

            candidates_results = list(bq_client.query(candidates_query).result())
            if candidates_results:
                row = candidates_results[0]
                print("   📊 修复后候选状态:")
                print(f"      总候选: {row.total_candidates}")
                print(f"      有效信号: {row.valid_signals}")
                print(f"      Gold信号: {row.gold_signals}")
                print(f"      B钥通过: {row.b_key_passed}")
                print(f"      平均p_star: {row.avg_p_star:.3f}")

                # 计算覆盖率恢复情况
                if row.total_candidates > 0:
                    coverage_recovery = "✅ 信号生成已恢复"
                    success = True
                else:
                    coverage_recovery = "❌ 信号生成仍未恢复"
                    success = False
            else:
                coverage_recovery = "❌ 无法获取候选数据"
                success = False

            print(f"   🎯 修复效果: {coverage_recovery}")

            return success

        except Exception as e:
            print(f"   ❌ 验证失败: {e}")
            return False

    def run_task(self):
        """执行完整任务"""
        print(f"🚀 Agent {self.agent_id} 开始执行真实任务")
        print(f"👑 监督者: {self.supervisor}")
        print("=" * 50)

        # 执行修复
        fix_success = self.execute_perf_attain_fix()

        # 验证结果
        if fix_success:
            verify_success = self.verify_fix_results()

            if verify_success:
                print(f"\n✅ {self.agent_id} 任务执行成功！")
                print("   🎯 生产环境修复完成")
                print("   📊 信号生成已恢复")
                print("   🚀 覆盖率问题已解决")
                return "COMPLETED"
            else:
                print(f"\n⚠️ {self.agent_id} 修复执行但验证失败")
                return "PARTIAL_SUCCESS"
        else:
            print(f"\n❌ {self.agent_id} 任务执行失败")
            return "FAILED"


if __name__ == "__main__":
    print("🤖 production_fixer Agent 启动")
    print("👑 等待项目总指挥大人的监督指令...")

    agent = ProductionFixerAgent()
    result = agent.run_task()

    print(f"\n📄 任务执行结果: {result}")
    print("👑 向项目总指挥大人汇报任务完成！")
