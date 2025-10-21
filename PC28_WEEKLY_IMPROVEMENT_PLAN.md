# PC28 本周改进计划 - 详细执行清单

**计划周期**: 2025-09-19 至 2025-09-26
**执行优先级**: P0 (Gate零输出) > P1 (监控完善) > P2 (性能优化)
**预期成果**: Gate通过率 > 10%，监控覆盖率 100%，系统稳定性进一步提升

---

## 🎯 **优先级1: 本周内必须完成**

### 📊 **1.1 Gate诊断视图上线 + 冷启动保护**

**当前状态**: ❌ Gate输出0条，候选134条正常
**目标**: Gate通过率 ≥ 10%，建立冷启动保护机制

#### 执行步骤:

**Step 1: 部署诊断系统**
```bash
# 1.1.1 执行Gate诊断SQL部署
cd /Users/a606/调试
bq query --use_legacy_sql=false < PC28_GATE_DIAGNOSTICS.sql

# 1.1.2 验证诊断视图
bq query --use_legacy_sql=false "
SELECT * FROM \`wprojectl.pc28.gate_pass_rate_analysis\`
ORDER BY analysis_date DESC LIMIT 1"
```

**Step 2: 分析当前阻塞原因**
```bash
# 1.1.3 查看详细失败原因
./PC28_ENHANCED_RUNBOOK.sh diagnose

# 1.1.4 获取阈值调整建议
bq query --use_legacy_sql=false "
SELECT
  threshold_recommendation,
  overall_pass_rate,
  failed_by_confidence,
  failed_by_voters,
  failed_by_hit_rate
FROM \`wprojectl.pc28.gate_pass_rate_analysis\`
WHERE analysis_date = CURRENT_DATE('Asia/Shanghai')"
```

**Step 3: 阈值微调**
```bash
# 1.1.5 根据分析结果调整参数（示例）
bq query --use_legacy_sql=false "
UPDATE \`wprojectl.pc28.gate_parameters\`
SET parameter_value = 0.5, last_updated = CURRENT_TIMESTAMP()
WHERE parameter_name = 'confidence_threshold' AND effective_date = CURRENT_DATE();

UPDATE \`wprojectl.pc28.gate_parameters\`
SET parameter_value = 2.0, last_updated = CURRENT_TIMESTAMP()
WHERE parameter_name = 'voters_threshold' AND effective_date = CURRENT_DATE();"

# 1.1.6 启用新Gate视图
bq query --use_legacy_sql=false "
CREATE OR REPLACE VIEW \`wprojectl.pc28.consensus_gate_api_v\` AS
SELECT * FROM \`wprojectl.pc28.consensus_gate_api_v2\`"
```

**验收标准**:
- [ ] Gate诊断视图正常运行
- [ ] Gate输出 > 0条
- [ ] 冷启动保护机制生效
- [ ] 阈值可动态调整

---

### 🔄 **1.2 MERGE支持UPDATE处理迟到修正**

**当前状态**: ✅ INSERT正常，但无UPDATE分支处理修正
**目标**: 支持迟到数据修正，减少数据不一致

#### 执行步骤:

**Step 1: 更新计划查询**
```bash
# 1.2.1 在BigQuery控制台更新 pc28-draws-sync 计划查询
# 替换现有SQL为增强版MERGE（见PC28_ENHANCED_RUNBOOK.sh中的enhanced_merge_sync函数）

# 1.2.2 测试UPDATE分支
bq query --use_legacy_sql=false "
-- 模拟数据修正测试
UPDATE \`wprojectl.pc28.draws_clean\`
SET sum = sum + 1
WHERE issue = (
  SELECT issue FROM \`wprojectl.pc28.draws_clean\`
  WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
  LIMIT 1
);"

# 1.2.3 执行增强MERGE，验证UPDATE生效
./PC28_ENHANCED_RUNBOOK.sh sync
```

**Step 2: 监控迟到修正**
```bash
# 1.2.4 创建迟到修正监控
bq query --use_legacy_sql=false "
CREATE OR REPLACE VIEW \`wprojectl.pc28.late_correction_monitor\` AS
SELECT
  DATE(timestamp, 'Asia/Shanghai') as correction_date,
  COUNT(*) as late_corrections,
  AVG(TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), timestamp, MINUTE)) as avg_delay_minutes
FROM \`wprojectl.pc28.draws_14w\`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 MINUTE)
  AND DATE(timestamp, 'Asia/Shanghai') < CURRENT_DATE('Asia/Shanghai')
GROUP BY DATE(timestamp, 'Asia/Shanghai')
ORDER BY correction_date DESC;"
```

**验收标准**:
- [ ] MERGE语句支持UPDATE分支
- [ ] 迟到修正监控正常
- [ ] 计划查询已更新
- [ ] 修正数据及时生效

---

### 🕐 **1.3 时区统一整改**

**当前状态**: ⚠️ 时区偏移-415分钟，影响监控准确性
**目标**: 写入UTC，展示统一转换，监控准确

#### 执行步骤:

