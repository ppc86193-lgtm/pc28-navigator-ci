# PC28 下游项目逻辑分析报告

## 📊 执行总结 (2025-09-19 03:35 CST)

### ✅ 分析范围
- **主数据集**: `wprojectl.pc28` (43个视图/表)
- **实验数据集**: `wprojectl.pc28_lab` (7个信号池相关视图)
- **核心数据源**: `draws_clean`, `signal_pool`, `draws_14w`

---

## 🎯 关键发现

### 🔴 CRITICAL 影响
**`raw_history` 视图** - 直接依赖 `draws_clean`
```sql
FROM `wprojectl.pc28.draws_clean`
```
- **影响**: 任何 draws_clean 的中断都会直接影响历史数据查询
- **当前状态**: ✅ 正常 (4583行，覆盖16天数据)

### 🟡 MEDIUM 影响
**11个视图** 依赖 `draws_14w` 系列表：
- `_period_norm_today_v` - 期号标准化
- `calendar_slices_v` - 日历切片
- `draws_today_v2` - 今日开奖视图
- `labels_today_v` - 今日标签
- `p_cloud_today_canon_v` - 预测云视图
- `p_map_today_canon_v` - 预测映射
- `p_size_today_canon_v` - 大小预测
- `rule_composite_flags_v` - 规则标志
- `veto_flags_today_v` - 否决标志
- `votes_*` - 各种投票视图

### 🟢 LOW 影响
**信号池视图** - 主要在 `pc28_lab` 中，用于实验和预测

---

## 📋 核心数据流依赖图

```
draws_clean (4583行)
    └── raw_history ⚠️ CRITICAL

draws_14w_dedup_v
    ├── draws_today_v2
    ├── p_*_today_canon_v (3个预测视图)
    ├── votes_*_v (5个投票视图)
    └── rule/veto flags_v (2个规则视图)

signal_pool (365行)
    ├── signal_pool_union_v2
    └── signal_pool_auto_v2 (当前0行 - 需关注)
```

---

## 🚨 数据完整性状态

### ✅ 正常运行
- **draws_clean**: 4583行，最新数据 2025-09-19 03:15:30
- **今日数据**: 134期开奖记录 (正常进行中)
- **昨日数据**: 402期完整 (接近理论403期)

### ⚠️ 需要关注
- **signal_pool_auto_v2**: 当前0行数据
  - 原因：可能由于时间窗口限制 (近12小时内真实信号)
  - 影响：自动预测功能可能受限

### 📊 信号池分布
```
pc28_CL1: 173条 (2025-09-18)
pc28_CL2: 152条 (2025-09-18)
pc28_CL3: 22条  (2025-09-18)
prod_model: 16条 (2025-09-14~15)
test_model: 2条  (2025-09-14)
```

---

## 🎯 关键视图逻辑分析

### 1. `signal_pool_auto_v2` (核心预测逻辑)
**设计思路**: 真实信号优先 + 保底填充
```sql
-- 限定近12小时的真实信号，降扫描成本
recent_real AS (
  FROM `wprojectl.pc28_lab.signal_pool_union_v2`
  WHERE ts_utc >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 12 HOUR)
)
-- 每 period+market 取最新一条真实记录
-- 仅在真实缺席的 period+market 上才启用保底
```

**当前问题**: 0行输出可能由于：
1. 12小时内无真实信号
2. signal_pool_fallback_today 未来数据为空
3. 时间窗口过于严格

### 2. `_period_norm_today_v` (期号标准化)
**功能**: 统一 draws 和 actions 的期号格式
```sql
-- draws侧: CAST(issue AS STRING) AS period_norm
-- actions侧: 长号如"pc28-3333709" -> "3333709"
```

### 3. `draws_today_v2` (今日开奖核心视图)
**依赖链**: `draws_14w` → `draws_14w_dedup_v` → `draws_today_v2`
**功能**: 提供今日所有开奖数据，支持实时查询

---

## 🔧 影响评估和建议

### 🎯 立即行动项

#### 1. 修复 `signal_pool_auto_v2` 空数据问题
**诊断命令**:
```sql
-- 检查近12小时真实信号
SELECT COUNT(*) FROM `wprojectl.pc28_lab.signal_pool_union_v2`
WHERE ts_utc >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 12 HOUR);

-- 检查保底数据
SELECT COUNT(*) FROM `wprojectl.pc28_lab.signal_pool_fallback_today`
WHERE timestamp >= CURRENT_TIMESTAMP();
```

#### 2. 监控核心依赖表健康度
```bash
# 每日数据完整性检查
bq query --use_legacy_sql=false "
SELECT
  DATE(timestamp, 'Asia/Shanghai') as date,
  COUNT(*) as periods,
  403 - COUNT(*) as missing
FROM \`wprojectl.pc28.draws_clean\`
WHERE DATE(timestamp, 'Asia/Shanghai') >= DATE_SUB(CURRENT_DATE('Asia/Shanghai'), INTERVAL 3 DAY)
GROUP BY 1 ORDER BY 1 DESC;
"
```

### 🚀 优化建议

#### 1. 视图性能优化
**高频查询视图建议分区**:
- `draws_today_v2` - 按日期分区
- `signal_pool_auto_v2` - 优化12小时窗口查询

#### 2. 依赖解耦
**减少单点故障**:
- 考虑为关键视图添加fallback机制
- `raw_history` 可考虑缓存机制

#### 3. 监控告警
**建议监控指标**:
- 每日期数完整率 (≥95%)
- signal_pool_auto_v2 数据可用性
- 关键视图查询性能

---

## 📈 下游系统健康检查清单

### ✅ 每日检查项
1. **数据新鲜度**: `MAX(timestamp)` 延迟 <10分钟
2. **期数完整性**: 今日期数 vs 预期403期
3. **信号池活跃度**: 各source最新数据时间
4. **视图可用性**: 关键视图是否正常返回数据

### 🔧 故障恢复优先级
1. **P0 - CRITICAL**: `draws_clean` 数据中断 → 影响 `raw_history`
2. **P1 - HIGH**: `draws_14w` 系列问题 → 影响11个预测/投票视图
3. **P2 - MEDIUM**: `signal_pool` 问题 → 影响实时预测功能

---

## 📊 系统架构总结

### 数据层级
```
原始数据层: draws_clean (4583行)
    ↓
聚合数据层: draws_14w_dedup_v
    ↓
应用视图层: 43个业务视图
    ↓
API输出层: consensus_*_api_v, kpi_push_api_v
```

### 预测系统
```
信号输入: signal_pool (5个来源)
    ↓
信号聚合: signal_pool_union_v2
    ↓
智能预测: signal_pool_auto_v2 (真实+保底)
    ↓
推送输出: lab_push_candidates_auto
```

**当前状态**: 🟢 数据管道正常，🟡 预测系统需要关注

---

*分析完成时间: 2025-09-19 03:35 CST*
*分析范围: 50个表/视图，365+4583条核心数据*
*风险等级: 🟢 LOW (系统稳定，少量优化建议)*
