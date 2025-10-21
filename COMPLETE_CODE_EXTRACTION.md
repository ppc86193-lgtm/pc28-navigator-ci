# PC28 完整代码提取记录

## 📊 gtp.txt完整代码模块提取

### 🎯 核心Python类实现

#### 1. BQ数据访问类
```python
class BQ:
    def __init__(self, project:str, ds_lab:str, ds_draw:str, bqloc:str, tz:str):
        self.proj, self.ds_lab, self.ds_draw, self.loc, self.tz = project, ds_lab, ds_draw, bqloc, tz

    def _run_json(self, sql:str, timeout:int=120)->List[Dict[str,Any]]:
        cmd = f"bq --location={shlex.quote(self.loc)} query --use_legacy_sql=false --format=json {shlex.quote(sql)}"
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=timeout)
        return json.loads(out.decode("utf-8") or "[]")

    def draws_today(self)->int:
        sql = f"SELECT COUNT(*) AS n FROM `{self.proj}.{self.ds_draw}.draws_14w_dedup_v` WHERE DATE(timestamp,'{self.tz}')=CURRENT_DATE('{self.tz}')"
        j = self._run_json(sql)
        return int(j[0].get("n",0)) if j else 0

    def kpi_window(self, window_min:int=60)->Dict[str,Any]:
        # 复杂的KPI计算SQL (60分钟窗口)
        # 返回覆盖率、准确率、Brier分数等指标
```

#### 2. PI控制器类
```python
class PIController:
    def __init__(self, cfg:Dict[str,Any]):
        self.cfg = cfg
        self.mode = cfg["meta"].get("run_mode","balanced")
        self.state = {"min_accept": cfg["voting"].get("accept_floor",0.50)}

    def set_mode(self, mode:str):
        self.mode = mode

    def step(self, cov:float, acc:float)->Dict[str,Any]:
        t_cov = float(self.cfg["controller"]["targets"]["cov"])
        t_acc = float(self.cfg["controller"]["targets"]["acc"])
        knobs = self.cfg["controller"][self.mode]
        k_cov = float(knobs["k_cov"])
        k_up = float(knobs["k_acc_up"])
        k_dn = float(knobs["k_acc_dn"])

        err_cov = t_cov - (cov or 0.0)
        err_acc = (t_acc - acc) if (acc is not None) else 0.0

        delta = k_cov*err_cov + (k_dn*max(err_acc,0.0) - k_up*max(-err_acc,0.0))
        new_floor = self.state["min_accept"] - delta
        new_floor = max(min_b, min(max_b, new_floor))

        return {"min_accept": new_floor, "changed": changed, "err_cov": err_cov, "err_acc": err_acc, "mode": self.mode}
```

#### 3. 风险管理模块
```python
def kelly_fraction(p_win:float, cap:float=0.05)->float:
    ev = 2.0*p_win - 1.0  # 基于1.95赔率的简化EV计算
    return max(0.0, min(cap, ev))

def stake_units(p_win:float, unit:int, cap:float)->int:
    f = kelly_fraction(p_win, cap)
    su = int(round(f / max(1e-9, cap))) * unit
    return max(0, su)
```

### 🔧 关键SQL视图定义

#### 1. 账本表DDL
```sql
CREATE TABLE IF NOT EXISTS `${PROJECT}.${DS_LAB}.score_ledger` (
  id STRING,
  day_id_cst DATE,
  market STRING,           -- 'oe' or 'size'
  draw_id INT64,           -- 期号
  created_at TIMESTAMP,
  p_win FLOAT64,
  ev FLOAT64,
  kelly_frac FLOAT64,
  stake_u INT64,
  outcome STRING,          -- 'win'/'lose'/NULL
  tag STRING,              -- 'prod'/NULL
  session STRING,          -- 'morning'/'afternoon'/etc
  tail INT64               -- 和值尾数
)
PARTITION BY day_id_cst
CLUSTER BY market, created_at;
```

#### 2. 运行时参数表
```sql
CREATE TABLE IF NOT EXISTS `${PROJECT}.${DS_LAB}.runtime_params` (
  market STRING,
  p_min_base FLOAT64,
  p_min_1_00 FLOAT64,
  p_min_0_67 FLOAT64,
  p_min_0_50 FLOAT64,
  last_updated TIMESTAMP,
  mode STRING,
  config_version STRING
)
CLUSTER BY market;
```

