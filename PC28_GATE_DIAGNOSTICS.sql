-- PC28 Gate诊断与优化方案
-- 解决 consensus_gate_api_v 零输出问题

-- 1. Gate诊断视图 - 拆解每个过滤条件
CREATE OR REPLACE VIEW `wprojectl.pc28.gate_diagnosis_v` AS
WITH
-- 获取候选数据
candidates AS (
  SELECT
    issue,
    timestamp,
    confidence,
    voters_agree,
    recent_hit_rate,
    prediction_grade,
    participating_models,
    final_prediction,
    ROW_NUMBER() OVER (ORDER BY timestamp DESC) as rn
  FROM `wprojectl.pc28.consensus_candidates_api_v`
  WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
),
-- 规则拆解诊断
rule_breakdown AS (
  SELECT
    c.*,
    -- 规则1: 置信度阈值
    (COALESCE(c.confidence, 0) >= 0.65) AS pass_confidence,
    0.65 AS threshold_confidence,

    -- 规则2: 投票者一致性
    (COALESCE(c.voters_agree, 0) >= 3) AS pass_voters,
    3 AS threshold_voters,

    -- 规则3: 近期命中率
    (COALESCE(c.recent_hit_rate, 0) >= 0.55) AS pass_hit_rate,
    0.55 AS threshold_hit_rate,

    -- 规则4: 预测等级
    (c.prediction_grade IN ('HIGH_CONFIDENCE', 'MEDIUM_CONFIDENCE')) AS pass_grade,

    -- 规则5: 参与模型数量
    (COALESCE(c.participating_models, 0) >= 4) AS pass_model_count,
    4 AS threshold_model_count
  FROM candidates c
),
-- 综合通过判定
pass_analysis AS (
  SELECT
    rb.*,
    (pass_confidence AND pass_voters AND pass_hit_rate AND pass_grade AND pass_model_count) AS would_pass_all,

    -- 各规则失败原因
    CASE
      WHEN NOT pass_confidence THEN 'confidence_low'
      WHEN NOT pass_voters THEN 'voters_insufficient'
      WHEN NOT pass_hit_rate THEN 'hit_rate_low'
      WHEN NOT pass_grade THEN 'grade_insufficient'
      WHEN NOT pass_model_count THEN 'models_insufficient'
      ELSE 'pass'
    END AS first_failure_reason,

    -- 差距分析
    GREATEST(0, threshold_confidence - COALESCE(confidence, 0)) AS confidence_gap,
    GREATEST(0, threshold_voters - COALESCE(voters_agree, 0)) AS voters_gap,
    GREATEST(0, threshold_hit_rate - COALESCE(recent_hit_rate, 0)) AS hit_rate_gap,
    GREATEST(0, threshold_model_count - COALESCE(participating_models, 0)) AS model_count_gap
  FROM rule_breakdown rb
)
SELECT * FROM pass_analysis
ORDER BY timestamp DESC;

-- ===================================================

