# PC28 高级特性详细记录

## 🎯 系统高级特性完整提取 (gtp.txt深度分析)

### 📊 执行后自动验证机制

#### 四层计数验证
```
1. candidates_v2 应 > 0 (候选信号存在)
2. signal_pool_union_v2/v3 ≥ ensemble ≥ canonical (层级递减)
3. 来源数检查: 若 <3 自动切 v3
4. COUNT(DISTINCT source) 验证多源供给
```

#### 投票桶验证
```
理想状态: ≥3个投票桶 (跨市场累计)
检查方法: 统计不同投票比例的数量
自动调整: 桶数不足时扩容到v3版本
```

#### KPI 60分钟窗口验证
```sql
-- 覆盖率计算
cov_60m = orders_60m / draws_60m

-- 准确率收敛验证
acc_60m = wins / (wins + losses)

-- 实时监控指标
SELECT
  market,
  n_orders,
  n_settled,
  coverage_rate,
  accuracy,
  brier_score,
  wilson_lower_bound
FROM kpi_realtime_v
```

### 🎯 达标路径详细说明

#### 覆盖率50%达成机制
```
1. 视图天然封顶至50% (防止过度交易)
2. 上游供给存在时，覆盖会逼近50%
3. 候选仍少时，自动降阈到0.55
4. 真参数表实时更新
```

#### 准确率80%达成机制
```
1. 在线校准系统自动调整
2. Guard守护机制防止偏离
3. AutoSwitch按acc偏差微调阈值与模式
4. 短期噪声逐步收敛回80%带
```

#### 风险控制机制
```
1. EV>0严格检查 (只下正EV单)
2. 仅未开奖期号参与
3. 封顶50%防止过度暴露
4. Kelly系数严格限制
```

### 🔧 故障处理详细剧本

#### 供给偏低处理
```
检查步骤:
1. 确认 p_cloud/map/size_today_v 当日真数据
2. 验证三源数据完整性
3. 检查预测模型输出质量
4. 确认候选视图生成逻辑

自动处理:
1. 三源缺失时降级兼容
2. v3扩容增加候选来源
3. 动态降低阈值到0.55
4. 自动切换到balanced模式
```

#### 准确率异常处理
```
检查步骤:
1. 分析Brier分数是否正常
2. 验证校准参数是否合理
3. 检查样本分布是否异常
4. 确认模型预测质量

自动处理:
1. 校准参数自动调整
2. 模式自动切换到conservative
3. 阈值自动提高
4. Guard锁定保护
```

### 📈 性能监控详细指标

#### 实时监控指标
```python
performance_metrics = {
  "coverage_metrics": {
    "current_coverage": "当前覆盖率",
    "target_coverage": "目标覆盖率50%",
    "coverage_trend": "覆盖率趋势",
    "coverage_volatility": "覆盖率波动性"
  },

  "accuracy_metrics": {
    "current_accuracy": "当前准确率",
    "target_accuracy": "目标准确率80%",
    "wilson_lower_bound": "Wilson置信下界",
    "brier_score": "Brier评分",
    "calibration_error": "校准误差"
  },

  "risk_metrics": {
    "current_ev": "当前期望收益",
    "kelly_utilization": "Kelly系数利用率",
    "max_drawdown": "最大回撤",
    "sharpe_ratio": "夏普比率"
  },

  "system_metrics": {
    "pi_controller_status": "PI控制器状态",
    "autoswitch_mode": "AutoSwitch模式",
    "guard_status": "Guard保护状态",
    "calibration_status": "校准系统状态"
  }
}
```

### 🔄 热补丁系统详细设计

#### 运行时参数消费
```python
# 外部请求文件监控
request_files = {
  "bucket_floor_request.json": "阈值调整请求",
  "mode_switch_request.json": "模式切换请求",
  "param_tweak_request.json": "参数微调请求"
}

# TTL过期检查
def check_request_ttl(request_data):
    current_time = time.time()
    request_time = request_data.get("ts", 0)
    ttl_seconds = request_data.get("ttl_sec", 0)

    return (current_time - request_time) < ttl_seconds
```

