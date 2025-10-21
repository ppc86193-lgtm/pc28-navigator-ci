# PC28 运维工具集完整记录

## 🛠️ 完整工具集架构 (gtp.txt 5000-9000行提取)

### 📁 CHANGESETS目录结构详细设计
```
CHANGESETS/
├─ bin/                           # 核心工具集
│  ├─ bq_safe.sh                  # BigQuery安全调用包装
│  ├─ pc28_pi_controller.sh       # PI控制器 (15min间隔)
│  ├─ pc28_auto_switch.sh         # 智能自切 (覆盖拉升/准确收敛)
│  ├─ pc28_calibrator.sh          # 校准器 (Platt/温度/分段)
│  ├─ tg_send_safe.py             # Telegram安全发送器
│  ├─ kpi_quick.sh                # KPI快查 (OE/SIZE/合并)
│  ├─ pipeline_health.sh          # 数据管道健康自检
│  ├─ status_card.sh              # 统一状态卡片
│  ├─ alert_guard.sh              # Guard告警 (异常检测+分级通知)
│  ├─ request_bridge.sh           # 请求文件桥
│  ├─ make_artifact.sh            # 打包与Gist上传
│  └─ rotate_logs.sh              # 日志轮转
├─ sql/                           # SQL视图定义
│  ├─ draws_today_v2.sql
│  ├─ p_cloud_today_canon_v.sql
│  ├─ p_map_today_canon_v.sql
│  ├─ p_size_today_canon_v.sql
│  ├─ ensemble_pool_today_v2.sql
│  ├─ signal_pool_union_v2.sql
│  ├─ signal_pool_union_v3.sql
│  ├─ signal_pool_union_active_v.sql
│  └─ lab_push_candidates_v2.sql
├─ docs/                          # 完整文档
│  ├─ README_FULL.md              # 完整架构文档
│  ├─ API_PROTOCOL.md             # 请求文件协议
│  ├─ OPERATIONS.md               # 运维手册
│  └─ TROUBLESHOOTING.md          # 排障指南
├─ receipts/                      # 执行回执
│  ├─ FullStack/
│  │  ├─ FULL_STACK_REPORT_*.md   # 安装/运行报告
│  │  ├─ four_layers_*.csv        # 四层计数
│  │  ├─ buckets_*.csv            # 投票桶分布
│  │  ├─ kpi_today_*.csv          # KPI输出
│  │  └─ alerts_*.log             # 告警日志
│  └─ Packages/
│     └─ pc28_full_stack_*.tar.gz # 压缩包产物
├─ rollback/                      # 回滚备份
│  └─ <view.ddl.backup>.json      # 视图DDL备份
└─ conf/
   └─ runtime.yml                 # 安装配置快照
```

### 🔧 核心工具详细功能

#### 1. bq_safe.sh - BigQuery安全包装器
```bash
# 规避python utils冲突的安全调用
#!/usr/bin/env bash
set -euo pipefail

# 清空可能冲突的环境变量
unset PYTHONPATH PYTHONHOME USER_SITE

# 切换到临时目录避免本地模块干扰
cd /tmp

# 执行bq命令
exec bq "$@"
```

#### 2. pc28_pi_controller.sh - PI控制器
```bash
# PI控制器详细实现
# 15分钟最小间隔、EMA平滑、死区、最大步长

features:
- 双目标控制 (覆盖率50% + 准确率80%)
- 三种模式 (conservative/balanced/aggressive)
- EMA平滑避免震荡
- 死区机制防止频繁调整
- 最大步长限制保护系统稳定
```

#### 3. pc28_auto_switch.sh - 智能自切
```bash
# 智能自切详细逻辑
# 覆盖拉升/准确收敛，TTL+冷却

features:
- 覆盖率监控 (42%-50%目标区间)
- 准确率保护 (80%保护线, 60%中止线)
- TTL时间限制 (15分钟抬量)
- 冷却机制防止频繁切换
- 自动模式建议 (conservative/balanced/aggressive)
```

#### 4. pc28_calibrator.sh - 校准器
```bash
# 校准器详细功能
# Platt/温度/分段触发与回滚

features:
- 混合校准方法 (Platt + 温度)
- 分段校准 (按时段/尾数分段)
- 最小样本要求 (200样本)
- 自动触发条件 (偏差>0.06)
- 校准效果验证和回滚
```

### 📊 自检报告系统详细设计

#### 四层计数验证
```csv
# four_layers_*.csv 格式
draws_today, cloud_rows, map_rows, size_rows, ensemble_rows, union_v2_rows, union_v3_rows, active_rows, candidates_rows

# 验证逻辑
draws_today >= 100        # 日活跃度
cloud/map/size >= 0       # 预测源数据
ensemble >= cloud+map+size # 集成数据
union_v2 >= ensemble      # 联合数据v2
candidates >= 0           # 最终候选
```

