
                CREATE OR REPLACE PROCEDURE `wprojectl.pc28.update_features_daily`()
                BEGIN
                  -- 更新特征表
                  MERGE `wprojectl.pc28.features_daily` T
                  USING (
                    SELECT 
                      DATE(timestamp, 'Asia/Shanghai') as feature_date,
                      COUNT(*) as draw_count,
                      AVG(a + b + c) as avg_sum,
                      COUNTIF((a + b + c) >= 14) / COUNT(*) as big_ratio
                    FROM `wprojectl.pc28.draws_14w_dedup_v`
                    WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
                    GROUP BY feature_date
                  ) S
                  ON T.feature_date = S.feature_date
                  WHEN MATCHED THEN UPDATE SET
                    T.draw_count = S.draw_count,
                    T.avg_sum = S.avg_sum,
                    T.big_ratio = S.big_ratio,
                    T.updated_at = CURRENT_TIMESTAMP()
                  WHEN NOT MATCHED THEN INSERT (
                    feature_date, draw_count, avg_sum, big_ratio, updated_at
                  ) VALUES (
                    S.feature_date, S.draw_count, S.avg_sum, S.big_ratio, CURRENT_TIMESTAMP()
                  );
                END
                