#### 配置热重载
```python
# 配置文件变更检测
def detect_config_changes():
    config_files = [
        "CHANGESETS/config/pc28_enhanced_config.yaml",
        "CHANGESETS/config/auto_smart_switch.yaml"
    ]

    for config_file in config_files:
        if file_modified_since_last_check(config_file):
            reload_config(config_file)
            notify_config_change(config_file)
```

### 📊 回滚系统详细机制

#### 自动备份策略
```bash
# 视图备份命名规则
backup_pattern = "CHANGESETS/rollback/${view_name//[:.]/_}.sql.$(date +%Y%m%d_%H%M%S)"

# 备份保留策略
- 保留最近7个版本
- 自动清理30天前的备份
- 关键视图额外保留
```

#### 回滚验证
```bash
# 回滚后验证
restore_verification = {
  "view_exists": "bq show ${view_name}",
  "data_consistency": "SELECT COUNT(*) FROM ${view_name}",
  "schema_integrity": "验证字段完整性",
  "performance_impact": "对比回滚前后性能"
}
```

### 🎪 完整的生命周期管理

#### 启动流程
```
1. 环境变量检查
2. 依赖验证 (python3/jq/bq)
3. 配置文件加载
4. BigQuery连接测试
5. 状态文件初始化
6. 服务注册 (systemd/cron)
7. 初始KPI基线建立
```

#### 运行时监控
```
1. 每2分钟执行一次tick
2. PI控制器参数调整
3. AutoSwitch状态检查
4. Guard保护机制验证
5. KPI指标计算
6. Telegram状态推送
```

#### 故障恢复
```
1. 异常检测和分类
2. 自动诊断根因
3. 执行对应修复剧本
4. 验证修复效果
5. 记录故障和恢复过程
```

### 🔧 核心算法详细实现

#### 决策算法 (decide函数)
```python
def decide(p_cloud, p_map, p_size, cfg, perf):
    # 三源权重动态调整
    weights = update_weights_based_on_performance(perf)

    # 加权平均
    p_star = (weights["cloud"] * p_cloud +
              weights["map"] * p_map +
              weights["size"] * p_size)

    # 极端值门控
    if p_star >= cfg["voting"]["extreme_gate"]["hi"]:
        p_star = cfg["voting"]["extreme_gate"]["hi"]
    elif p_star <= cfg["voting"]["extreme_gate"]["lo"]:
        p_star = cfg["voting"]["extreme_gate"]["lo"]

    # 阈值检查
    accept_threshold = cfg["voting"]["accept_floor"]
    accept = p_star >= accept_threshold

    return {
        "p_star": p_star,
        "accept": accept,
        "weights_used": weights,
        "threshold_used": accept_threshold
    }
```

#### 校准算法详细实现
```python
def apply_hybrid_calibration(p_star, segment_key, calibration_params):
    # 获取分段参数
    segment_params = calibration_params.get(segment_key, {"a": 1.0, "b": 0.0, "T": 1.0})

    # Platt校准
    def logit(p): return math.log(p / (1 - p + 1e-9))
    def inv_logit(x): return 1 / (1 + math.exp(-x))

    platt_result = inv_logit(segment_params["a"] * logit(p_star) + segment_params["b"])

    # 温度校准
    temp_result = inv_logit(logit(p_star) / segment_params["T"])

    # 混合策略
    calibrated_p = 0.7 * platt_result + 0.3 * temp_result

    return max(1e-6, min(1-1e-6, calibrated_p))
```

---

**所有高级特性和细节已详细记录，确保不遗漏任何有用信息！** 📊

**这确实是一个极其精密和高级的自适应交易系统！** 🎯
