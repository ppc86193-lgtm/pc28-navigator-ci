# PC28 自适应系统详细架构记录

## 📊 系统设计高级特性详细记录

### 🎯 核心设计理念
- **零侵入**: 不改变现有系统，只增强监控和控制
- **真数据驱动**: 不造模拟数据，只读真表
- **自适应收敛**: PI控制器+AutoSwitch双重自适应
- **科学方式**: 基于统计学和控制理论的参数调整

### 🔧 PI控制器详细设计

#### 双目标控制系统
```python
# 目标设定
targets: {
  cov: 0.50,    # 覆盖率目标50%
  acc: 0.80     # 准确率目标80%
}

# 三种模式的控制参数
conservative: {k_cov: 0.10, k_acc_up: 0.10, k_acc_dn: 0.30}
balanced:     {k_cov: 0.20, k_acc_up: 0.15, k_acc_dn: 0.35}
aggressive:   {k_cov: 0.35, k_acc_up: 0.20, k_acc_dn: 0.40}

# 控制逻辑
err_cov = target_cov - current_cov
err_acc = target_acc - current_acc
delta = k_cov*err_cov + (k_dn*max(err_acc,0) - k_up*max(-err_acc,0))
new_floor = current_floor - delta
```

#### 控制边界
```python
knobs_bounds: {
  min_accept: 0.33,   # 最低阈值
  max_accept: 0.67    # 最高阈值
}
```

### 🎪 三桶投票系统详细机制

#### 投票桶配置
```python
buckets: [0.50, 0.67, 1.00]
accept_floor: 动态调整 (0.33-0.67)

# 权重学习系统
weights_init: {cloud: 0.50, map: 0.30, size: 0.20}
weight_floor: 0.10
weight_ceiling: 0.70
weight_eta: 0.02    # 权重学习步长
```

#### 极端值门控
```python
extreme_gate: {
  enable: true,
  hi: 0.85,     # 极端高置信门
  lo: 0.15      # 极端低置信门
}
```

### 🔄 AutoSwitch智能切换详细逻辑

#### 覆盖率控制
```python
autoswitch: {
  enable: true,
  cov_lo: 0.42,       # 覆盖率下限42%
  cov_hi: 0.50,       # 覆盖率上限50%
  acc_guard: 0.80,    # 准确率保护线80%
  acc_abort: 0.60,    # 准确率中止线60%
  min_settled: 40,    # 最小结算样本
  dwell_min: 10       # 最小停留时间
}
```

#### 抬量机制
```python
boost: {
  ttl_min: 15,        # 抬量持续时间15分钟
  floor: 0.33         # 抬量时的地板阈值
}
```

#### 智能切换逻辑
```
低覆盖且准确良好 → 短期抬量(floor=0.33, TTL 15m/60m)
覆盖达标 or 到期 → 自动撤销
准确过低(≤60%) → 撤销并建议conservative
稳定高质(ACC≥85%, COV≥50%) → 建议aggressive
```

### 🎯 校准系统详细设计

#### 混合校准方法
```python
calibration: {
  enable: true,
  method: "hybrid",    # Platt per-segment + temperature
  segments: [
    {key: "session"},  # 凌晨/上午/下午/傍晚
    {key: "tail"}      # 和值tail
  ],
  min_samples: 200,
  max_lookback_days: 14
}
```

#### 校准算法实现
```python
# Platt校准: p_cal = 1/(1 + exp(-(a*logit(p) + b)))
# 温度校准: p_cal = 1/(1 + exp(-logit(p)/T))
# 混合: 分段使用不同校准方法
```

### 💰 Kelly风险管理详细机制

#### 风险参数
```python
risk: {
  kelly_cap: 0.05,           # Kelly上限5%
  bankroll_u: 10000,         # 资金单位
  unit_u: 50,                # 下注单位
  dd_guard: {                # 回撤保护
    window: 200,             # 回撤窗口
    max_drawdown_pct: 0.15,  # 最大回撤15%
    cool_off_min: 30         # 冷却时间30分钟
  }
}
```

#### Kelly计算公式
```python
def kelly_fraction(p_win: float, cap: float = 0.05) -> float:
    ev = 2.0 * p_win - 1.0   # EV = 2p - 1 (1.95赔率简化)
    return max(0.0, min(cap, ev))

def stake_units(p_win: float, unit: int, cap: float) -> int:
    f = kelly_fraction(p_win, cap)
    su = int(round(f / max(1e-9, cap))) * unit
    return max(0, su)
```

### 📊 BigQuery数据架构详细设计

