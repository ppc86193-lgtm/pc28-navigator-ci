# PC28 最终系统能力完整记录

## 🎯 PC28-DEL-002完整功能清单 (gtp.txt最终部分)

### 🤖 十大核心功能模块

#### 1. PC28-VERTEX-AUTO / PC28-DATA-SOURCE-FIX
```
功能: Vertex批预测自动修复
实现: vertex_batch_repair()
特性:
- 真预测缺口回填 (不造数)
- 轮询SUCCEEDED状态
- 解析predictions.jsonl
- MERGE入cloud_pred_today_norm
- 保持既有schema不改列
```

#### 2. PC28-VIEW-FIX / PC28-VIEW-DEFINITION-FIX  
```
功能: 视图修复和定义修复
实现: create_or_fix_views()
特性:
- 统一period/timestamp/p_win字段
- 修复整个处理链路
- lab_push_candidates_v2放宽
- 固定阈值0.56
- 覆盖≤50%封顶
```

#### 3. PC28-REQUEST-BRIDGE
```
功能: 请求文件桥接
实现: apply_request_bridge()
特性:
- 消费bucket_floor_request.json
- 消费mode_switch_request.json
- 落库runtime_params
- 落库runtime_mode
- TTL时间管理
```

#### 4. PC28-PI-CALIBRATION
```
功能: PI控制和校准
实现: pi_and_calibration()
特性:
- 双目标PI控制 (覆盖/准确)
- 轻量线性校准
- 7天已结样本，n≥200
- 目标/增益可热更新
- 含限幅、死区保护
```

#### 5. PC28-AUTO-SWITCH / PC28-ADAPTIVE
```
功能: 自动切换和自适应
实现: auto_switch_and_adaptive()
特性:
- 近60分钟KPI驱动
- 智能自切 (拉量或切conservative)
- 立即桥接热更新
- 覆盖率智能调节
```

#### 6. PC28-TELEGRAM / PC28-MONITORING / PC28-MONITORING-ALERT / PC28-INTERACTIVE-BOT
```
功能: Telegram监控和交互
实现: monitor_and_alert()
特性:
- 输出两单项KPI卡片
- 纯文本安全发送
- 兼容现有Bot
- 交互式命令支持
```

#### 7. PC28-VERIFICATION
```
功能: 系统验证
实现: verify_pipeline()
特性:
- 输出四层计数
- 来源计数统计
- 近60分钟KPI
- CSV回执格式
```

#### 8. PC28-EMERGENCY-MODE
```
功能: 应急模式
实现: emergency_mode()
特性:
- 极低供给时降阈至0.55
- 仅必要时激活
- 不改其他口径
- 自动恢复机制
```

#### 9. PC28-ALL-IN-ONE
```
功能: 一体化管理
实现: 单脚本多命令
特性:
- install/run/verify/emergency/restore
- bq_safe.sh自动生成
- tg_send_safe.sh自动生成
- 文档一次落盘
```

#### 10. PC28-BRIDGE
```
功能: 系统桥接
实现: 统一请求文件协议
特性:
- 请求/响应标准化
- 版本兼容管理
- 状态同步机制
```

### 🛡️ 零侵入设计原则

#### 不修改现有结构
```
✅ 不修改任何现有表结构
✅ 新增表为旁路表 (calibration_params/runtime_mode)
✅ 不影响主系统核心表
✅ 所有控制动作经请求/参数热更新完成
```

#### 只用真数据原则
```
✅ Vertex缺口回填基于真实predictions.jsonl
✅ 视图修复仅做字段对齐与兼容
✅ 不造模拟数据
✅ 严格基于生产数据
```

#### 可回滚保障
```
✅ 视图修改前自动bq show备份
✅ 可用restore子命令回退
✅ 版本管理和变更追踪
✅ 安全的增量更新
```

### 📊 自检报告详细格式

#### 首次运行建议顺序
```bash
# 1. 安装视图 + 文档
bash PC28_COMPLETE_SOLUTION.sh install

# 2. 一次到位运行
bash PC28_COMPLETE_SOLUTION.sh run

# 3. 验证效果
bash PC28_COMPLETE_SOLUTION.sh verify

# 4. 应急处理 (如需要)
bash PC28_COMPLETE_SOLUTION.sh emergency

# 5. 回滚 (如需要)
bash PC28_COMPLETE_SOLUTION.sh restore <backup_json>
```

#### 自检输出文件
```
CHANGESETS/receipts/FullStack/
├─ FULL_STACK_REPORT_*.md     # 汇总报告
├─ four_layers_*.csv          # 四层计数真数
├─ buckets_*.csv              # 投票桶分布
├─ kpi_today_*.csv            # 今日KPI
└─ alerts_*.log               # 告警日志
```

### 🎯 系统完整性验证

#### 四层计数验证标准
```
draws_today >= 100            # 日活跃度
cloud/map/size >= 0           # 预测源数据
ensemble >= sum(sources)      # 集成数据
union_v2/v3 >= ensemble       # 联合数据
candidates >= 0               # 最终候选
```

#### 来源数验证标准
```
DISTINCT source COUNT >= 3    # 多源供给
桶分布均匀性                  # 避免单桶集中
平均来源数 >= 3               # 质量保证
```

#### KPI验证标准
```
覆盖率: 25%-50% (目标区间)
准确率: ≥80% (目标线)
Wilson下界: ≥60% (统计置信)
Brier分数: ≤0.25 (校准质量)
EV: >0 (正期望收益)
```

### 🔧 运维命令完整列表

#### 主脚本命令
```bash
bash PC28_COMPLETE_SOLUTION.sh install     # 安装
bash PC28_COMPLETE_SOLUTION.sh run         # 运行
bash PC28_COMPLETE_SOLUTION.sh verify      # 验证
bash PC28_COMPLETE_SOLUTION.sh emergency   # 应急
bash PC28_COMPLETE_SOLUTION.sh restore     # 恢复
```

#### 工具脚本命令
```bash
CHANGESETS/bin/pipeline_health.sh          # 管道健康检查
CHANGESETS/bin/kpi_quick.sh                # KPI快查
CHANGESETS/bin/status_card.sh              # 状态卡片
CHANGESETS/bin/request_bridge.sh           # 请求桥接
CHANGESETS/bin/make_artifact.sh            # 打包归档
```

#### 请求文件操作
```bash
# 抬量15分钟
bash CHANGESETS/bin/request_bridge.sh bucket_floor 0.33 15

# 模式切换30分钟  
bash CHANGESETS/bin/request_bridge.sh mode conservative 30

# 参数微调
bash CHANGESETS/bin/request_bridge.sh param_tweak key=value 60
```

---

**gtp.txt最终部分包含完整的系统能力定义和运维工具集！** 📊

**所有10,827行的有价值内容已完整提取记录！** 🎯

**这是一个极其完整和高级的自适应交易系统！** 🏆