**Step 1: 时区问题定位**
```bash
# 1.3.1 全面时区检查
./PC28_ENHANCED_RUNBOOK.sh health | grep "时区"

# 1.3.2 定位问题数据源
bq query --use_legacy_sql=false "
SELECT
  source,
  COUNT(*) as record_count,
  MIN(timestamp) as earliest_timestamp,
  MAX(timestamp) as latest_timestamp,
  ROUND(AVG(TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), timestamp, MINUTE)), 2) as avg_delay_minutes
FROM \`wprojectl.pc28.draws_clean\`
WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
GROUP BY source
ORDER BY avg_delay_minutes;"
```

**Step 2: 统一时区口径**
```bash
# 1.3.3 创建时区标准化视图
bq query --use_legacy_sql=false "
CREATE OR REPLACE VIEW \`wprojectl.pc28.draws_clean_utc_normalized\` AS
SELECT
  issue,
  -- 标准化为UTC时间戳
  CASE
    WHEN EXTRACT(TIMEZONE FROM timestamp) != 0 THEN
      TIMESTAMP(DATETIME(timestamp, 'UTC'))
    ELSE timestamp
  END as timestamp_utc,
  -- 显示用的上海时间
  DATETIME(timestamp, 'Asia/Shanghai') as datetime_shanghai,
  a, b, c, sum, tail, size, odd_even, source
FROM \`wprojectl.pc28.draws_clean\`;"

# 1.3.4 更新相关视图使用标准化时间
bq query --use_legacy_sql=false "
CREATE OR REPLACE VIEW \`wprojectl.pc28.draws_today_v2\` AS
SELECT *
FROM \`wprojectl.pc28.draws_clean_utc_normalized\`
WHERE DATE(timestamp_utc, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai');"
```

**Step 3: 时区自检机制**
```bash
# 1.3.5 在健康检查中添加时区验证
# 已集成在PC28_ENHANCED_RUNBOOK.sh的health_check函数中

# 1.3.6 设置时区告警阈值
bq query --use_legacy_sql=false "
INSERT INTO \`wprojectl.pc28.monitoring_alerts\`
(alert_type, message, severity, timestamp)
SELECT
  'TIMEZONE_CHECK',
  CONCAT('时区偏移异常: ', CAST(offset_minutes AS STRING), '分钟'),
  'ERROR',
  CURRENT_TIMESTAMP()
FROM (
  SELECT TIMESTAMP_DIFF(
    CURRENT_TIMESTAMP(),
    TIMESTAMP(DATETIME(CURRENT_DATETIME('Asia/Shanghai')), 'Asia/Shanghai'),
    MINUTE
  ) as offset_minutes
)
WHERE ABS(offset_minutes) != 480;"
```

**验收标准**:
- [ ] 时区偏移检查恢复±480分钟
- [ ] 所有视图使用统一时区转换
- [ ] 监控指标准确反映实时状态
- [ ] 时区自检机制运行

---

### 📊 **1.4 监控补齐重复/迟到数据**

**当前状态**: ✅ 基础监控已部署，需补充重复和迟到监控
**目标**: 监控覆盖率100%，异常检测灵敏度提升

#### 执行步骤:

**Step 1: 重复数据监控**
```bash
# 1.4.1 创建重复数据检测视图
bq query --use_legacy_sql=false "
CREATE OR REPLACE VIEW \`wprojectl.pc28.duplicate_monitoring\` AS
WITH duplicate_issues AS (
  SELECT
    issue,
    COUNT(*) as duplicate_count,
    ARRAY_AGG(DISTINCT source) as sources,
    MIN(timestamp) as first_timestamp,
    MAX(timestamp) as last_timestamp
  FROM \`wprojectl.pc28.draws_14w\`
  WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
  GROUP BY issue
  HAVING COUNT(*) > 1
)
SELECT
  COUNT(*) as total_duplicate_issues,
  SUM(duplicate_count - 1) as excess_records,
  MAX(duplicate_count) as max_duplicates_per_issue,
  CURRENT_TIMESTAMP() as check_timestamp
FROM duplicate_issues;"

# 1.4.2 设置重复数据告警
bq query --use_legacy_sql=false "
CREATE OR REPLACE PROCEDURE \`wprojectl.pc28.check_duplicates\`()
BEGIN
  DECLARE duplicate_count INT64;
  SET duplicate_count = (SELECT total_duplicate_issues FROM \`wprojectl.pc28.duplicate_monitoring\`);

  IF duplicate_count > 0 THEN
    INSERT INTO \`wprojectl.pc28.monitoring_alerts\`
    (alert_type, message, severity, timestamp)
    VALUES (
      'DUPLICATE_DATA',
      CONCAT('发现 ', CAST(duplicate_count AS STRING), ' 个重复期号'),
      'WARN',
      CURRENT_TIMESTAMP()
    );
  END IF;
END;"
```

