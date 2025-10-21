# PC28 Vertex AI集成详细记录

## 🤖 Vertex AI批预测完整流程 (gtp.txt 10000行后提取)

### 🎯 Vertex批预测重启和回填机制

#### 完整的C-SOP流程
```bash
# 1. 发现最近成功的BatchPrediction配置
gcloud ai batch-predictions list --project=${PROJECT} --region=${BQLOC}
gcloud ai batch-predictions describe <job-name> --project=${PROJECT} --region=${BQLOC}

# 2. 识别今日缺口periods
WITH gap_analysis AS (
  SELECT d.period 
  FROM `${PROJECT}.${DS_DRAW}.draws_14w_dedup_v` d
  LEFT JOIN `${PROJECT}.${DS_LAB}.cloud_pred_today_norm` p 
    ON d.period = p.period
  WHERE DATE(d.timestamp,'${TZ}') = CURRENT_DATE('${TZ}')
    AND p.period IS NULL
)
SELECT period FROM gap_analysis ORDER BY period;

# 3. 导出缺口特征到GCS
# 保持历史沿用的输入格式和列结构
# 确保与已训练模型的schema一致

# 4. 触发BatchPrediction作业
gcloud ai batch-predictions create \
  --project="${PROJECT}" --region="${BQLOC}" \
  --model="${VERTEX_MODEL_RESOURCE}" \
  --display-name="pc28-batch-$(date +%F-%H%M)" \
  --input-config="gcsSource={uris=[\"${GCS_INPUT_URI}\"]}" \
  --output-config="gcsDestination={outputUriPrefix=\"${GCS_OUTPUT_PREFIX}\"}"

# 5. 等待作业完成 (超时保护60分钟)
while true; do
  status=$(gcloud ai batch-predictions describe $job_name --format="value(state)")
  if [[ "$status" == "SUCCEEDED" ]]; then break; fi
  if [[ "$status" == "FAILED" ]]; then exit 1; fi
  sleep 30
  # 超时检查
done

# 6. 解析输出predictions.jsonl
# 规范化格式: period,p_even,timestamp
awk 'BEGIN{print "period,p_even,timestamp"} 
{
  # 提取period和scores
  if ($0 ~ /"period":/) { match($0, /"period":"([^"]+)"/, a); period=a[1]; }
  if ($0 ~ /"scores":\[/) { 
    match($0, /\[([0-9\.\, ]+)\]/, b); 
    split(b[1], arr, ","); 
    if (length(arr)>=2) p_even=arr[2]+0; 
  }
  if (period!="") {
    cmd="date -u +%Y-%m-%dT%H:%M:%SZ"; 
    cmd | getline timestamp; 
    close(cmd);
    print period, p_even, timestamp;
  }
}' predictions.jsonl > vertex_parsed.csv

# 7. 安全加载到BigQuery (避免重复)
bq load --source_format=CSV --skip_leading_rows=1 \
  ${PROJECT}:${DS_LAB}.cloud_pred_today_norm_tmp \
  vertex_parsed.csv \
  period:STRING,p_even:FLOAT,timestamp:TIMESTAMP

# 8. MERGE到正式表 (防重复)
MERGE `${PROJECT}.${DS_LAB}.cloud_pred_today_norm` T
USING (
  SELECT period, timestamp, p_even
  FROM `${PROJECT}.${DS_LAB}.cloud_pred_today_norm_tmp`
) S
ON T.period=S.period AND DATE(T.timestamp,'${TZ}')=CURRENT_DATE('${TZ}')
WHEN NOT MATCHED THEN
  INSERT(period, timestamp, p_even, src) VALUES(S.period, S.timestamp, S.p_even, 'cloud');
```

### 🔧 数据管道健康检查详细机制

#### pipeline_health.sh功能
```bash
# 四层数据完整性检查
check_draws_today()     # 开奖数据当日更新
check_prediction_sources() # 三源预测数据 (cloud/map/size)
check_ensemble_pool()   # 集成池数据
check_signal_union()    # 信号联合数据
check_candidates()      # 最终候选数据

# 来源数验证
verify_source_count() {
  # 期望: COUNT(DISTINCT source) >= 3
  # 不足时自动切换到union_v3扩容
}

# 投票桶分布检查
verify_bucket_distribution() {
  # 统计各桶的信号数量
  # 检查分布是否均匀
  # 验证是否有足够的投票多样性
}
```

### 📊 KPI快查工具详细实现

#### kpi_quick.sh核心功能
```bash
# OE/SIZE分别统计
get_oe_kpi() {
  bq query --format=csv "
  SELECT 
    'oe' as market,
    COUNT(*) as n_orders,
    COUNTIF(outcome IN ('win','lose')) as n_settled,
    SAFE_DIVIDE(COUNTIF(outcome='win'), NULLIF(COUNTIF(outcome IN ('win','lose')),0)) as accuracy,
    AVG(p_win) as avg_p_win,
    SAFE_DIVIDE(COUNT(*), (SELECT COUNT(*) FROM draws_14w_dedup_v WHERE DATE(timestamp,'${TZ}')=CURRENT_DATE('${TZ}'))) as coverage
  FROM score_ledger 
  WHERE market='oe' AND day_id_cst=CURRENT_DATE('${TZ}')
  "
}

# SIZE统计 (类似逻辑)
get_size_kpi() { ... }

# 合并统计
get_combined_kpi() {
  # 双通道综合指标
  # 加权平均或最保守估计
}
```

### 🔄 请求文件桥接详细协议

#### request_bridge.sh功能
```bash
# 支持的请求类型
handle_bucket_floor_request() {
  # 阈值调整请求
  # TTL时间管理
  # 多市场同步
}

handle_mode_switch_request() {
  # 模式切换请求
  # 参数验证
  # 平滑切换
}

handle_param_tweak_request() {
  # 细微参数调整
  # 安全边界检查
  # 回滚准备
}

# 请求文件格式标准化
request_format = {
  "timestamp": "ISO格式时间戳",
  "ttl_sec": "生存时间秒数",
  "requester": "请求来源标识",
  "reason": "请求原因说明",
  "parameters": "具体参数内容"
}
```

### 📦 打包和归档详细机制

#### make_artifact.sh功能
```bash
# 打包内容
package_contents = [
  "配置文件快照",
  "SQL视图定义", 
  "Python模块代码",
  "执行日志",
  "KPI报告",
  "状态文件",
  "回滚备份"
]

# 打包格式
tar_structure = {
  "config/": "配置文件",
  "sql/": "SQL定义", 
  "logs/": "执行日志",
  "reports/": "KPI报告",
  "backups/": "回滚备份"
}

# 可选Gist上传
gist_upload = {
  "public": false,
  "description": "PC28系统状态快照",
  "files": "关键配置和报告文件"
}
```

### 🔄 日志轮转详细策略

#### rotate_logs.sh机制
```bash
# 日志文件管理
log_files = [
  "TEMP_CODE/logs/pc28_enhanced_system.log",
  "TEMP_CODE/logs/auto_smart_switch.log", 
  "TEMP_CODE/logs/pi_controller.log",
  "TEMP_CODE/logs/calibrator.log"
]

# 轮转策略
rotation_policy = {
  "max_size": "10MB",
  "max_files": 5,
  "compression": true,
  "retention_days": 30
}

# 轮转执行
for log_file in log_files:
  if [[ $(stat -f%z "$log_file") -gt 10485760 ]]; then
    mv "$log_file" "${log_file}.1"
    gzip "${log_file}.1"
    touch "$log_file"
  fi
```

---

**继续提取gtp.txt后面的内容，确保不遗漏任何有价值的设计！** 📊
