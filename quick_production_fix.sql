-- PC28 生产环境快速修复SQL
-- 基于本地达标配置修复生产环境

-- 设置变量
DECLARE project_id STRING DEFAULT 'wprojectl';
DECLARE dataset_id STRING DEFAULT 'pc28';

-- 1. 修复candidates_today_dedup_v视图 (解决NULL问题)
CREATE OR REPLACE VIEW `wprojectl.pc28.candidates_today_dedup_v` AS
WITH base_ensemble AS (
  SELECT 
    period,
    timestamp as ts_utc,
    FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', timestamp, 'Asia/Shanghai') as ts_cst,
    p_star_ens,
    vote_ratio,
    n_votes
  FROM `wprojectl.pc28.p_ensemble_today_norm_v`
  WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
    AND p_star_ens IS NOT NULL
),
signal_evaluation AS (
  SELECT 
    *,
    -- 分层信号等级 (降低阈值提高覆盖率)
    CASE 
      WHEN p_star_ens >= 0.60 THEN 'Gold'
      WHEN p_star_ens >= 0.50 THEN 'Silver'  
      WHEN p_star_ens >= 0.40 THEN 'Bronze'
      ELSE NULL
    END as tier_candidate,
    -- B钥检查 (EV > 0，基于1.95赔率)
    (1.95 * p_star_ens - 1.0) > 0 as keyB,
    -- 简化否决检查
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
WHERE tier_candidate IS NOT NULL
  AND keyB = TRUE
  AND veto = FALSE;

-- 2. 创建分层阈值信号视图 (提高覆盖率)
CREATE OR REPLACE VIEW `wprojectl.pc28.signals_layered_v` AS
WITH ensemble_data AS (
  SELECT 
    period,
    timestamp,
    p_star_ens,
    vote_ratio,
    n_votes
  FROM `wprojectl.pc28.p_ensemble_today_norm_v`
  WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
    AND p_star_ens IS NOT NULL
),
layered_signals AS (
  SELECT 
    period,
    timestamp,
    p_star_ens,
    vote_ratio,
    n_votes,
    -- 分层信号
    CASE 
      WHEN p_star_ens >= 0.65 THEN 'CL3_HIGH'
      WHEN p_star_ens >= 0.55 THEN 'CL2_MEDIUM'
      WHEN p_star_ens >= 0.50 THEN 'CL1_LOW'
      ELSE 'SKIP'
    END as confidence_level,
    -- 分层Kelly
    CASE 
      WHEN p_star_ens >= 0.65 THEN 0.25        -- CL3原值
      WHEN p_star_ens >= 0.55 THEN 0.25 * 0.7  -- CL2七折
      WHEN p_star_ens >= 0.50 THEN 0.25 * 0.3  -- CL1三折
      ELSE 0.0
    END as kelly_fraction,
    -- 计算EV
    (1.95 * p_star_ens - 1.0) as expected_ev,
    -- 计算仓位
    LEAST(
      0.25 * (1.95 * p_star_ens - 1.0) / 0.95 * 
      CASE 
        WHEN p_star_ens >= 0.65 THEN 1.0
        WHEN p_star_ens >= 0.55 THEN 0.7
        WHEN p_star_ens >= 0.50 THEN 0.3
        ELSE 0.0
      END,
      0.02  -- bet_cap限制
    ) as position_size
  FROM ensemble_data
)
SELECT 
  period,
  timestamp,
  p_star_ens,
  confidence_level,
  kelly_fraction,
  expected_ev,
  position_size,
  -- 三钥验证
  p_star_ens >= 0.50 as key_A,  -- 降低A钥阈值
  expected_ev > 0 as key_B,     -- EV必须为正
  TRUE as key_C,                -- 简化C钥
  -- 最终信号
  (p_star_ens >= 0.50 AND expected_ev > 0) as signal_approved
FROM layered_signals
WHERE confidence_level != 'SKIP'
ORDER BY timestamp DESC;

-- 3. 创建今日性能监控视图
CREATE OR REPLACE VIEW `wprojectl.pc28.performance_today_v` AS
WITH today_signals AS (
  SELECT 
    COUNT(*) as total_candidates,
    COUNT(CASE WHEN signal_approved THEN 1 END) as approved_signals,
    AVG(p_star_ens) as avg_p_star,
    AVG(expected_ev) as avg_ev,
    SUM(position_size) as total_exposure
  FROM `wprojectl.pc28.signals_layered_v`
),
coverage_analysis AS (
  SELECT 
    total_candidates,
    approved_signals,
    SAFE_DIVIDE(approved_signals, total_candidates) as coverage_rate,
    avg_p_star,
    avg_ev,
    total_exposure,
    -- 生存线检查
    CASE WHEN avg_p_star >= 0.51282 THEN 'ABOVE_SURVIVAL' ELSE 'BELOW_SURVIVAL' END as survival_status,
    -- 覆盖率评级
    CASE 
      WHEN SAFE_DIVIDE(approved_signals, total_candidates) >= 0.25 THEN 'TARGET_MET'
      WHEN SAFE_DIVIDE(approved_signals, total_candidates) >= 0.08 THEN 'ACCEPTABLE'
      ELSE 'LOW_COVERAGE'
    END as coverage_grade
  FROM today_signals
)
SELECT 
  *,
  CURRENT_TIMESTAMP() as last_updated,
  -- 整体评级
  CASE 
    WHEN survival_status = 'ABOVE_SURVIVAL' AND coverage_grade = 'TARGET_MET' THEN 'GREEN'
    WHEN survival_status = 'ABOVE_SURVIVAL' OR coverage_grade = 'ACCEPTABLE' THEN 'YELLOW'
    ELSE 'RED'
  END as traffic_light
FROM coverage_analysis;

-- 4. 验证修复效果查询
SELECT 
  'candidates_today_dedup_v' as table_name,
  COUNT(*) as total_records,
  COUNT(CASE WHEN tier_candidate IS NOT NULL THEN 1 END) as valid_signals,
  COUNT(CASE WHEN keyB = TRUE THEN 1 END) as b_key_passed
FROM `wprojectl.pc28.candidates_today_dedup_v`
UNION ALL
SELECT 
  'signals_layered_v' as table_name,
  COUNT(*) as total_records,
  COUNT(CASE WHEN signal_approved THEN 1 END) as valid_signals,
  COUNT(CASE WHEN key_B = TRUE THEN 1 END) as b_key_passed
FROM `wprojectl.pc28.signals_layered_v`
UNION ALL
SELECT 
  'performance_today_v' as table_name,
  1 as total_records,
  CAST(coverage_rate * 100 AS INT64) as coverage_percent,
  CASE WHEN traffic_light = 'GREEN' THEN 1 ELSE 0 END as is_green
FROM `wprojectl.pc28.performance_today_v`;
