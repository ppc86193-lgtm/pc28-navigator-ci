CREATE OR REPLACE PROCEDURE `wprojectl.pc28_lab.sp_fill_fallback_today_merge`(
  HORIZON       INT64,   -- 例如 20
  LOOKBACK_DAYS INT64,   -- 例如 14
  FREQ_SECONDS  INT64    -- 例如 60
)
BEGIN
  -- 把需要引号的常量做成变量，通过 USING 绑定，彻底回避转义
  DECLARE fmt STRING DEFAULT '%Y%m%d';
  DECLARE tz  STRING DEFAULT 'Asia/Shanghai';

  EXECUTE IMMEDIATE '''
  -- 1) 今日未来期：有真实开奖时间就优先用它
  WITH expected_from_draws AS (
    SELECT CAST(period AS STRING) AS period, timestamp
    FROM `wprojectl.pc28_lab.draws_today_v2`
    WHERE timestamp >= CURRENT_TIMESTAMP()
    LIMIT ?
  ),

  -- 2) 当今日未来期为空时，按时钟兜底生成 HORIZON 条
  expected_from_clock AS (
    SELECT
      CONCAT(FORMAT_DATE(@fmt, CURRENT_DATE(@tz)), '_', LPAD(CAST(n AS STRING), 4, '0')) AS period,
      TIMESTAMP_ADD(
        TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MINUTE),
        INTERVAL n * @freq_seconds SECOND
      ) AS timestamp
    FROM UNNEST(GENERATE_ARRAY(1, @horizon)) AS n
  ),

  -- 3) 优先用真实 draws；没有则用时钟兜底
  expected AS (
    SELECT * FROM expected_from_draws
    UNION ALL
    SELECT * FROM expected_from_clock
    WHERE NOT EXISTS (SELECT 1 FROM expected_from_draws)
  ),

  -- 4) 检查哪些期号已有真实信号
  real_has AS (
    SELECT DISTINCT CAST(period AS STRING) AS period
    FROM `wprojectl.pc28_lab.signal_pool_union_v2`
    WHERE ts_utc >= (SELECT MIN(timestamp) FROM expected)
  ),

  -- 5) 需要保底填充的期号
  need_fill AS (
    SELECT e.*
    FROM expected e
    LEFT JOIN real_has r USING (period)
    WHERE r.period IS NULL
  ),

  -- 6) 历史统计（近 @lookback_days 天开奖）→ 奇偶/大小基线
  hist AS (
    SELECT
      AVG(CASE WHEN MOD(CAST(a+b+c AS INT64), 2) = 1 THEN 1 ELSE 0 END) AS p_odd,
      AVG(CASE WHEN CAST(a+b+c AS INT64) >= 14 THEN 1 ELSE 0 END)       AS p_big
    FROM `wprojectl.pc28.draws_14w_dedup_v`
    WHERE DATE(TIMESTAMP(timestamp), @tz) >= DATE_SUB(CURRENT_DATE(@tz), INTERVAL @lookback_days DAY)
  ),

  -- 7) 生成 oe 和 size 两个 market 的保底记录
  to_write_oe AS (
    SELECT
      n.period,
      n.timestamp,
      'oe' AS market,
      (CASE WHEN (SELECT p_odd FROM hist) >= 0.5 THEN 'odd' ELSE 'even' END) AS pick,
      (CASE WHEN (SELECT p_odd FROM hist) >= 0.5
            THEN (SELECT p_odd FROM hist)
            ELSE 1.0 - (SELECT p_odd FROM hist) END) AS p_win,
      'fallback_simple' AS source
    FROM need_fill n
  ),

  to_write_size AS (
    SELECT
      n.period,
      n.timestamp,
      'size' AS market,
      (CASE WHEN (SELECT p_big FROM hist) >= 0.5 THEN 'big' ELSE 'small' END) AS pick,
      (CASE WHEN (SELECT p_big FROM hist) >= 0.5
            THEN (SELECT p_big FROM hist)
            ELSE 1.0 - (SELECT p_big FROM hist) END) AS p_win,
      'fallback_simple' AS source
    FROM need_fill n
  ),

  to_write AS (
    SELECT * FROM to_write_oe
    UNION ALL
    SELECT * FROM to_write_size
  )

  -- 8) MERGE 进目标表
  MERGE `wprojectl.pc28_lab.signal_pool_fallback_today` T
  USING to_write S
  ON T.period = S.period AND T.market = S.market AND T.source = S.source
  WHEN NOT MATCHED THEN
    INSERT (period, timestamp, market, pick, p_win, source)
    VALUES (S.period, S.timestamp, S.market, S.pick, S.p_win, S.source)
  ''' USING
      HORIZON,
      LOOKBACK_DAYS,
      FREQ_SECONDS,
      fmt,
      tz;
END;