#### 3. KPI实时视图
```sql
CREATE OR REPLACE VIEW `${PROJECT}.${DS_LAB}.kpi_realtime_v` AS
WITH recent_window AS (
  SELECT
    market,
    COUNT(*) as n_orders,
    COUNTIF(outcome IN ('win','lose')) as n_settled,
    SAFE_DIVIDE(COUNTIF(outcome='win'), NULLIF(COUNTIF(outcome IN ('win','lose')),0)) as accuracy,
    AVG(p_win) as avg_p_win,
    AVG(CASE WHEN outcome IN ('win','lose') THEN POW(p_win - IF(outcome='win',1,0), 2) END) as brier_score
  FROM `${PROJECT}.${DS_LAB}.score_ledger`
  WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 MINUTE)
    AND (tag IS NULL OR tag='prod')
  GROUP BY market
),
draw_count AS (
  SELECT COUNT(*) as n_draws
  FROM `${PROJECT}.${DS_DRAW}.draws_14w_dedup_v`
  WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 MINUTE)
)
SELECT
  r.*,
  d.n_draws,
  SAFE_DIVIDE(r.n_orders, d.n_draws) as coverage_rate,
  -- Wilson置信下界
  SAFE_DIVIDE(
    r.accuracy + POW(1.96,2)/(2*r.n_settled) - 1.96*SQRT((r.accuracy*(1-r.accuracy)+POW(1.96,2)/(4*r.n_settled))/r.n_settled),
    1 + POW(1.96,2)/r.n_settled
  ) as wilson_lower_bound
FROM recent_window r
CROSS JOIN draw_count d;
```

### 🔄 AutoSwitch详细算法

#### 状态机设计
```python
# AutoSwitch状态转换
states = {
  "NORMAL": "正常运行",
  "LOW_COVERAGE": "覆盖率不足",
  "BOOST_ACTIVE": "抬量激活",
  "HIGH_ACCURACY": "高准确率",
  "LOW_ACCURACY": "低准确率"
}

# 状态转换条件
transitions = {
  "NORMAL -> LOW_COVERAGE": "cov < cov_lo and acc >= acc_guard",
  "LOW_COVERAGE -> BOOST_ACTIVE": "activate boost with floor=0.33",
  "BOOST_ACTIVE -> NORMAL": "cov >= cov_hi or ttl expired",
  "* -> LOW_ACCURACY": "acc < acc_abort"
}
```

#### 决策树实现
```python
def autoswitch_decision(cov, acc, settled, state):
    if settled < min_settled:
        return "WAIT_SAMPLES"

    if acc < acc_abort:
        return "EMERGENCY_CONSERVATIVE"

    if cov < cov_lo and acc >= acc_guard:
        return "ACTIVATE_BOOST"

    if cov >= cov_hi:
        return "DEACTIVATE_BOOST"

    if acc >= 0.85 and cov >= 0.50:
        return "SUGGEST_AGGRESSIVE"

    return "MAINTAIN_CURRENT"
```

### 📡 Telegram集成详细实现

#### 消息格式模板
```python
# KPI推送模板
kpi_template = """
🎯 PC28 KPI Report
📊 覆盖率: {coverage:.1%}
🎯 准确率: {accuracy:.1%}
💰 EV: {ev:.3f}
📈 Brier: {brier:.3f}
🔧 模式: {mode}
⚙️ 阈值: {threshold:.3f}
"""

# AutoSwitch状态模板
autoswitch_template = """
⚙️ AutoSwitch Status
🎚️ 当前模式: {mode}
📊 覆盖率: {coverage:.1%} (目标: 50%)
🎯 准确率: {accuracy:.1%} (目标: 80%)
🔧 当前动作: {action}
⏰ 下次检查: {next_check}
"""
```

### 🛡️ Guard机制详细设计

#### 锁定条件
```python
guard_conditions = {
  "max_drawdown": "回撤超过15%",
  "low_accuracy": "准确率连续低于60%",
  "system_error": "系统异常或数据中断",
  "manual_lock": "人工锁定"
}

# 锁定文件检查
lock_files = [
  "/var/run/pc28.lock",
  "~/.pc28_state/lock.flag",
  "TEMP_CODE/state/emergency.lock"
]
```

#### 自动解锁条件
```python
unlock_conditions = {
  "accuracy_recovery": "准确率恢复到80%以上",
  "drawdown_recovery": "回撤恢复到5%以下",
  "system_stable": "系统稳定运行30分钟",
  "manual_unlock": "人工解锁"
}
```

---

**继续深入提取gtp.txt的所有高级设计细节...** 📊
