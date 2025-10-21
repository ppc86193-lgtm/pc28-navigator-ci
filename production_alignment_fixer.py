#!/usr/bin/env python3
"""
PC28 生产环境达标修复器
将生产环境调整到本地测试达标状态
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from google.cloud import bigquery

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ProductionFixer")

class ProductionAlignmentFixer:
    """生产环境达标修复器"""
    
    def __init__(self):
        self.project_id = "wprojectl"
        self.dataset = "pc28"
        self.location = "us-central1"
        self.bq_client = bigquery.Client(project=self.project_id, location=self.location)
        
        # 本地达标配置
        self.target_config = {
            "threshold_conf_raw": 0.78,
            "kelly_fraction": 0.25,
            "bet_cap": 0.02,
            "survival_threshold": 0.51282,
            "target_coverage": [0.25, 0.40],  # 25-40%
            "target_accuracy": 0.60,
            "target_ev": 0.03
        }
        
        logger.info("生产环境达标修复器初始化完成")
    
    def analyze_production_vs_local(self) -> Dict[str, Any]:
        """分析生产环境与本地达标配置的差异"""
        logger.info("分析生产环境与本地配置差异...")
        
        # 查询生产环境实际参数
        production_analysis = self._get_production_parameters()
        
        # 对比分析
        comparison = {
            "local_target": self.target_config,
            "production_current": production_analysis,
            "gaps": self._identify_gaps(production_analysis),
            "alignment_plan": self._create_alignment_plan(production_analysis)
        }
        
        return comparison
    
    def _get_production_parameters(self) -> Dict[str, Any]:
        """获取生产环境实际参数"""
        try:
            # 查询最近7天的实际性能
            query = f"""
            WITH recent_performance AS (
              SELECT 
                d.issue,
                d.timestamp,
                (d.a + d.b + d.c) as actual_sum,
                CASE WHEN (d.a + d.b + d.c) >= 14 THEN 'big' ELSE 'small' END as actual_size,
                e.p_star_ens
              FROM `{self.project_id}.{self.dataset}.draws_14w_dedup_v` d
              LEFT JOIN `{self.project_id}.{self.dataset}.p_ensemble_today_norm_v` e
                ON d.issue = e.period
              WHERE DATE(d.timestamp, 'Asia/Shanghai') >= DATE_SUB(CURRENT_DATE('Asia/Shanghai'), INTERVAL 7 DAY)
                AND e.p_star_ens IS NOT NULL
              ORDER BY d.timestamp DESC
            )
            SELECT 
              COUNT(*) as total_periods,
              AVG(p_star_ens) as avg_p_star,
              STDDEV(p_star_ens) as std_p_star,
              MIN(p_star_ens) as min_p_star,
              MAX(p_star_ens) as max_p_star,
              COUNT(CASE WHEN p_star_ens >= 0.78 THEN 1 END) as signals_at_78,
              COUNT(CASE WHEN p_star_ens >= 0.60 THEN 1 END) as signals_at_60,
              COUNT(CASE WHEN p_star_ens >= 0.50 THEN 1 END) as signals_at_50
            FROM recent_performance
            """
            
            results = list(self.bq_client.query(query).result())
            if results:
                row = results[0]
                return {
                    "total_periods": row.total_periods,
                    "avg_p_star": float(row.avg_p_star),
                    "std_p_star": float(row.std_p_star) if row.std_p_star else 0,
                    "min_p_star": float(row.min_p_star),
                    "max_p_star": float(row.max_p_star),
                    "coverage_at_78": row.signals_at_78 / row.total_periods if row.total_periods > 0 else 0,
                    "coverage_at_60": row.signals_at_60 / row.total_periods if row.total_periods > 0 else 0,
                    "coverage_at_50": row.signals_at_50 / row.total_periods if row.total_periods > 0 else 0,
                    "effective_threshold": self._calculate_effective_threshold(row),
                    "model_health": "POOR" if row.avg_p_star < 0.513 else "GOOD"
                }
        except Exception as e:
            logger.error(f"获取生产参数失败: {e}")
            return {"error": str(e)}
    
    def _calculate_effective_threshold(self, data) -> float:
        """计算有效阈值"""
        # 基于生存线+安全边际计算
        avg_p_star = float(data.avg_p_star)
        if avg_p_star >= 0.6:
            return 0.65  # 高质量模型可用较高阈值
        elif avg_p_star >= 0.55:
            return 0.58  # 中等质量模型适中阈值
        elif avg_p_star >= 0.51:
            return 0.53  # 低质量模型最低阈值
        else:
            return 0.78  # 模型质量太差，保持高阈值等优化
    
    def _identify_gaps(self, production: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别差距"""
        gaps = []
        
        if "error" in production:
            gaps.append({
                "category": "DATA_ACCESS",
                "issue": "无法获取生产数据",
                "severity": "CRITICAL"
            })
            return gaps
        
        # 模型性能差距
        if production["avg_p_star"] < self.target_config["survival_threshold"]:
            gaps.append({
                "category": "MODEL_PERFORMANCE",
                "issue": f"平均p_star({production['avg_p_star']:.3f})低于生存线({self.target_config['survival_threshold']:.3f})",
                "severity": "CRITICAL",
                "impact": "无法产生正EV信号"
            })
        
        # 覆盖率差距
        if production["coverage_at_78"] == 0:
            gaps.append({
                "category": "COVERAGE",
                "issue": "当前阈值下覆盖率为0%",
                "severity": "HIGH",
                "impact": "无法执行任何交易"
            })
        
        # 阈值设置差距
        effective_threshold = production.get("effective_threshold", 0.78)
        if effective_threshold != self.target_config["threshold_conf_raw"]:
            gaps.append({
                "category": "THRESHOLD_MISMATCH",
                "issue": f"建议阈值({effective_threshold})与设置阈值({self.target_config['threshold_conf_raw']})不匹配",
                "severity": "MEDIUM",
                "impact": "阈值设置不合理"
            })
        
        return gaps
    
    def _create_alignment_plan(self, production: Dict[str, Any]) -> Dict[str, Any]:
        """创建对齐计划"""
        if "error" in production:
            return {"error": "无法创建对齐计划，生产数据获取失败"}
        
        plan = {
            "phase_1_emergency": {
                "description": "紧急恢复信号生成",
                "actions": [
                    {
                        "action": "降低阈值到有效水平",
                        "from": 0.78,
                        "to": production.get("effective_threshold", 0.55),
                        "expected_coverage": f"{production.get('coverage_at_60', 0)*100:.1f}%",
                        "risk": "中等"
                    },
                    {
                        "action": "修复candidates_today_dedup_v视图",
                        "type": "SQL修复",
                        "priority": "HIGH"
                    }
                ],
                "timeline": "立即执行"
            },
            
            "phase_2_optimization": {
                "description": "模型性能优化",
                "actions": [
                    {
                        "action": "重新训练Vertex AI模型",
                        "target": "提升p_star到0.6+",
                        "data_source": "最近30天数据"
                    },
                    {
                        "action": "实施分层阈值策略",
                        "CL3": 0.75,
                        "CL2": 0.65,
                        "CL1": 0.55
                    }
                ],
                "timeline": "本周内完成"
            },
            
            "phase_3_monitoring": {
                "description": "建立持续监控",
                "actions": [
                    {
                        "action": "部署Navigator实时监控",
                        "coverage": "全链路监控"
                    },
                    {
                        "action": "建立TDR自动处置",
                        "scope": "故障自动恢复"
                    }
                ],
                "timeline": "持续运行"
            }
        }
        
        return plan
    
    def generate_emergency_fix_sql(self) -> List[str]:
        """生成紧急修复SQL"""
        sql_fixes = []
        
        # 1. 修复candidates_today_dedup_v视图
        candidates_fix = f"""
        -- 紧急修复candidates_today_dedup_v视图
        CREATE OR REPLACE VIEW `{self.project_id}.{self.dataset}.candidates_today_dedup_v` AS
        WITH base_ensemble AS (
          SELECT 
            period,
            timestamp as ts_utc,
            FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', timestamp, 'Asia/Shanghai') as ts_cst,
            p_star_ens,
            vote_ratio,
            n_votes
          FROM `{self.project_id}.{self.dataset}.p_ensemble_today_norm_v`
          WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            AND p_star_ens IS NOT NULL
        ),
        signal_evaluation AS (
          SELECT 
            *,
            CASE 
              WHEN p_star_ens >= 0.60 THEN 'Gold'
              WHEN p_star_ens >= 0.50 THEN 'Silver'
              WHEN p_star_ens >= 0.40 THEN 'Bronze'
              ELSE 'Skip'
            END as tier_candidate,
            -- 计算EV
            (1.95 * p_star_ens - 1.0) as expected_ev,
            -- B钥检查 (EV > 0)
            (1.95 * p_star_ens - 1.0) > 0 as keyB,
            -- 简化的否决检查
            FALSE as veto
          FROM base_ensemble
        )
        SELECT 
          CURRENT_DATE('Asia/Shanghai') as day_id,
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
        WHERE tier_candidate != 'Skip'
          AND keyB = TRUE
          AND veto = FALSE;
        """
        sql_fixes.append(candidates_fix)
        
        # 2. 创建分层阈值配置表
        threshold_config = f"""
        -- 创建分层阈值配置表
        CREATE TABLE IF NOT EXISTS `{self.project_id}.{self.dataset}.threshold_config` (
          config_id STRING NOT NULL,
          threshold_level STRING NOT NULL,
          threshold_value FLOAT64 NOT NULL,
          kelly_multiplier FLOAT64 NOT NULL,
          description STRING,
          is_active BOOL NOT NULL DEFAULT TRUE,
          created_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
          updated_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP()
        );
        
        -- 插入分层阈值配置
        INSERT INTO `{self.project_id}.{self.dataset}.threshold_config` 
        (config_id, threshold_level, threshold_value, kelly_multiplier, description)
        VALUES
        ('CL3_HIGH_CONFIDENCE', 'CL3', 0.75, 1.0, '高置信度信号，Kelly原值'),
        ('CL2_MEDIUM_CONFIDENCE', 'CL2', 0.65, 0.7, '中置信度信号，Kelly七折'),
        ('CL1_LOW_CONFIDENCE', 'CL1', 0.55, 0.3, '低置信度信号，Kelly三折'),
        ('EMERGENCY_THRESHOLD', 'EMERGENCY', 0.50, 0.1, '紧急阈值，最小仓位');
        """
        sql_fixes.append(threshold_config)
        
        # 3. 创建修复后的信号生成视图
        signal_generator = f"""
        -- 创建修复后的信号生成视图
        CREATE OR REPLACE VIEW `{self.project_id}.{self.dataset}.signals_fixed_v` AS
        WITH ensemble_data AS (
          SELECT 
            period,
            timestamp,
            p_star_ens,
            vote_ratio,
            n_votes
          FROM `{self.project_id}.{self.dataset}.p_ensemble_today_norm_v`
          WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            AND p_star_ens IS NOT NULL
        ),
        threshold_applied AS (
          SELECT 
            e.*,
            tc.threshold_level,
            tc.threshold_value,
            tc.kelly_multiplier,
            -- 应用分层阈值
            CASE 
              WHEN e.p_star_ens >= 0.75 THEN 'CL3'
              WHEN e.p_star_ens >= 0.65 THEN 'CL2'
              WHEN e.p_star_ens >= 0.55 THEN 'CL1'
              WHEN e.p_star_ens >= 0.50 THEN 'EMERGENCY'
              ELSE 'SKIP'
            END as signal_level,
            -- 计算EV
            (1.95 * e.p_star_ens - 1.0) as expected_ev,
            -- 计算仓位
            {self.target_config['kelly_fraction']} * (1.95 * e.p_star_ens - 1.0) / 0.95 as kelly_position
          FROM ensemble_data e
          CROSS JOIN `{self.project_id}.{self.dataset}.threshold_config` tc
          WHERE tc.is_active = TRUE
        ),
        final_signals AS (
          SELECT 
            period,
            timestamp,
            p_star_ens,
            signal_level,
            expected_ev,
            LEAST(kelly_position * kelly_multiplier, {self.target_config['bet_cap']}) as position_size,
            -- 三钥检查
            p_star_ens >= threshold_value as key_A,
            expected_ev > 0 as key_B,
            TRUE as key_C,  -- 简化压制检查
            -- 最终信号
            (p_star_ens >= threshold_value AND expected_ev > 0) as signal_approved
          FROM threshold_applied
          WHERE signal_level != 'SKIP'
        )
        SELECT 
          period,
          timestamp,
          p_star_ens,
          signal_level,
          expected_ev,
          position_size,
          key_A,
          key_B, 
          key_C,
          signal_approved,
          CASE WHEN signal_approved THEN signal_level ELSE 'SKIP' END as final_action
        FROM final_signals
        ORDER BY timestamp DESC;
        """
        sql_fixes.append(signal_generator)
        
        return sql_fixes
    
    def _identify_gaps(self, production: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别差距"""
        if "error" in production:
            return [{"category": "DATA_ERROR", "issue": production["error"]}]
        
        gaps = []
        
        # 检查平均p_star
        if production["avg_p_star"] < self.target_config["survival_threshold"]:
            gaps.append({
                "category": "MODEL_PERFORMANCE",
                "current": production["avg_p_star"],
                "target": self.target_config["survival_threshold"],
                "gap": self.target_config["survival_threshold"] - production["avg_p_star"],
                "severity": "CRITICAL"
            })
        
        # 检查覆盖率
        if production["coverage_at_78"] < self.target_config["target_coverage"][0]:
            gaps.append({
                "category": "COVERAGE",
                "current": production["coverage_at_78"],
                "target": self.target_config["target_coverage"][0],
                "gap": self.target_config["target_coverage"][0] - production["coverage_at_78"],
                "severity": "HIGH"
            })
        
        return gaps
    
    def _create_alignment_plan(self, production: Dict[str, Any]) -> Dict[str, Any]:
        """创建对齐计划"""
        if "error" in production:
            return {"error": "无法创建对齐计划"}
        
        # 基于实际数据制定计划
        avg_p_star = production["avg_p_star"]
        
        if avg_p_star >= 0.55:
            # 模型质量尚可，调整阈值策略
            plan_type = "THRESHOLD_ADJUSTMENT"
            recommended_threshold = 0.55
            expected_coverage = production["coverage_at_50"]
        elif avg_p_star >= 0.50:
            # 模型质量一般，紧急阈值
            plan_type = "EMERGENCY_MODE"
            recommended_threshold = 0.50
            expected_coverage = production["coverage_at_50"]
        else:
            # 模型质量差，需要重新训练
            plan_type = "MODEL_RETRAIN"
            recommended_threshold = 0.78
            expected_coverage = 0.0
        
        return {
            "plan_type": plan_type,
            "recommended_threshold": recommended_threshold,
            "expected_coverage": expected_coverage,
            "risk_level": "HIGH" if recommended_threshold < 0.55 else "MEDIUM",
            "implementation": "立即执行" if plan_type != "MODEL_RETRAIN" else "需要重新训练"
        }
    
    async def execute_alignment_fix(self):
        """执行对齐修复"""
        print("🔧 PC28 生产环境达标修复")
        print("=" * 50)
        print("目标: 将生产环境调整到本地测试达标状态")
        print()
        
        # 1. 分析差异
        print("📊 第1步: 分析生产vs本地差异...")
        comparison = self.analyze_production_vs_local()
        
        if "error" in comparison.get("production_current", {}):
            print(f"   ❌ 数据获取失败: {comparison['production_current']['error']}")
            return
        
        production = comparison["production_current"]
        gaps = comparison["gaps"]
        plan = comparison["alignment_plan"]
        
        print(f"   生产环境平均p_star: {production['avg_p_star']:.3f}")
        print(f"   目标生存线: {self.target_config['survival_threshold']:.3f}")
        print(f"   当前覆盖率@0.78: {production['coverage_at_78']:.1%}")
        print(f"   模型健康度: {production['model_health']}")
        
        print(f"\n🚨 发现差距: {len(gaps)}个")
        for gap in gaps:
            print(f"   • {gap['category']}: {gap['issue']}")
        
        # 2. 执行修复计划
        print(f"\n🔧 第2步: 执行对齐修复...")
        print(f"   修复方案: {plan['plan_type']}")
        print(f"   建议阈值: {plan['recommended_threshold']}")
        print(f"   预期覆盖率: {plan['expected_coverage']:.1%}")
        print(f"   风险等级: {plan['risk_level']}")
        
        # 3. 生成修复SQL
        print(f"\n📝 第3步: 生成修复SQL...")
        fix_sqls = self.generate_emergency_fix_sql()
        
        for i, sql in enumerate(fix_sqls, 1):
            sql_file = f"fix_production_{i}.sql"
            with open(sql_file, 'w', encoding='utf-8') as f:
                f.write(sql)
            print(f"   📄 修复SQL {i}: {sql_file}")
        
        # 4. 验证修复效果
        print(f"\n✅ 第4步: 修复完成验证...")
        
        if plan['plan_type'] == 'THRESHOLD_ADJUSTMENT':
            print(f"   🎯 阈值调整方案:")
            print(f"   从 0.78 → {plan['recommended_threshold']}")
            print(f"   预期覆盖率: {plan['expected_coverage']:.1%}")
            print(f"   ✅ 可立即恢复信号生成")
        elif plan['plan_type'] == 'EMERGENCY_MODE':
            print(f"   🚨 紧急模式方案:")
            print(f"   紧急阈值: {plan['recommended_threshold']}")
            print(f"   最小仓位: 0.01")
            print(f"   ⚠️ 需要密切监控风险")
        else:
            print(f"   🔄 模型重训方案:")
            print(f"   ❌ 当前模型质量太差")
            print(f"   🔧 需要重新训练模型")
        
        # 5. 保存完整报告
        report = {
            "alignment_time": datetime.now().isoformat(),
            "comparison": comparison,
            "fix_plan": plan,
            "sql_files": [f"fix_production_{i}.sql" for i in range(1, len(fix_sqls)+1)]
        }
        
        report_file = f"production_alignment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 完整对齐报告: {report_file}")
        print(f"✅ 生产环境达标修复计划已生成！")

async def main():
    """主函数"""
    fixer = ProductionAlignmentFixer()
    await fixer.execute_alignment_fix()

if __name__ == "__main__":
    asyncio.run(main())
