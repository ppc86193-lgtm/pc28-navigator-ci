-- PC28数据标准化紧急修复方案
-- 发现问题: size/odd_even字段存在7种不同格式
-- 影响: 导致模型训练和评估基于混乱的标签数据

-- 1. 创建标准化函数
CREATE OR REPLACE FUNCTION `wprojectl.pc28_lab.standardize_size`(size_value STRING) AS (
  CASE
    WHEN UPPER(size_value) IN ('LARGE', 'BIG', '大') THEN 'large'
    WHEN UPPER(size_value) IN ('SMALL', '小') THEN 'small'
    WHEN LOWER(size_value) IN ('large', 'small') THEN LOWER(size_value)
    ELSE 'unknown'
  END
);

CREATE OR REPLACE FUNCTION `wprojectl.pc28_lab.standardize_odd_even`(odd_even_value STRING) AS (
  CASE
    WHEN UPPER(odd_even_value) IN ('ODD', '单') THEN 'odd'
    WHEN UPPER(odd_even_value) IN ('EVEN', '双') THEN 'even'
    WHEN LOWER(odd_even_value) IN ('odd', 'even') THEN LOWER(odd_even_value)
    ELSE 'unknown'
  END
);

-- 2. 验证函数正确性
WITH function_test AS (
  SELECT
    'LARGE' as input, `wprojectl.pc28_lab.standardize_size`('LARGE') as output
  UNION ALL SELECT 'BIG', `wprojectl.pc28_lab.standardize_size`('BIG')
  UNION ALL SELECT '大', `wprojectl.pc28_lab.standardize_size`('大')
  UNION ALL SELECT 'SMALL', `wprojectl.pc28_lab.standardize_size`('SMALL')
  UNION ALL SELECT '小', `wprojectl.pc28_lab.standardize_size`('小')
  UNION ALL SELECT 'ODD', `wprojectl.pc28_lab.standardize_odd_even`('ODD')
  UNION ALL SELECT 'EVEN', `wprojectl.pc28_lab.standardize_odd_even`('EVEN')
  UNION ALL SELECT '单', `wprojectl.pc28_lab.standardize_odd_even`('单')
  UNION ALL SELECT '双', `wprojectl.pc28_lab.standardize_odd_even`('双')
)
SELECT * FROM function_test;

-- 3. 创建标准化后的清洁表
CREATE OR REPLACE TABLE `wprojectl.pc28_lab.draws_14w_clean` AS
SELECT
  issue,
  timestamp,
  a, b, c, sum, tail,
  hour, session, source,
  -- 标准化字段
  `wprojectl.pc28_lab.standardize_size`(size) as size,
  `wprojectl.pc28_lab.standardize_odd_even`(odd_even) as odd_even,
  -- 基于和值重新计算验证 (PC28标准: >=14为大)
  CASE WHEN sum >= 14 THEN 'large' ELSE 'small' END as size_calculated,
  CASE WHEN MOD(sum, 2) = 1 THEN 'odd' ELSE 'even' END as odd_even_calculated
FROM `wprojectl.pc28_lab.draws_14w_partitioned`;

-- 4. 数据质量验证报告
CREATE OR REPLACE VIEW `wprojectl.pc28_lab.data_quality_report` AS
WITH validation_summary AS (
  SELECT
    COUNT(*) as total_rows,
    -- 标准化效果
    COUNT(CASE WHEN size IN ('large', 'small') THEN 1 END) as size_standardized,
    COUNT(CASE WHEN odd_even IN ('odd', 'even') THEN 1 END) as odd_even_standardized,
    -- 计算一致性
    COUNT(CASE WHEN size = size_calculated THEN 1 END) as size_matches,
    COUNT(CASE WHEN odd_even = odd_even_calculated THEN 1 END) as odd_even_matches,
    -- 分布统计
    COUNT(CASE WHEN size = 'large' THEN 1 END) as large_count,
    COUNT(CASE WHEN size = 'small' THEN 1 END) as small_count,
    COUNT(CASE WHEN odd_even = 'odd' THEN 1 END) as odd_count,
    COUNT(CASE WHEN odd_even = 'even' THEN 1 END) as even_count
  FROM `wprojectl.pc28_lab.draws_14w_clean`
)
SELECT
  *,
  ROUND(size_standardized / total_rows, 4) as size_standardization_rate,
  ROUND(odd_even_standardized / total_rows, 4) as odd_even_standardization_rate,
  ROUND(size_matches / total_rows, 4) as size_accuracy_rate,
  ROUND(odd_even_matches / total_rows, 4) as odd_even_accuracy_rate,
  ROUND(large_count / total_rows, 4) as large_distribution,
  ROUND(odd_count / total_rows, 4) as odd_distribution
FROM validation_summary;

-- 5. 原子性表替换操作 (慎重执行)
-- 备份原表
-- CREATE TABLE `wprojectl.pc28_lab.draws_14w_partitioned_backup_20250919` AS
-- SELECT * FROM `wprojectl.pc28_lab.draws_14w_partitioned`;

-- 原子替换 (需确认无误后执行)
-- DROP TABLE `wprojectl.pc28_lab.draws_14w_partitioned`;
-- CREATE TABLE `wprojectl.pc28_lab.draws_14w_partitioned` AS
-- SELECT * FROM `wprojectl.pc28_lab.draws_14w_clean`;

-- 6. 重新计算模型准确率基线 (修复后执行)
CREATE OR REPLACE VIEW `wprojectl.pc28_lab.corrected_model_accuracy` AS
WITH prediction_evaluation AS (
  SELECT
    mp.model_id,
    mp.period,
    mp.prediction_big,
    CASE WHEN mp.prediction_big >= 0.5 THEN 'large' ELSE 'small' END as predicted_size,
    dc.size as actual_size,
    CASE WHEN predicted_size = actual_size THEN 1 ELSE 0 END as is_correct
  FROM `wprojectl.pc28.model_predictions` mp
  JOIN `wprojectl.pc28_lab.draws_14w_clean` dc
    ON mp.period = dc.issue
  WHERE DATE(mp.prediction_timestamp, 'Asia/Shanghai') >= DATE_SUB(CURRENT_DATE('Asia/Shanghai'), INTERVAL 7 DAY)
)
SELECT
  model_id,
  COUNT(*) as total_predictions,
  SUM(is_correct) as correct_predictions,
  ROUND(AVG(is_correct), 4) as accuracy_rate,
  -- Wilson置信区间
  ROUND(AVG(is_correct) - 1.96 * SQRT(AVG(is_correct) * (1 - AVG(is_correct)) / COUNT(*)), 4) as accuracy_lower_bound,
  ROUND(AVG(is_correct) + 1.96 * SQRT(AVG(is_correct) * (1 - AVG(is_correct)) / COUNT(*)), 4) as accuracy_upper_bound
FROM prediction_evaluation
GROUP BY model_id
ORDER BY accuracy_rate DESC;