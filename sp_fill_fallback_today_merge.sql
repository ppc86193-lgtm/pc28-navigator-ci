-- ======================================================================
-- 保底写入（MERGE 版）：sp_fill_fallback_today_merge
-- 参数：
--   HORIZON        未来需要覆盖的期数（优先读 draws_today_v2；若未来为空则按时钟兜底）
--   LOOKBACK_DAYS  统计历史众数/均值的回看天数（用于保底模板）
--   FREQ_SECONDS   当未来期号缺失时，用此秒级间隔按时钟生成占位 period
-- ======================================================================
CREATE OR REPLACE PROCEDURE `wprojectl.pc28_lab.sp_fill_fallback_today_merge`(
  HORIZON INT64,
  LOOKBACK_DAYS INT64,
  FREQ_SECONDS INT64
)
BEGIN
  -- 1) 动态探测 fallback 表可写列（只写表内真实存在的列）
  DECLARE insert_cols STRING;
  DECLARE values_cols STRING;
  DECLARE dyn_sql STRING;

  SET (insert_cols, values_cols) = (
    SELECT AS STRUCT
      STRING_AGG(c ORDER BY ord),
      STRING_AGG('S.' || c ORDER BY ord)
    FROM (
      WITH allowed AS (
        SELECT 'period'     AS c, 1 AS ord UNION ALL
        SELECT 'timestamp', 2 UNION ALL
        SELECT 'market', 3 UNION ALL
        SELECT 'pick', 4 UNION ALL
        SELECT 'p_win', 5 UNION ALL
        SELECT 'source', 6
      ),
      existing AS (
        SELECT LOWER(column_name) AS c
        FROM `wprojectl.pc28_lab`.INFORMATION_SCHEMA.COLUMNS
        WHERE table_name = 'signal_pool_fallback_today'
      )
      SELECT a.c, a.ord
      FROM allowed a
      JOIN existing e USING (c)
      ORDER BY a.ord
    )
  );

  -- 保障最小列集合
  ASSERT insert_cols LIKE 'period,timestamp%' AS
    'signal_pool_fallback_today 至少需要列 period, timestamp';

  -- 2) 组装动态 SQL（@HORIZON/@LOOKBACK_DAYS/@FREQ_SECONDS 为绑定参数）
  SET dyn_sql = '''
    WITH expected_from_draws AS (
      SELECT CAST(period AS STRING) AS period, timestamp
      FROM `wprojectl.pc28_lab.draws_today_v2`
      WHERE timestamp >= CURRENT_TIMESTAMP()
      ORDER BY timestamp
      LIMIT @HORIZON
    ),
    expected_from_clock AS (
      -- 当 draws_today_v2 未来为空：按时钟兜底
      SELECT
        CONCAT(EXTRACT(YEAR FROM CURRENT_TIMESTAMP()), EXTRACT(MONTH FROM CURRENT_TIMESTAMP()), EXTRACT(DAY FROM CURRENT_TIMESTAMP()), ''_'', CAST(1000 + n AS STRING)) AS period,
        TIMESTAMP_ADD(TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MINUTE), INTERVAL n*@FREQ_SECONDS SECOND) AS timestamp
      FROM UNNEST(GENERATE_ARRAY(1, @HORIZON)) AS n
    ),
    expected AS (
      SELECT * FROM expected_from_draws
      UNION ALL
      SELECT e.* FROM expected_from_clock e
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
    -- 历史统计（近 LOOKBACK_DAYS 天开奖）→ 奇偶/大小基线
    hist AS (
      SELECT
        AVG(CASE WHEN MOD(CAST(a+b+c AS INT64), 2) = 1 THEN 1 ELSE 0 END) AS p_odd,
        AVG(CASE WHEN CAST(a+b+c AS INT64) >= 14 THEN 1 ELSE 0 END)       AS p_big
      FROM `wprojectl.pc28.draws_14w_dedup_v`
      WHERE DATE(TIMESTAMP(timestamp), 'Asia/Shanghai')
            >= DATE_SUB(CURRENT_DATE('Asia/Shanghai'), INTERVAL @LOOKBACK_DAYS DAY)
    ),
    -- 生成 oe 和 size 两个 market 的保底记录
    to_write_oe AS (
      SELECT
        n.period,
        n.timestamp,
        ''oe'' AS market,
        (CASE WHEN (SELECT p_odd FROM hist) >= 0.5 THEN ''odd'' ELSE ''even'' END) AS pick,
        (CASE WHEN (SELECT p_odd FROM hist) >= 0.5
              THEN (SELECT p_odd FROM hist)
              ELSE 1.0 - (SELECT p_odd FROM hist) END) AS p_win,
        ''fallback_simple'' AS source
      FROM need_fill n
      LEFT JOIN `wprojectl.pc28_lab.signal_pool_fallback_today` f
        ON f.period = n.period AND f.market = ''oe'' AND f.source = ''fallback_simple''
      WHERE f.period IS NULL
    ),
    to_write_size AS (
      SELECT
        n.period,
        n.timestamp,
        ''size'' AS market,
        (CASE WHEN (SELECT p_big FROM hist) >= 0.5 THEN ''big'' ELSE ''small'' END) AS pick,
        (CASE WHEN (SELECT p_big FROM hist) >= 0.5
              THEN (SELECT p_big FROM hist)
              ELSE 1.0 - (SELECT p_big FROM hist) END) AS p_win,
        ''fallback_simple'' AS source
      FROM need_fill n
      LEFT JOIN `wprojectl.pc28_lab.signal_pool_fallback_today` f
        ON f.period = n.period AND f.market = ''size'' AND f.source = ''fallback_simple''
      WHERE f.period IS NULL
    ),
    to_write AS (
      SELECT * FROM to_write_oe
      UNION ALL
      SELECT * FROM to_write_size
    )
    MERGE `wprojectl.pc28_lab.signal_pool_fallback_today` T
    USING to_write S
    ON T.period = S.period AND T.market = S.market AND T.source = S.source
    WHEN NOT MATCHED THEN
      INSERT (''' || insert_cols || ''')
      VALUES (''' || values_cols || ''')
  ''';

  -- 执行（绑定参数）
  EXECUTE IMMEDIATE dyn_sql
  USING HORIZON AS HORIZON, LOOKBACK_DAYS AS LOOKBACK_DAYS, FREQ_SECONDS AS FREQ_SECONDS;
END;