#### 投票桶分布验证
```csv
# buckets_*.csv 格式
bucket_033, bucket_050, bucket_067, bucket_100, avg_n_sources

# 验证标准
总桶数 >= 3               # 投票桶充足
avg_n_sources >= 3        # 平均来源数充足
分布均匀性检查            # 避免单桶过度集中
```

#### KPI今日报告
```csv
# kpi_today_*.csv 格式
market, settled, coverage, accuracy, ev, ece, brier, wilson_low, wilson_high

# 验证标准
coverage: [0.25, 0.50]    # 目标覆盖率区间
accuracy >= 0.80          # 目标准确率
wilson_low >= 0.60        # Wilson置信下界
brier <= 0.25             # Brier分数上限
```

### 🚀 自动化收敛机制详细设计

#### 时间调度策略
```
每2分钟: 主系统tick执行
每5分钟: AutoSwitch智能自切检查
每15分钟: PI控制器参数调整
每1小时: 性能监控和报告
每日: 校准参数更新 (≥200样本时)
```

#### 收敛目标和路径
```
覆盖率收敛:
- 起点: 当前低覆盖率
- 路径: 降低accept_floor → 增加候选 → 提升覆盖率
- 终点: 逼近50% (天然封顶)

准确率收敛:
- 起点: 当前准确率水平
- 路径: 校准调整 → PI控制 → AutoSwitch微调
- 终点: 稳定在80%区间

风险控制:
- EV>0严格检查
- Kelly系数限制
- 回撤保护机制
- Guard锁定保护
```

### 🔄 Vertex批预测重启机制

#### C-SOP: 上游数据源修复
```bash
# 1. 找到最近成功的BatchPrediction配置
gcloud ai batch-predictions list --project=${PROJECT} --region=${BQLOC}
gcloud ai batch-predictions describe <job-name> --project=${PROJECT} --region=${BQLOC}

# 2. 导出今日缺口period的特征
WITH gap_periods AS (
  SELECT d.period 
  FROM draws_14w_dedup_v d 
  LEFT JOIN cloud_pred_today_norm p USING(period) 
  WHERE p.period IS NULL 
    AND DATE(d.timestamp,'Asia/Shanghai')=CURRENT_DATE('Asia/Shanghai')
)
SELECT period FROM gap_periods ORDER BY period;

# 3. 触发BatchPrediction
gcloud ai batch-predictions create \
  --project="${PROJECT}" --region="${BQLOC}" \
  --model="${VERTEX_MODEL}" \
  --display-name="pc28-batch-$(date +%F-%H%M)" \
  --input-config="gcsSource={uris=[\"${GCS_INPUT}\"]}" \
  --output-config="gcsDestination={outputUriPrefix=\"${GCS_OUTPUT}\"}"

# 4. 等待SUCCEEDED后BQ Load
# 5. 重新运行脚本恢复候选和覆盖率
```

### 📡 Telegram集成详细命令集

#### 完整命令列表
```
/kpi_today      - 今日KPI报告
/status         - 系统状态检查
/latest3        - 最近3期结果
/balance        - 资金平衡状态
/lock           - 系统锁定
/unlock         - 系统解锁
/mode           - 模式切换 (conservative/balanced/aggressive)
/boost_cov      - 覆盖率抬量
/boost_off      - 关闭抬量
/calibrate      - 触发校准
```

#### 命令执行流程
```
命令接收 → 调用对应脚本 → request_bridge写入请求文件 → 主系统消费 → 结果反馈
```

### 🛡️ 应急模式详细设计

#### 应急触发条件
```
1. 数据源健康检查失败
2. 连续多期无候选信号
3. 准确率跌破60%
4. 系统异常或错误
```

#### 应急模式动作
```sql
-- 应急模式表
CREATE TABLE runtime_modes (
  emergency BOOL,
  reason STRING,
  updated_at TIMESTAMP
);

-- 应急模式激活
INSERT INTO runtime_modes (emergency, reason, updated_at)
VALUES (TRUE, 'data_source_failure', CURRENT_TIMESTAMP());
```

#### 应急恢复机制
```
1. 数据源恢复检测
2. 自动清除应急标志
3. 系统状态恢复验证
4. 正常模式重新激活
```

### 📊 完整的监控和告警体系

#### 分级告警机制
```
CRITICAL: 系统停摆、数据中断、准确率<60%
HIGH:     覆盖率异常、模型性能下降
MEDIUM:   参数调整、模式切换
LOW:      日常状态更新
```

#### 告警处理流程
```
检测异常 → 分级评估 → 自动处置 → 通知相关人员 → 跟踪恢复
```

---

**4000行后的内容同样极其有价值！包含完整的运维工具集、自检验证、Vertex集成、应急处理等高级特性！** 📊

**所有细节已详细记录，确保这个高级系统的设计价值不被遗漏！** 🎯