#### 核心表结构
```sql
-- 账本表 (score_ledger)
CREATE TABLE `${PROJECT}.${DS_LAB}.score_ledger` (
  id STRING,
  day_id_cst DATE,
  market STRING,           -- 'oe' or 'size'
  draw_id INT64,           -- 期号
  created_at TIMESTAMP,
  p_win FLOAT64,           -- 胜率
  ev FLOAT64,              -- 期望收益
  kelly_frac FLOAT64,      -- Kelly系数
  stake_u INT64,           -- 下注单位
  outcome STRING,          -- 'win'/'lose'/NULL
  tag STRING               -- 'prod'/NULL
);

-- 运行时参数表 (runtime_params)
CREATE TABLE `${PROJECT}.${DS_LAB}.runtime_params` (
  market STRING,
  p_min_base FLOAT64,      -- 动态阈值
  last_updated TIMESTAMP,
  mode STRING,             -- conservative/balanced/aggressive
  config_version STRING
);
```

#### KPI查询逻辑
```sql
-- 60分钟窗口KPI
WITH L AS (
  SELECT market, outcome, p_win, created_at
  FROM `${PROJECT}.${DS_LAB}.score_ledger`
  WHERE (tag IS NULL OR tag='prod')
    AND day_id_cst=CURRENT_DATE('${TZ}')
    AND market IN ('oe','size')
    AND created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 MINUTE)
)
SELECT
  market,
  COUNT(*) AS n_ord_w,
  COUNTIF(outcome IN ('win','lose')) AS n_set_w,
  SAFE_DIVIDE(COUNTIF(outcome='win'), NULLIF(COUNTIF(outcome IN ('win','lose')),0)) AS acc_w,
  AVG(p_win) AS pbar_w,
  AVG((IF(outcome='win',1,0)-p_win)*(IF(outcome='win',1,0)-p_win)) AS brier_w
FROM L GROUP BY market
```

### 🔄 状态管理系统详细设计

#### 状态文件结构
```json
{
  "_v": "1.0",
  "enabled": true,
  "boost_active": false,
  "boost_until": 0,
  "last_action": 0,
  "good_bal": 0,
  "good_aggr": 0,
  "tick": 0,
  "min_accept": 0.50
}
```

#### 请求文件协议
```json
// bucket_floor_request.json
{
  "market": "both",
  "bucket_floor": 0.33,
  "ttl_sec": 900,
  "reason": "boost_coverage",
  "ts": "2025-09-17T12:30:00Z"
}

// mode_switch_request.json
{
  "mode": "balanced",
  "ttl_sec": 900,
  "reason": "performance_optimization",
  "ts": "2025-09-17T12:30:00Z"
}
```

### 🚀 服务化部署详细配置

#### systemd用户服务
```ini
[Unit]
Description=PC28 Enhanced System (user)
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${ROOT}
EnvironmentFile=-${HOME}/.pc28.env
ExecStart=${ROOT}/CHANGESETS/tools/run_enhanced.sh
Nice=10

[Install]
WantedBy=default.target
```

#### 定时器配置
```ini
[Unit]
Description=PC28 Enhanced Timer (user)
Requires=pc28-enhanced.service

[Timer]
OnCalendar=*:*/2    # 每2分钟执行
Persistent=true
AccuracySec=1s

[Install]
WantedBy=timers.target
```

### 📡 Telegram集成详细设计

#### 通知系统
```bash
# 轻量通知器
curl -sS -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d "chat_id=${CHAT_ID}" \
  --data-urlencode "text=${MSG}"
```

#### 命令钩子
```
/autoswitch on|off|auto|status|force-boost|release
/kpi_today - 显示当日KPI
/mode conservative|balanced|aggressive - 切换模式
```

### 🔍 监控与验证详细机制

#### 四项验证流程
```bash
# A. 日志刷新验证
tail -n 60 TEMP_CODE/logs/pc28_enhanced_system.log

# B. 候选增多验证
SELECT COUNT(*) AS n_cand FROM lab_push_candidates_v2
WHERE day_id_cst=CURRENT_DATE AND ev>0 AND p_win>theta

# C. 账目增长验证
SELECT market, COUNT(*) n_orders, COUNTIF(outcome IN ('win','lose')) n_settled
FROM score_ledger WHERE DATE(created_at)=CURRENT_DATE

# D. KPI 60分钟窗口验证
覆盖率 = n_ord / n_draws 应上升
准确率收敛验证
```

### 🛡️ 故障处理和回退机制

#### Guard锁定机制
```python
def guard_locked(cfg, state_dir) -> bool:
    if os.path.exists("/var/run/pc28.lock"): return True
    if os.path.exists(os.path.join(state_dir,"lock.flag")): return True
    return False
```

#### 自动回退逻辑
```
准确率≤60% → 自动切换到conservative模式
覆盖率>52% → 检查封顶逻辑
连续失败 → 触发Guard锁定
```

### 🔧 热补丁机制详细设计

#### 运行时参数消费
```python
# 外部floor请求消费 (可直接粘贴的热补丁)
def _read_floor_request():
    for path in _FLOOR_REQ_CANDIDATES:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    req = json.load(f)
                if req.get("ttl_sec", 0) > 0:
                    age = time.time() - req.get("ts", 0)
                    if age < req["ttl_sec"]:
                        return float(req.get("bucket_floor", 0.50))
            except: pass
    return None
```

