
                CREATE OR REPLACE PROCEDURE `wprojectl.pc28.update_predictions_hourly`()
                BEGIN
                  -- 更新预测表
                  INSERT INTO `wprojectl.pc28.predictions_log` (
                    prediction_time,
                    model_version,
                    prediction_data,
                    created_at
                  )
                  SELECT
                    CURRENT_TIMESTAMP() as prediction_time,
                    'v1.0' as model_version,
                    TO_JSON_STRING(STRUCT(
                      RAND() * 0.4 + 0.3 as big_prob,
                      RAND() * 0.4 + 0.3 as small_prob
                    )) as prediction_data,
                    CURRENT_TIMESTAMP() as created_at;
                END
                