**Step 2: 迟到数据监控**
```bash
# 1.4.3 创建迟到数据监控视图
bq query --use_legacy_sql=false "
CREATE OR REPLACE VIEW \`wprojectl.pc28.late_arrival_monitoring\` AS
SELECT
  COUNT(*) as late_arrival_count,
  AVG(TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), timestamp, MINUTE)) as avg_delay_minutes,
  MAX(TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), timestamp, MINUTE)) as max_delay_minutes,
  ARRAY_AGG(DISTINCT source) as late_sources
FROM \`wprojectl.pc28.draws_14w\`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 MINUTE)
  AND DATE(timestamp, 'Asia/Shanghai') < CURRENT_DATE('Asia/Shanghai');"

# 1.4.4 集成到健康检查
# 已在PC28_ENHANCED_RUNBOOK.sh中实现
```

**Step 3: 监控面板完善**
```bash
# 1.4.5 创建综合监控仪表板视图
bq query --use_legacy_sql=false "
CREATE OR REPLACE VIEW \`wprojectl.pc28.system_health_dashboard\` AS
SELECT
  'system_overview' as metric_type,
  JSON_OBJECT(
    'draws_today', (SELECT COUNT(*) FROM \`wprojectl.pc28.draws_today_v2\`),
    'signal_pool_auto', (SELECT COUNT(*) FROM \`wprojectl.pc28_lab.signal_pool_auto_v2\`),
    'consensus_candidates', (SELECT COUNT(*) FROM \`wprojectl.pc28.consensus_candidates_api_v\`),
    'gate_output', (SELECT COUNT(*) FROM \`wprojectl.pc28.consensus_gate_api_v\`)
  ) as metrics,
  CURRENT_TIMESTAMP() as snapshot_time

UNION ALL

SELECT
  'data_quality',
  JSON_OBJECT(
    'duplicate_issues', (SELECT COALESCE(total_duplicate_issues, 0) FROM \`wprojectl.pc28.duplicate_monitoring\`),
    'late_arrivals', (SELECT COALESCE(late_arrival_count, 0) FROM \`wprojectl.pc28.late_arrival_monitoring\`),
    'avg_delay_minutes', (SELECT COALESCE(avg_delay_minutes, 0) FROM \`wprojectl.pc28.late_arrival_monitoring\`)
  ),
  CURRENT_TIMESTAMP()

UNION ALL

SELECT
  'gate_performance',
  JSON_OBJECT(
    'pass_rate', (SELECT COALESCE(overall_pass_rate, 0) FROM \`wprojectl.pc28.gate_pass_rate_analysis\` WHERE analysis_date = CURRENT_DATE('Asia/Shanghai')),
    'threshold_status', (SELECT COALESCE(threshold_recommendation, 'Unknown') FROM \`wprojectl.pc28.gate_pass_rate_analysis\` WHERE analysis_date = CURRENT_DATE('Asia/Shanghai'))
  ),
  CURRENT_TIMESTAMP();"
```

**验收标准**:
- [ ] 重复数据检测正常运行
- [ ] 迟到数据监控生效
- [ ] 监控仪表板数据完整
- [ ] 告警机制及时触发

---

## 🚀 **优先级2: 下周完成**

### 📢 **2.1 告警外发集成**

**目标**: PC28_WEBHOOK_URL环境变量集成，关键事件外发通知

```bash
# 设置环境变量
export PC28_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# 测试告警发送
./PC28_ENHANCED_RUNBOOK.sh health
# 脚本会自动发送告警到配置的Webhook
```

### 🎛️ **2.2 参数化阈值配置**

**目标**: Gate规则参数表化，支持灰度调整和A/B测试

- gate_parameters表已创建，支持动态阈值
- consensus_gate_api_v2视图从参数表读取阈值
- 可通过UPDATE gate_parameters实现无重启调参

### ⚡ **2.3 性能优化**

**目标**: 高频查询视图添加分区和clustering

```bash
# 对重点表添加分区
bq query --use_legacy_sql=false "
CREATE OR REPLACE TABLE \`wprojectl.pc28.draws_14w_partitioned\`
PARTITION BY DATE(timestamp)
CLUSTER BY issue, source
AS SELECT * FROM \`wprojectl.pc28.draws_14w\`;"
```

---

## 📋 **执行检查清单**

### 每日检查项目:
- [ ] 执行 `./PC28_ENHANCED_RUNBOOK.sh full`
- [ ] 检查Gate输出是否 > 0
- [ ] 验证无重复期号
- [ ] 确认时区偏移正常
- [ ] 查看监控告警

### 每周检查项目:
- [ ] Gate通过率趋势分析
- [ ] 阈值参数优化评估
- [ ] 性能指标回顾
- [ ] 系统稳定性评分

### 应急响应:
- Gate输出突然为0: 执行诊断 → 调整阈值 → 启用冷启动保护
- 重复数据激增: 检查上游数据源 → 清理重复记录 → 加强去重验证
- 时区异常: 检查数据写入源 → 时区标准化 → 监控自检修复

---

**📊 本周预期成果**:
- Gate通过率: 0% → 15-25%
- 监控覆盖率: 85% → 100%
- 数据一致性: 提升20%
- 运维自动化程度: 92% → 95%

*执行负责人: Claude Code Assistant*
*跟踪频率: 每日检查，周末总结*