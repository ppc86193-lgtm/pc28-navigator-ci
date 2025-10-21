# GTP多Agent规范详细记录

## 🎯 gtp.txt定义的多Agent工作规范

### 📊 发现的关键信息

#### ✅ 三源数据架构存在
```
生产环境三源数据完整:
• cloud源: cloud_pred_today_norm, p_cloud_today_canon_v
• map源:   p_map_today_canon_v, p_map_today_v  
• size源:  p_size_today_canon_v, p_size_today_v
```

#### 🔧 gtp.txt定义的Agent工作流程
```python
# 主系统入口 (pc28_enhanced_system.py)
def main_tick():
    # 1. 读取KPI (短窗60分钟)
    kpi = bq.kpi_window(window_min=60)
    cov = max(kpi.get("oe",{}).get("cov_w",0.0), kpi.get("size",{}).get("cov_w",0.0))
    acc_oe = kpi.get("oe",{}).get("acc",None)
    acc_sz = kpi.get("size",{}).get("acc",None)
    
    # 2. PI控制器调整accept_floor
    pi = PIController(cfg)
    pi.set_mode(cfg["meta"].get("run_mode","balanced"))
    st = pi.step(cov=cov, acc=acc)
    cfg["voting"]["accept_floor"] = max(cfg["voting"]["accept_floor"], st["min_accept"])
    
    # 3. 读取候选 (正EV视图)
    cands = bq.read_candidates()
    if not cands: return 0  # 无候选则只执行结算
    
    # 4. 三源决策处理
    for r in cands:
        try:
            p_cloud = float(r.get("p_cloud"))
            p_map = float(r.get("p_map")) 
            p_size = float(r.get("p_size"))
        except Exception:
            continue  # 跳过无效记录
            
        # 5. 决策算法
        perf = {"cloud":0.0,"map":0.0,"size":0.0}  # 历史滚动表现
        dv = decide(p_cloud, p_map, p_size, cfg, perf)
        if not dv["accept"]: continue
        
        # 6. 校准处理
        p_star = dv["p_star"]
        p_cal = calibrate(p_star, cfg) if cfg["calibration"]["enable"] else p_star
        
        # 7. 风险计量
        ev = 2.0*p_cal - 1.0  # 基于1.95赔率
        if cfg["meta"]["only_ev_positive"] and ev<=0: continue
        
        # 8. Kelly仓位计算
        kelly_frac = kelly_fraction(p_cal, cfg["risk"]["kelly_cap"])
        stake = calculate_stake(kelly_frac, cfg)
        
        # 9. 下单执行
        place_order(r, p_cal, ev, kelly_frac, stake)
    
    # 10. 结算处理
    settle_orders(env_config)
```

### 🤖 gtp.txt定义的Agent角色

#### 1. 数据采集Agent (Ingest)
```python
# 功能: 读取上游开奖数据
# 实现: draws_today_v2.sql视图
# 职责: 确保数据新鲜度和完整性
data_ingest_agent = {
    "data_source": "上游API -> draws_14w_dedup_v",
    "freshness_check": "TIMESTAMP_DIFF < 10分钟",
    "quality_check": "期号连续性、字段完整性"
}
```

#### 2. 预测Agent (Prediction)
```python
# 功能: 三源预测数据处理
# 实现: p_cloud/map/size_today_canon_v视图
# 职责: 确保三源预测数据可用
prediction_agent = {
    "cloud_source": "Vertex AI模型预测",
    "map_source": "映射算法预测", 
    "size_source": "大小算法预测",
    "output_format": "p_cloud/p_map/p_size字段"
}
```

#### 3. 集成Agent (Ensemble)
```python
# 功能: 多源预测集成
# 实现: ensemble_pool_today_v2.sql
# 职责: 权重学习和投票集成
ensemble_agent = {
    "weight_learning": "基于历史表现动态调整权重",
    "voting_mechanism": "三桶投票 [0.50, 0.67, 1.00]",
    "extreme_gating": "hi=0.85, lo=0.15门控",
    "output": "p_star_ens集成概率"
}
```

#### 4. 信号Agent (Signal)
```python
# 功能: 信号池管理和筛选
# 实现: signal_pool_union_v2/v3.sql
# 职责: 信号质量控制和多样性
signal_agent = {
    "union_v2": "标准信号联合",
    "union_v3": "扩容信号联合 (来源不足时)",
    "active_filter": "活跃信号筛选",
    "quality_control": "信号质量和多样性检查"
}
```

