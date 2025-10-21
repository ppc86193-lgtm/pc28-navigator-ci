CREATE OR REPLACE PROCEDURE `wprojectl.pc28_lab.sp_fill_fallback_today_merge`(
  HORIZON       INT64,
  LOOKBACK_DAYS INT64,
  FREQ_SECONDS  INT64
)
BEGIN
  -- 创建临时表存储要插入的数据
  EXECUTE IMMEDIATE CONCAT('''
  CREATE TEMP TABLE temp_to_write AS
  WITH expected_from_draws AS (
    SELECT CAST(period AS STRING) AS period, timestamp
    FROM `wprojectl.pc28_lab.draws_today_v2`
    WHERE timestamp >= CURRENT_TIMESTAMP()
    LIMIT ''', CAST(HORIZON AS STRING), '''
  ),
  expected_from_clock AS (
    SELECT
      CONCAT(FORMAT_DATE('%Y%m%d', CURRENT_DATE('Asia/Shanghai')), '_', LPAD(CAST(n AS STRING), 4, '0')) AS period,
      TIMESTAMP_ADD(TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MINUTE), INTERVAL n * ''', CAST(FREQ_SECONDS AS STRING), ''' SECOND) AS timestamp
    FROM UNNEST(GENERATE_ARRAY(1, ''', CAST(HORIZON AS STRING), ''')) AS n
  ),
  expected AS (
    SELECT * FROM expected_from_draws
    UNION ALL
    SELECT * FROM expected_from_clock
    WHERE NOT EXISTS (SELECT 1 FROM expected_from_draws)
  ),
  real_has AS (
    SELECT DISTINCT CAST(period AS STRING) AS period
    FROM `wprojectl.pc28_lab.signal_pool_union_v2`
    WHERE ts_utc >= (SELECT MIN(timestamp) FROM expected)
  ),
  need_fill AS (
    SELECT e.*
    FROM expected e
    LEFT JOIN real_has r USING (period)
    WHERE r.period IS NULL
  ),
  hist AS (
    SELECT
      AVG(CASE WHEN MOD(CAST(a+b+c AS INT64), 2) = 1 THEN 1 ELSE 0 END) AS p_odd,
      AVG(CASE WHEN CAST(a+b+c AS INT64) >= 14 THEN 1 ELSE 0 END) AS p_big
    FROM `wprojectl.pc28.draws_14w_dedup_v`
    WHERE DATE(TIMESTAMP(timestamp), 'Asia/Shanghai') >= DATE_SUB(CURRENT_DATE('Asia/Shanghai'), INTERVAL ''', CAST(LOOKBACK_DAYS AS STRING), ''' DAY)
  ),
  to_write_oe AS (
    SELECT
      n.period,
      n.timestamp,
      'oe' AS market,
      (CASE WHEN (SELECT p_odd FROM hist) >= 0.5 THEN 'odd' ELSE 'even' END) AS pick,
      (CASE WHEN (SELECT p_odd FROM hist) >= 0.5 THEN (SELECT p_odd FROM hist) ELSE 1.0 - (SELECT p_odd FROM hist) END) AS p_win,
      'fallback_simple' AS source
    FROM need_fill n
  ),
  to_write_size AS (
    SELECT
      n.period,
      n.timestamp,
      'size' AS market,
      (CASE WHEN (SELECT p_big FROM hist) >= 0.5 THEN 'big' ELSE 'small' END) AS pick,
      (CASE WHEN (SELECT p_big FROM hist) >= 0.5 THEN (SELECT p_big FROM hist) ELSE 1.0 - (SELECT p_big FROM hist) END) AS p_win,
      'fallback_simple' AS source
    FROM need_fill n
  )
  SELECT * FROM to_write_oe
  UNION ALL
  SELECT * FROM to_write_size
  ''');

  -- 插入数据（去重）
  INSERT INTO `wprojectl.pc28_lab.signal_pool_fallback_today` (period, timestamp, market, pick, p_win, source)
  SELECT period, timestamp, market, pick, p_win, source
  FROM temp_to_write
  WHERE NOT EXISTS (
    SELECT 1 FROM `wprojectl.pc28_lab.signal_pool_fallback_today` f
    WHERE f.period = temp_to_write.period
      AND f.market = temp_to_write.market
      AND f.source = temp_to_write.source
  );

END;
