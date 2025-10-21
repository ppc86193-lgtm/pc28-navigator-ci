-- PC28系统完整审计报告真实性验证SQL
-- 法务级审计：所有语句均为只读，可直接在BigQuery控制台执行
-- 目的：验证审计报告中的关键数据主张是否真实可追溯

-- ========================================================================
-- A. "8天断流→同步3004行"核验 🚨 高优先级红旗
-- ========================================================================

-- A1: 验证近8天应补缺期数 vs 实际行数
WITH src_issues AS (
  SELECT DISTINCT issue, DATE(timestamp, 'Asia/Shanghai') as draw_date
  FROM `wprojectl.pc28.draws_clean`
  WHERE DATE(timestamp, 'Asia/Shanghai')
        BETWEEN DATE_SUB(CURRENT_DATE('Asia/Shanghai'), INTERVAL 8 DAY)
            AND CURRENT_DATE('Asia/Shanghai')
),
tf_existing AS (
  SELECT DISTINCT issue
  FROM `wprojectl.pc28.training_features`
  WHERE DATE(timestamp, 'Asia/Shanghai')
        BETWEEN DATE_SUB(CURRENT_DATE('Asia/Shanghai'), INTERVAL 8 DAY)
            AND CURRENT_DATE('Asia/Shanghai')
),
missing_analysis AS (
  SELECT
    COUNT(*) as total_source_issues_8d,
    COUNT(CASE WHEN tf.issue IS NOT NULL THEN 1 END) as existing_in_tf,
    COUNT(CASE WHEN tf.issue IS NULL THEN 1 END) as missing_issues
  FROM src_issues s
  LEFT JOIN tf_existing tf ON s.issue = tf.issue
),
actual_rows AS (
  SELECT COUNT(*) as tf_rows_added_8d
  FROM `wprojectl.pc28.training_features`
  WHERE DATE(timestamp, 'Asia/Shanghai')
        BETWEEN DATE_SUB(CURRENT_DATE('Asia/Shanghai'), INTERVAL 8 DAY)
            AND CURRENT_DATE('Asia/Shanghai')
)
SELECT
  'A1_数据同步核验' as test_name,
  ma.total_source_issues_8d,
  ma.existing_in_tf,
  ma.missing_issues,
  ar.tf_rows_added_8d,
  -- 🚨 关键验证点：3004行是否可信
  CASE
    WHEN ar.tf_rows_added_8d BETWEEN 2950 AND 3050 THEN '✅ 3004行基本可信'
    WHEN ar.tf_rows_added_8d < 1500 THEN '🚨 显著低于3004，需解释'
    ELSE '⚠️ 与3004有差异，需核查倍数关系'
  END as verification_result
FROM missing_analysis ma
CROSS JOIN actual_rows ar;

-- ========================================================================
-- B. "670条预测(134期×5模型)"核验
-- ========================================================================

