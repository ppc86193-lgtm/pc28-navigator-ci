-- ======================================================================
-- 自动优选视图：优先真实；缺口时用 fallback_simple
-- ======================================================================
CREATE OR REPLACE VIEW `wprojectl.pc28_lab.signal_pool_auto_v2` AS
WITH
-- 限定"近 12 小时"的真实信号，降扫描成本
recent_real AS (
  SELECT
    id,
    ts_utc,
    CAST(period AS STRING) AS period,
    market,
    pick,
    SAFE_CAST(p_win AS FLOAT64)      AS p_win,
    source,
    SAFE_CAST(vote_ratio AS FLOAT64) AS vote_ratio
  FROM `wprojectl.pc28_lab.signal_pool_union_v2`
  WHERE ts_utc >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 12 HOUR)
),
-- 每 period+market 取最新一条真实记录
real_top AS (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY period, market ORDER BY ts_utc DESC) AS rk
  FROM recent_real
),
-- 历史开奖基线（用于给 fallback 推导 p_win）
hist AS (
  SELECT
    AVG(CASE WHEN MOD(CAST(a+b+c AS INT64), 2) = 1 THEN 1 ELSE 0 END) AS p_odd,
    AVG(CASE WHEN CAST(a+b+c AS INT64) >= 14 THEN 1 ELSE 0 END)       AS p_big
  FROM `wprojectl.pc28.draws_14w_dedup_v`
  WHERE DATE(TIMESTAMP(timestamp), 'Asia/Shanghai')
        >= DATE_SUB(CURRENT_DATE('Asia/Shanghai'), INTERVAL 14 DAY)
),
-- 保底原始行（未来窗口）
fb_base AS (
  SELECT period, timestamp AS ts_utc, market, pick
  FROM `wprojectl.pc28_lab.signal_pool_fallback_today`
  WHERE timestamp >= CURRENT_TIMESTAMP()
),
-- 将保底行标准化为 union_v2 口径
fb_rows AS (
  SELECT
    CONCAT('fb_', b.period, '_', b.market) AS id,
    b.ts_utc,
    b.period,
    b.market,
    b.pick,
    CASE
      WHEN b.market = 'oe' AND b.pick = 'odd'  THEN (SELECT p_odd FROM hist)
      WHEN b.market = 'oe' AND b.pick = 'even' THEN 1.0 - (SELECT p_odd FROM hist)
      WHEN b.market = 'size' AND b.pick = 'big'   THEN (SELECT p_big FROM hist)
      WHEN b.market = 'size' AND b.pick = 'small' THEN 1.0 - (SELECT p_big FROM hist)
      ELSE NULL
    END AS p_win,
    'fallback_simple' AS source,
    CAST(NULL AS FLOAT64) AS vote_ratio
  FROM fb_base b
),
-- 仅在真实缺席的 period+market 上才启用保底
fallback_take AS (
  SELECT f.*
  FROM fb_rows f
  WHERE NOT EXISTS (
    SELECT 1
    FROM real_top r
    WHERE r.rk = 1 AND r.period = f.period AND r.market = f.market
  )
)
-- 合并输出：真实（Top-1） + 缺口处的保底
SELECT id, ts_utc, period, market, pick, p_win, source, vote_ratio
FROM (
  SELECT id, ts_utc, period, market, pick, p_win, source, vote_ratio
  FROM real_top
  WHERE rk = 1
  UNION ALL
  SELECT id, ts_utc, period, market, pick, p_win, source, vote_ratio
  FROM fallback_take
);