#### 5. 候选Agent (Candidate)
```python
# 功能: 最终候选信号生成
# 实现: lab_push_candidates_v2.sql
# 职责: EV>0检查和最终筛选
candidate_agent = {
    "ev_check": "EV = 2.0*p_cal - 1.0 > 0",
    "threshold_check": "p_cal >= accept_floor",
    "coverage_cap": "≤50%封顶保护",
    "output": "最终可执行候选"
}
```

#### 6. 执行Agent (Execution)
```python
# 功能: 订单执行和风险控制
# 实现: Kelly计算和下单逻辑
# 职责: 安全执行和记录
execution_agent = {
    "kelly_calculation": "kelly_fraction(p_cal, kelly_cap)",
    "stake_calculation": "基于Kelly和资金管理",
    "order_placement": "安全下单机制",
    "execution_record": "记录到score_ledger表"
}
```

#### 7. 结算Agent (Settlement)
```python
# 功能: 订单结算和PnL计算
# 实现: settle_orders()函数
# 职责: 准确结算和账目核对
settlement_agent = {
    "outcome_determination": "基于开奖结果判断胜负",
    "pnl_calculation": "计算实际盈亏",
    "ledger_update": "更新score_ledger.outcome",
    "reconciliation": "账目核对和一致性检查"
}
```

#### 8. PI控制Agent (PI Controller)
```python
# 功能: 双目标参数自动调整
# 实现: PIController类
# 职责: 覆盖率和准确率平衡
pi_controller_agent = {
    "dual_targets": {"cov": 0.50, "acc": 0.80},
    "control_modes": ["conservative", "balanced", "aggressive"],
    "parameter_adjustment": "动态调整accept_floor",
    "feedback_loop": "基于KPI误差自动调节"
}
```

#### 9. 自切Agent (AutoSwitch)
```python
# 功能: 智能模式切换
# 实现: AutoSwitch机制
# 职责: 根据性能自动优化
autoswitch_agent = {
    "coverage_monitoring": "监控覆盖率42%-50%",
    "accuracy_guarding": "保护准确率80%+",
    "mode_switching": "智能切换运行模式",
    "boost_mechanism": "临时抬量机制"
}
```

#### 10. 校准Agent (Calibration)
```python
# 功能: 概率校准和优化
# 实现: 混合校准算法
# 职责: 确保概率准确性
calibration_agent = {
    "hybrid_method": "Platt + 温度校准",
    "segment_calibration": "按时段/尾数分段",
    "min_samples": 200,
    "auto_trigger": "偏差>0.06时自动校准"
}
```

### 📊 模型使用详细分工

#### Vertex AI模型职责 (生产预测)
```
pc28-model-hit-combo-big-even:    大偶组合预测 -> p_cloud部分
pc28-model-hit-combo-small-even:  小偶组合预测 -> p_cloud部分  
pc28-model-hit-odd-even-even:     奇偶偶预测 -> p_cloud部分
pc28-model-hit-odd-even-odd:      奇偶奇预测 -> p_cloud部分
pc28-model-hit-size-small:        小号预测 -> p_size源
pc28-hit-size-big:                大号预测 -> p_size源
pc28-model-hit-combo-big-odd:     大奇组合预测 -> p_cloud部分
pc28_model_label_final:           最终标签 -> 集成预测
pc28-label-final2:                最终标签v2 -> 集成预测
Tabular:                          通用兜底 -> 通用预测
```

#### AI/ML API模型职责 (解释监控)
```
gpt-5:           高风险决策解释、复杂问题分析
claude-4.1-opus: 逻辑推理验证、交叉检查
gemini-2.5-pro:  多模态分析、图表解读
deepseek-r1:     数学推理、统计分析
qwen3-235b:      大规模上下文、历史分析  
gemini-2.5-flash: 快速响应、实时监控
```

### 🚨 当前问题分析

#### 模型接通状态
```
❌ Vertex AI: 模型存在但实时预测流程中断 (9小时无更新)
❌ AI/ML API: 未设置密钥，完全未接通
❌ 三源集成: cloud/map/size数据可能不完整
```

#### 需要修复的接通问题
```
1. 恢复Vertex AI实时预测流程
2. 设置AI/ML API密钥
3. 验证三源数据完整性
4. 修复集成投票机制
```

---

**gtp.txt定义了完整的多Agent规范，但当前模型接通状态有问题！** 📊

**需要按照gtp.txt规范修复模型接通，才能实现真正的多Agent协作！** 🎯