-- B1: 验证今日模型预测总数和分布
WITH model_counts AS (
  SELECT
    COUNT(*) as total_predictions_today,
    COUNT(DISTINCT model_id) as active_models,
    COUNT(DISTINCT period) as predicted_periods
  FROM `wprojectl.pc28.model_predictions`
  WHERE DATE(prediction_timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
),
model_breakdown AS (
  SELECT
    model_id,
    COUNT(*) as predictions_per_model
  FROM `wprojectl.pc28.model_predictions`
  WHERE DATE(prediction_timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
  GROUP BY model_id
  ORDER BY model_id
)
SELECT
  'B1_模型预测核验' as test_name,
  mc.total_predictions_today,
  mc.active_models,
  mc.predicted_periods,
  -- 🚨 关键验证点：670条预测是否可信
  CASE
    WHEN mc.total_predictions_today BETWEEN 650 AND 690 THEN '✅ 670条基本可信'
    WHEN mc.total_predictions_today = 0 THEN '🚨 无预测数据，系统可能未运行'
    ELSE CONCAT('⚠️ 实际', CAST(mc.total_predictions_today AS STRING), '条，与670有差异')
  END as verification_result,
  -- 验证134×5的数学逻辑
  CASE
    WHEN mc.predicted_periods * mc.active_models = mc.total_predictions_today THEN '✅ 数学逻辑一致'
    ELSE '⚠️ 期数×模型数不等于总预测数'
  END as math_check
FROM model_counts mc;

-- B2: 各模型预测数量明细
SELECT
  'B2_模型分布明细' as test_name,
  model_id,
  COUNT(*) as predictions_count,
  ROUND(AVG(prediction_big), 4) as avg_prediction_big
FROM `wprojectl.pc28.model_predictions`
WHERE DATE(prediction_timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
GROUP BY model_id
ORDER BY model_id;

-- ========================================================================
-- C. "Gate通过率88.81%(119条)"核验 🚨 高优先级红旗
-- ========================================================================

-- C1: 首先确认对象类型（核心红旗：是否能向视图INSERT）
SELECT
  'C1_对象类型核验' as test_name,
  table_name,
  table_type,
  CASE
    WHEN table_type = 'VIEW' AND table_name LIKE '%_v' THEN '🚨 视图不能INSERT，报告有误'
    WHEN table_type = 'TABLE' THEN '✅ 表可以INSERT'
    ELSE '⚠️ 需进一步确认'
  END as insert_feasibility
FROM `wprojectl.pc28.INFORMATION_SCHEMA.TABLES`
WHERE table_name IN ('consensus_candidates_api_v', 'consensus_gate_api_v', 'pred_consensus_gate_ext_v')
ORDER BY table_name;

-- C2: Gate通过率计算验证
WITH candidates_today AS (
  SELECT COUNT(*) as total_candidates
  FROM `wprojectl.pc28.consensus_candidates_api_v`
  WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
),
gate_output_today AS (
  SELECT COUNT(*) as gate_passed
  FROM `wprojectl.pc28.consensus_gate_api_v`
  WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
)
SELECT
  'C2_Gate通过率核验' as test_name,
  ct.total_candidates,
  got.gate_passed,
  SAFE_DIVIDE(got.gate_passed, ct.total_candidates) as calculated_pass_rate,
  ROUND(SAFE_DIVIDE(got.gate_passed, ct.total_candidates) * 100, 2) as pass_rate_percent,
  -- 🚨 关键验证点：88.81%是否可信
  CASE
    WHEN got.gate_passed BETWEEN 115 AND 125 THEN '✅ 119条基本可信'
    WHEN got.gate_passed = 0 THEN '🚨 Gate无输出，与报告矛盾'
    ELSE CONCAT('⚠️ 实际', CAST(got.gate_passed AS STRING), '条，与119有差异')
  END as gate_count_check,
  CASE
    WHEN ABS(ROUND(SAFE_DIVIDE(got.gate_passed, ct.total_candidates) * 100, 2) - 88.81) < 1
    THEN '✅ 88.81%基本可信'
    ELSE '⚠️ 通过率与88.81%有显著差异'
  END as pass_rate_check
FROM candidates_today ct
CROSS JOIN gate_output_today got;

-- ========================================================================
-- D. "model_3准确率54.25%"核验 🚨 需要实际准确率计算
-- ========================================================================

-- D1: 验证model_3的预测准确率（需要与开奖结果比对）
WITH model3_predictions AS (
  SELECT
    period,
    prediction_big,
    CASE WHEN prediction_big >= 0.5 THEN '大' ELSE '小' END as predicted_size
  FROM `wprojectl.pc28.model_predictions`
  WHERE model_id = 'model_3'
    AND DATE(prediction_timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
),
actual_results AS (
  SELECT
    CAST(REGEXP_EXTRACT(issue, r'(\d+)$') AS INT64) as period,
    size as actual_size
  FROM `wprojectl.pc28.draws_clean`
  WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
),
accuracy_calc AS (
  SELECT
    COUNT(*) as total_predictions,
    SUM(CASE WHEN mp.predicted_size = ar.actual_size THEN 1 ELSE 0 END) as correct_predictions
  FROM model3_predictions mp
  JOIN actual_results ar ON mp.period = ar.period
)
SELECT
  'D1_model3准确率核验' as test_name,
  ac.total_predictions,
  ac.correct_predictions,
  SAFE_DIVIDE(ac.correct_predictions, ac.total_predictions) as calculated_accuracy,
  ROUND(SAFE_DIVIDE(ac.correct_predictions, ac.total_predictions) * 100, 2) as accuracy_percent,
  -- 🚨 关键验证点：54.25%是否可信
  CASE
    WHEN ABS(ROUND(SAFE_DIVIDE(ac.correct_predictions, ac.total_predictions) * 100, 2) - 54.25) < 2
    THEN '✅ 54.25%基本可信'
    WHEN ac.total_predictions = 0 THEN '⚠️ 无法验证，缺少预测数据'
    ELSE '🚨 准确率与54.25%有显著差异'
  END as accuracy_check
FROM accuracy_calc ac;

-- ========================================================================
-- E. "votes_today 804条"核验
-- ========================================================================

-- E1: 验证投票系统数据量
SELECT
  'E1_投票系统核验' as test_name,
  COUNT(*) as actual_votes_today,
  CASE
    WHEN COUNT(*) BETWEEN 780 AND 830 THEN '✅ 804条基本可信'
    WHEN COUNT(*) = 0 THEN '🚨 无投票数据'
    ELSE CONCAT('⚠️ 实际', CAST(COUNT(*) AS STRING), '条，与804有差异')
  END as votes_check
FROM `wprojectl.pc28.votes_today`
WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai');

-- ========================================================================
-- F. "时区偏移-415分钟"核验 🚨 高度可疑的异常值
-- ========================================================================

-- F1: 时区偏移合理性检查
WITH timezone_check AS (
  SELECT
    CURRENT_TIMESTAMP() as utc_now,
    TIMESTAMP(DATETIME(CURRENT_TIMESTAMP(), 'Asia/Shanghai')) as shanghai_now,
    TIMESTAMP_DIFF(
      CURRENT_TIMESTAMP(),
      TIMESTAMP(DATETIME(CURRENT_DATE('Asia/Shanghai'), TIME(0,0,0)), 'Asia/Shanghai'),
      MINUTE
    ) as offset_minutes
)
SELECT
  'F1_时区偏移核验' as test_name,
  tc.offset_minutes,
  -- 🚨 关键验证点：-415分钟极度可疑
  CASE
    WHEN ABS(tc.offset_minutes + 415) < 10 THEN '🚨 确实存在-415分钟偏移，极度异常'
    WHEN ABS(tc.offset_minutes) <= 60 THEN '✅ 时区偏移正常范围'
    WHEN tc.offset_minutes BETWEEN -500 AND -400 THEN '⚠️ 存在异常偏移，但不是-415'
    ELSE '⚠️ 时区计算可能有问题'
  END as timezone_check,
  '正常的时区偏移应该是60分钟的整数倍，-415(-6:55)极不寻常' as note
FROM timezone_check tc;

-- ========================================================================
-- G. 数据量统计对比核验
-- ========================================================================

-- G1: 关键表的总数据量统计
SELECT 'G1_数据量统计核验' as test_name, '总量' as period_filter
UNION ALL
SELECT 'draws_clean', CAST(COUNT(*) AS STRING) FROM `wprojectl.pc28.draws_clean`
UNION ALL
SELECT 'training_features', CAST(COUNT(*) AS STRING) FROM `wprojectl.pc28.training_features`
UNION ALL
SELECT 'enhanced_training_features_v2', CAST(COUNT(*) AS STRING) FROM `wprojectl.pc28.enhanced_training_features_v2`
UNION ALL
SELECT 'model_predictions', CAST(COUNT(*) AS STRING) FROM `wprojectl.pc28.model_predictions`
UNION ALL
SELECT 'sum_based_predictions', CAST(COUNT(*) AS STRING) FROM `wprojectl.pc28.sum_based_predictions`
UNION ALL
SELECT 'combo_based_predictions', CAST(COUNT(*) AS STRING) FROM `wprojectl.pc28.combo_based_predictions`;

-- G2: 今日数据量统计
SELECT 'G2_今日数据量统计' as test_name, '今日' as period_filter
UNION ALL
SELECT 'draws_clean_today', CAST(COUNT(*) AS STRING)
FROM `wprojectl.pc28.draws_clean`
WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
UNION ALL
SELECT 'training_features_today', CAST(COUNT(*) AS STRING)
FROM `wprojectl.pc28.training_features`
WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
UNION ALL
SELECT 'model_predictions_today', CAST(COUNT(*) AS STRING)
FROM `wprojectl.pc28.model_predictions`
WHERE DATE(prediction_timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai');

-- ========================================================================
-- H. 综合可信度评分
-- ========================================================================

-- H1: 审计报告可信度综合评估
WITH verification_summary AS (
  SELECT
    '审计报告可信度评估' as assessment_type,
    CURRENT_TIMESTAMP() as verification_time,
    '基于以上SQL验证结果，请人工判断各项指标的可信度' as instruction,
    '🔴 必须立即修正的问题' as critical_issues,
    '1. 如果pred_consensus_gate_ext_v是视图却声称INSERT，属于技术性错误' as issue_1,
    '2. 如果时区偏移确实是-415分钟，需要解释异常原因' as issue_2,
    '3. 如果3004行与实际数据量差异过大，需要说明计算口径' as issue_3,
    '🟡 需要补充证据的声明' as evidence_needed,
    '1. 54.25%准确率需要提供计算窗口和市场范围' as evidence_1,
    '2. 88.81%通过率需要明确分母统计口径' as evidence_2,
    '3. 所有"L4自动驾驶"等定性判断需要量化标准' as evidence_3
)
SELECT * FROM verification_summary;

-- ========================================================================
-- 使用说明
-- ========================================================================
/*
使用方法：
1. 复制以上SQL到BigQuery控制台
2. 替换项目名：wprojectl → 你的实际项目名
3. 逐段执行，记录每个验证结果
4. 根据验证结果更新审计报告，修正不实声明
5. 保留作业ID作为可追溯证据

重点关注：
- A1: 3004行是否真实
- B1: 670条预测是否真实
- C1: 对象类型是否支持INSERT操作
- C2: 88.81%通过率是否可复现
- D1: 54.25%准确率是否可验证
- F1: -415分钟时区偏移是否异常

如果任何一项显示🚨标志，必须在审计报告中修正或补充说明。
*/