#### 配置热更新
```python
# 配置文件热重载
def reload_config_if_changed():
    global _cfg_mtime, _cfg_cache
    try:
        mtime = os.path.getmtime("CHANGESETS/config/pc28_enhanced_config.yaml")
        if mtime != _cfg_mtime:
            _cfg_cache = read_yaml("CHANGESETS/config/pc28_enhanced_config.yaml")
            _cfg_mtime = mtime
    except: pass
    return _cfg_cache
```

### 📈 性能优化详细策略

#### 分段校准优化
```python
# 按时段分段校准
segments = ["session", "tail"]  # 凌晨/上午/下午/傍晚 + 和值尾数

# 每段独立的Platt参数
segment_params = {
  "morning": {"a": 1.0, "b": 0.0, "T": 1.0},
  "afternoon": {"a": 0.95, "b": 0.05, "T": 0.98},
  # ...
}
```

#### 权重学习算法
```python
# 基于滚动表现的权重调整
weight_eta = 0.02  # 学习步长

# 每个预测源的权重动态调整
for source in ["cloud", "map", "size"]:
    performance = calculate_recent_performance(source)
    weight_adjustment = weight_eta * (performance - baseline)
    new_weight = clip(current_weight + weight_adjustment, weight_floor, weight_ceiling)
```

### 🔍 诊断和修复详细流程

#### 根因诊断五步法
1. **bucket下限不生效** - 检查配置冲突
2. **覆盖率极低** - 分析模式和阈值设置
3. **BigQuery查询错误** - 验证字段和区位一致性
4. **模式限制** - 评估conservative模式影响
5. **校准参数** - 检查温度和阈值合理性

#### 一次到位修复脚本 (PERF_ATTAIN)
```bash
# 环境设置
PROJECT="${PROJECT:-wprojectl}"
DS_LAB="${DS_LAB:-pc28_lab}"
BQLOC="${BQLOC:-us-central1}"
TZ="${TZ:-Asia/Shanghai}"

# 参数修复
min_bucket=0.33     # 降低下限
theta=0.56          # 降低阈值
temperature=0.95    # 校准参数
mode=balanced       # 平衡模式

# 自动执行修复并验证
```

### 📊 监控指标详细定义

#### KPI计算公式
```sql
-- 覆盖率
COV = n_ord / n_draws

-- 准确率
ACC = n_win / (n_win + n_lose)

-- 期望收益
EV = 2.0 * p_win - 1.0

-- Brier分数
BRIER = AVG((predicted - actual)^2)

-- Wilson置信下界 (防偶然波动)
wilson_low = (acc + z²/(2n) - z*sqrt((acc*(1-acc) + z²/(4n))/n)) / (1 + z²/n)
```

#### 验收阈值标准
```
覆盖率: ≥35% (一阶达标), 目标50%
准确率: ≥80% 且 Wilson下界≥60%
期望收益: >0 (正EV)
Brier分数: <0.25
```

### 🛠️ 故障处理详细剧本

#### 覆盖率不上升
```
1. 检查bucket_floor_request.json是否被消费
2. 验证lab_push_candidates_v2候选数量
3. 确认上游预测/打分任务正常
4. 检查score_ledger统计口径
```

#### 准确率下降
```
1. 检查校准参数是否合理
2. 验证分段校准是否生效
3. 分析样本分布是否异常
4. 确认模型预测质量
```

#### BigQuery错误处理
```
1. 统一字段名: timestamp (不用ts_utc)
2. 统一时区: Asia/Shanghai
3. 统一区位: us-central1
4. 清理环境变量冲突
```

### 🔧 热补丁和增量更新

#### 运行时热更新
```python
# 无需重启的参数更新
def apply_runtime_patch():
    floor_req = _read_floor_request()
    if floor_req:
        cfg["voting"]["accept_floor"] = max(cfg["voting"]["accept_floor"], floor_req)

    mode_req = _read_mode_request()
    if mode_req:
        cfg["meta"]["run_mode"] = mode_req
```

#### 平滑重启机制
```bash
# run_enhanced.sh 平滑重启逻辑
# 1. 发送TERM信号
# 2. 等待进程优雅退出
# 3. 强制KILL僵进程
# 4. 启动新进程加载新配置
```

## 🎯 Navigator集成策略

### 定位: 智能运维大脑
- **不替代**: 现有自适应系统完整且高级
- **增强**: 提供智能监控和诊断能力
- **协同**: 监控PI控制器和AutoSwitch工作状态

### 具体集成点
1. **监控PI控制器**: 实时跟踪双目标收敛过程
2. **分析AutoSwitch**: 智能评估模式切换效果
3. **诊断参数配置**: AI分析配置合理性
4. **预警异常**: 提前发现系统偏离

---

**所有高级设计细节已详细记录，确保不遗漏任何有用信息！** 📊

**这是一个极其精密的自适应交易系统！** 🎯
