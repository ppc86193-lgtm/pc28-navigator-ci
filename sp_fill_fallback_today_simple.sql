-- 创建 / 重建：简单版"保底补齐"存储过程（无动态 SQL）
CREATE OR REPLACE PROCEDURE `wprojectl.pc28_lab.sp_fill_fallback_today_simple`(tz STRING)
BEGIN
  DECLARE d DATE DEFAULT CURRENT_DATE(tz);

  -- 1) 今天已存在的 period/market 抽到临时表（只看真实/非保底来源）
  CREATE TEMP TABLE have AS
  SELECT CAST(period AS STRING) AS period, market
  FROM `wprojectl.pc28_lab.signal_pool`
  WHERE DATE(ts_utc, tz) = d
    AND (source NOT LIKE 'fallback%' AND source NOT LIKE 'auto%');

  -- 2) 从"自动视图"抽出保底候选（已包含你定义好的保底逻辑）
  CREATE TEMP TABLE cand AS
  SELECT
    CAST(period AS STRING) AS period,
    market,
    pick,
    p_win,
    ts_utc
  FROM `wprojectl.pc28_lab.signal_pool_auto_v2`
  WHERE DATE(ts_utc, tz) = d
    AND (source LIKE 'fallback%' OR source LIKE 'auto%');

  -- 3) 只补"缺口"：左连接反选（不读 target 表）
  INSERT INTO `wprojectl.pc28_lab.signal_pool`
    (id, ts_utc, period, market, pick, p_win, source, vote_ratio)
  SELECT
    CONCAT('auto_', c.period, '_', c.market) AS id,
    c.ts_utc,
    c.period,
    c.market,
    c.pick,
    c.p_win,
    'fallback_auto' AS source,
    NULL AS vote_ratio
  FROM cand c
  LEFT JOIN have h
  USING (period, market)
  WHERE h.period IS NULL;  -- 只补尚未存在的 period+market
END;