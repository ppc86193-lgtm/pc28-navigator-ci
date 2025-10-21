# PC28 下游功能故障报告

## 🚨 执行总结 (2025-09-19 03:40 CST)

### ❌ 关键发现：3个严重功能故障

经过详细测试，下游逻辑中发现 **3个关键功能完全失效**，影响核心预测和API输出。

---

## 🔥 CRITICAL 故障清单

### 1️⃣ `signal_pool_auto_v2` - 预测核心完全失效
**状态**: 🔴 **BROKEN** - 0行数据输出
**影响**: 所有自动预测功能停止工作

**根本原因分析**:
```sql
-- 检查12小时内真实信号
SELECT COUNT(*) FROM `wprojectl.pc28_lab.signal_pool_union_v2`
WHERE ts_utc >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 12 HOUR);
-- 结果: 0 行 (无近期真实信号)

-- 检查未来保底数据
SELECT COUNT(*) FROM `wprojectl.pc28_lab.signal_pool_fallback_today`
WHERE timestamp >= CURRENT_TIMESTAMP();
-- 结果: 0 行 (无未来预测数据)
```

**问题详情**:
- `signal_pool_fallback_today` 最新数据止于 `2025-09-18 12:43:00`
- 12小时窗口限制过严格，最新数据已过期
- 未来时间窗口为空，保底机制无法启动

### 2️⃣ `draws_today_v2` - 今日数据视图失效
**状态**: 🔴 **BROKEN** - 0行今日数据
**影响**: 所有"今日"相关功能和预测失效

**根本原因分析**:
```sql
-- 检查底层数据源
draws_clean (今日): 134 条 ✅ 正常
draws_14w (今日): 0 条 ❌ 缺失
draws_14w_dedup_v (今日): 0 条 ❌ 依赖 draws_14w
draws_today_v2 (今日): 0 条 ❌ 依赖链断裂
```

**数据同步问题**:
- `draws_clean` 有今日134期数据 (正常)
- `draws_14w` 缺失今日数据 (最新为2025-09-18)
- **数据管道中断**: `draws_clean` → `draws_14w` 同步失效

### 3️⃣ `consensus_candidates_api_v` - API输出失效
**状态**: 🔴 **BROKEN** - 0行API输出
**影响**: 外部API调用返回空数据

**依赖链故障**:
```
signal_pool_auto_v2 (0 rows)
    ↓
consensus_candidates_api_v (0 rows)
    ↓
API输出为空 ❌
```

---

## 📊 影响面评估

### 🔴 完全失效功能 (3个)
- **自动预测系统**: signal_pool_auto_v2
- **今日数据查询**: draws_today_v2
- **API数据输出**: consensus_candidates_api_v

### 🟡 部分影响功能 (11个)
**依赖 `draws_today_v2` 的视图**:
- `_period_norm_today_v` - 期号标准化
- `p_*_today_canon_v` - 预测视图 (3个)
- `votes_*_v` - 投票视图 (5个)
- `rule/veto_flags_today_v` - 规则标志 (2个)

### ✅ 正常运行功能
- `raw_history` - 历史数据查询
- `kpi_push_api_v` - KPI推送 (1行正常输出)
- 基础数据表 `draws_clean` (4583行)

---

## 🛠 故障修复优先级

### P0 - 立即修复 (数据同步)
```sql
-- 1. 修复 draws_clean → draws_14w 数据同步
INSERT INTO `wprojectl.pc28.draws_14w`
SELECT * FROM `wprojectl.pc28.draws_clean`
WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai');
```

### P1 - 紧急修复 (保底数据)
```sql
-- 2. 更新 signal_pool_fallback_today 未来数据
-- 需要重新运行生成未来期号的存储过程
CALL `wprojectl.pc28_lab.sp_fill_fallback_today_simple`('Asia/Shanghai');
```

### P2 - 优化修复 (时间窗口)
```sql
-- 3. 调整 signal_pool_auto_v2 的12小时窗口限制
-- 改为24小时或去掉时间限制，使用数据分区优化性能
WHERE ts_utc >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
```

---

## 🎯 根本原因总结

### 1. **数据管道故障**
- `draws_clean` → `draws_14w` 同步中断
- 可能原因: ETL作业失败、权限问题、调度停止

### 2. **时间窗口设计缺陷**
- 12小时窗口过于严格
- 保底数据未及时更新
- 缺乏数据过期容错机制

### 3. **依赖链脆弱性**
- 单点故障影响整个预测系统
- 缺乏降级和容错机制
- 监控告警不及时

---

## 🚀 立即行动计划

### ⚡ 紧急恢复 (15分钟内)
```bash
# 1. 手动同步今日数据到 draws_14w
bq query --use_legacy_sql=false "
INSERT INTO \`wprojectl.pc28.draws_14w\`
SELECT * FROM \`wprojectl.pc28.draws_clean\`
WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai');"

# 2. 重新生成保底数据
bq query --use_legacy_sql=false "
CALL \`wprojectl.pc28_lab.sp_fill_fallback_today_simple\`('Asia/Shanghai');"
```


### 🔧 系统加固 (1小时内)
1. **修复数据同步作业**
2. **调整时间窗口参数**
3. **增加容错机制**
4. **设置监控告警**

### 📊 验证恢复效果
```bash
# 验证修复效果
bq query --use_legacy_sql=false "
SELECT
  'draws_today_v2' as view_name,
  COUNT(*) as row_count
FROM \`wprojectl.pc28.draws_today_v2\`
UNION ALL
SELECT
  'signal_pool_auto_v2' as view_name,
  COUNT(*) as row_count
FROM \`wprojectl.pc28_lab.signal_pool_auto_v2\`
UNION ALL
SELECT
  'consensus_candidates_api_v' as view_name,
  COUNT(*) as row_count
FROM \`wprojectl.pc28.consensus_candidates_api_v\`;"
```

**预期修复后结果**:
- draws_today_v2: 134行 (今日数据)
- signal_pool_auto_v2: >0行 (预测数据)
- consensus_candidates_api_v: >0行 (API输出)

---

## 📈 长期优化建议

### 1. **数据管道监控**
- 每小时检查关键表数据新鲜度
- 自动化数据同步作业
- 失败自动重试机制

### 2. **容错设计改进**
- 多时间窗口容错 (12h/24h/48h)
- 降级保底数据机制
- 依赖解耦设计

### 3. **实时告警系统**
- 关键视图0行数据告警
- 数据延迟超阈值告警
- API输出异常告警

---

## 🎯 执行状态总结

**功能故障率**: 3/43 = **7%** (严重故障)
**影响功能数**: 14个 (3个完全失效 + 11个部分影响)
**修复紧急度**: 🔴 P0 - 立即处理

**当前状态**: 预测系统完全瘫痪，需要立即修复

---

*故障分析完成时间: 2025-09-19 03:40 CST*
*检查范围: 43个下游视图，发现3个关键故障*
*建议处理时间: <1小时紧急修复*