-- 2. Gate通过率统计视图
CREATE OR REPLACE VIEW `wprojectl.pc28.gate_pass_rate_analysis` AS
WITH daily_stats AS (
  SELECT
    DATE(timestamp, 'Asia/Shanghai') as analysis_date,
    COUNT(*) as total_candidates,
    SUM(CASE WHEN would_pass_all THEN 1 ELSE 0 END) as would_pass_count,

    -- 各规则通过率
    AVG(CASE WHEN pass_confidence THEN 1.0 ELSE 0.0 END) as confidence_pass_rate,
    AVG(CASE WHEN pass_voters THEN 1.0 ELSE 0.0 END) as voters_pass_rate,
    AVG(CASE WHEN pass_hit_rate THEN 1.0 ELSE 0.0 END) as hit_rate_pass_rate,
    AVG(CASE WHEN pass_grade THEN 1.0 ELSE 0.0 END) as grade_pass_rate,
    AVG(CASE WHEN pass_model_count THEN 1.0 ELSE 0.0 END) as model_count_pass_rate,

    -- 失败原因分布
    SUM(CASE WHEN first_failure_reason = 'confidence_low' THEN 1 ELSE 0 END) as failed_by_confidence,
    SUM(CASE WHEN first_failure_reason = 'voters_insufficient' THEN 1 ELSE 0 END) as failed_by_voters,
    SUM(CASE WHEN first_failure_reason = 'hit_rate_low' THEN 1 ELSE 0 END) as failed_by_hit_rate,
    SUM(CASE WHEN first_failure_reason = 'grade_insufficient' THEN 1 ELSE 0 END) as failed_by_grade,
    SUM(CASE WHEN first_failure_reason = 'models_insufficient' THEN 1 ELSE 0 END) as failed_by_models,

    -- 平均差距
    AVG(confidence_gap) as avg_confidence_gap,
    AVG(voters_gap) as avg_voters_gap,
    AVG(hit_rate_gap) as avg_hit_rate_gap,
    AVG(model_count_gap) as avg_model_count_gap

  FROM `wprojectl.pc28.gate_diagnosis_v`
  GROUP BY DATE(timestamp, 'Asia/Shanghai')
)
SELECT
  *,
  ROUND(would_pass_count * 100.0 / total_candidates, 2) as overall_pass_rate,

  -- 建议的阈值调整
  CASE
    WHEN confidence_pass_rate < 0.1 THEN 'Lower confidence threshold to 0.5'
    WHEN voters_pass_rate < 0.1 THEN 'Lower voters threshold to 2'
    WHEN hit_rate_pass_rate < 0.1 THEN 'Lower hit_rate threshold to 0.45'
    WHEN model_count_pass_rate < 0.1 THEN 'Lower model_count threshold to 3'
    ELSE 'Thresholds appear reasonable'
  END as threshold_recommendation
FROM daily_stats
ORDER BY analysis_date DESC;

-- ===================================================

-- 3. Gate冷启动保护机制
CREATE OR REPLACE VIEW `wprojectl.pc28.gate_with_fallback` AS
WITH
-- 正常Gate逻辑（从诊断视图获取would_pass的记录）
normal_gate AS (
  SELECT issue, timestamp, confidence, final_prediction, 'NORMAL' as source
  FROM `wprojectl.pc28.gate_diagnosis_v`
  WHERE would_pass_all = true
),
-- 冷启动保护（当正常Gate输出<3条时，选择top候选）
fallback_gate AS (
  SELECT
    issue, timestamp, confidence, final_prediction, 'FALLBACK' as source
  FROM `wprojectl.pc28.consensus_candidates_api_v`
  WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
  ORDER BY
    COALESCE(confidence, 0) DESC,
    COALESCE(participating_models, 0) DESC,
    timestamp DESC
  LIMIT 5
),
-- 决策逻辑
gate_decision AS (
  SELECT COUNT(*) as normal_count FROM normal_gate
)
SELECT
  ng.issue, ng.timestamp, ng.confidence, ng.final_prediction, ng.source
FROM normal_gate ng, gate_decision gd
WHERE gd.normal_count >= 3  -- 正常情况

UNION ALL

SELECT
  fg.issue, fg.timestamp, fg.confidence, fg.final_prediction, fg.source
FROM fallback_gate fg, gate_decision gd
WHERE gd.normal_count < 3  -- 冷启动保护

ORDER BY timestamp DESC;

-- ===================================================

-- 4. Gate决策日志表
CREATE TABLE IF NOT EXISTS `wprojectl.pc28.gate_decisions_log` (
  decision_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  issue STRING,
  decision_type STRING,  -- 'PASS', 'REJECT', 'FALLBACK'
  confidence FLOAT64,
  voters_agree INT64,
  recent_hit_rate FLOAT64,
  participating_models INT64,
  failure_reason STRING,
  threshold_used JSON,
  final_prediction FLOAT64
);

-- ===================================================

-- 5. Gate阈值参数表（支持动态调整）
CREATE TABLE IF NOT EXISTS `wprojectl.pc28.gate_parameters` (
  parameter_name STRING,
  parameter_value FLOAT64,
  effective_date DATE,
  description STRING,
  last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 插入默认参数
INSERT INTO `wprojectl.pc28.gate_parameters`
(parameter_name, parameter_value, effective_date, description)
VALUES
  ('confidence_threshold', 0.65, CURRENT_DATE(), '置信度阈值'),
  ('voters_threshold', 3.0, CURRENT_DATE(), '投票者数量阈值'),
  ('hit_rate_threshold', 0.55, CURRENT_DATE(), '近期命中率阈值'),
  ('model_count_threshold', 4.0, CURRENT_DATE(), '参与模型数量阈值'),
  ('fallback_trigger_count', 3.0, CURRENT_DATE(), '冷启动保护触发阈值')
ON CONFLICT(parameter_name, effective_date) DO NOTHING;

-- ===================================================

-- 6. 动态阈值Gate视图（从参数表读取阈值）
CREATE OR REPLACE VIEW `wprojectl.pc28.consensus_gate_api_v2` AS
WITH
-- 获取当前参数
current_params AS (
  SELECT
    MAX(CASE WHEN parameter_name = 'confidence_threshold' THEN parameter_value END) as conf_threshold,
    MAX(CASE WHEN parameter_name = 'voters_threshold' THEN parameter_value END) as voters_threshold,
    MAX(CASE WHEN parameter_name = 'hit_rate_threshold' THEN parameter_value END) as hit_rate_threshold,
    MAX(CASE WHEN parameter_name = 'model_count_threshold' THEN parameter_value END) as model_threshold,
    MAX(CASE WHEN parameter_name = 'fallback_trigger_count' THEN parameter_value END) as fallback_count
  FROM `wprojectl.pc28.gate_parameters`
  WHERE effective_date <= CURRENT_DATE()
),
-- 应用动态阈值判断
candidates_with_dynamic_rules AS (
  SELECT
    c.*,
    p.conf_threshold,
    p.voters_threshold,
    p.hit_rate_threshold,
    p.model_threshold,
    p.fallback_count,

    -- 动态规则判断
    (COALESCE(c.confidence, 0) >= p.conf_threshold) AS pass_confidence,
    (COALESCE(c.voters_agree, 0) >= p.voters_threshold) AS pass_voters,
    (COALESCE(c.recent_hit_rate, 0) >= p.hit_rate_threshold) AS pass_hit_rate,
    (COALESCE(c.participating_models, 0) >= p.model_threshold) AS pass_models
  FROM `wprojectl.pc28.consensus_candidates_api_v` c
  CROSS JOIN current_params p
  WHERE DATE(c.timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
),
-- 正常通过的记录
normal_pass AS (
  SELECT *
  FROM candidates_with_dynamic_rules
  WHERE pass_confidence AND pass_voters AND pass_hit_rate AND pass_models
),
-- 冷启动保护
fallback_records AS (
  SELECT *
  FROM candidates_with_dynamic_rules
  ORDER BY
    COALESCE(confidence, 0) DESC,
    COALESCE(participating_models, 0) DESC
  LIMIT 5
)
-- 最终输出逻辑
SELECT issue, timestamp, confidence, voters_agree, recent_hit_rate, participating_models, final_prediction
FROM normal_pass
WHERE (SELECT COUNT(*) FROM normal_pass) >= (SELECT fallback_count FROM current_params LIMIT 1)

UNION ALL

SELECT issue, timestamp, confidence, voters_agree, recent_hit_rate, participating_models, final_prediction
FROM fallback_records
WHERE (SELECT COUNT(*) FROM normal_pass) < (SELECT fallback_count FROM current_params LIMIT 1)

ORDER BY confidence DESC, timestamp DESC;