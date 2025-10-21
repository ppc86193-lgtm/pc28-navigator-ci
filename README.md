# PC28 Navigator - 独立项目

[![codecov](https://codecov.io/gh/ppc86193-lgtm/pc28-navigator-ci/branch/main/graph/badge.svg)](https://codecov.io/gh/ppc86193-lgtm/pc28-navigator-ci)

## 🧭 项目简介

**项目名称**: PC28 Navigator
**项目代码**: PC28-NAV
**核心功能**: 13个Agent + 1人工审批位的智能航管塔系统

## 🎯 核心价值

### 解决生产环境问题
- 🚨 **上游API同步中断** - 恢复数据流
- 🚨 **信号生成停摆** - 修复处理链路
- 🚨 **监控告警失效** - 重建监控体系

### 智能系统增强
- ⏰ **时间宪法** - 五种时间严格管理
- 🔧 **TDR机制** - 自动故障处置恢复
- 🤖 **AI路由** - 6个顶级模型智能调用
- ⚖️ **三权分立** - 量化/AI/人工职责分离

## 📁 项目结构

```
PC28_NAVIGATOR_CLEAN/
├── README.md                 # 本文档
├── navigator_core.py         # 核心系统(唯一实现文件)
├── config.yaml              # 配置文件
└── deployment/               # 部署相关
    ├── setup.sh             # 环境设置
    └── deploy.sh            # 部署脚本
```

### 服务与部署整合（本仓库）
- 统一服务入口：`cloud_app.py`
  - `GET /health?mode=basic|deep`
  - `GET /heartbeat`
  - `POST /push/kpi`, `POST /push/battle`
- 兼容层：`app.py`、`push_endpoints_app.py` 均改为转发 `cloud_app.app`
- AI 服务统一：使用 `ai_service.py`（FastAPI）；`ai_service_fixed.py`、`ai_service_complete.py` 改为导出 `ai_service.app` 的兼容层
- 部署命令统一：`python -m deploy.cli <subcommand>`
  - `prepare` | `cloudbuild` | `cloudbuild-fix` | `real` | `immediate` | `master`

### Agents 统一入口
- 通过通用 CLI 运行现有 Agent 脚本（无需修改脚本本身）：
```
python -m agents.cli run agent_exec          # 调用模块 main()
python -m agents.cli call agent_exec main    # 指定函数
```

### 归档
- 新建 `docs/archive/` 保存历史/演示/冗余配置文件，避免干扰主构建：
  - `cloudbuild.fixed.yaml`
  - `Dockerfile.training`, `Dockerfile.cloud`, `Dockerfile.fixed`
  - 其他演示脚本逐步迁移（详见 `docs/archive/README.md`）

#### 环境变量
- `GCP_PROJECT`/`GOOGLE_CLOUD_PROJECT`：GCP 项目（默认 `wprojectl`）
- `GCP_LOCATION`：区域（默认 `us-central1`）
- `HEARTBEAT_TABLE`：心跳表（默认 `wprojectl.pc28_monitor.heartbeats`）
- `DRAWS_VIEW`：开奖视图（默认 `wprojectl.pc28.draws_14w_dedup_v`）
- `KPI_TABLE`：KPI 表（默认 `wprojectl.pc28.kpi_daily_base`）
- `PUSH_LOGS_TABLE`：推送日志表（默认 `wprojectl.pc28_monitor.push_logs`）
- `FRESHNESS_MINUTES_OK`：数据新鲜阈值（默认 `60`）
- `DISABLE_PUSH`：为 `1` 时禁用 `/push/*` 端点

## 🚀 快速开始

1. **设置环境**
```bash
cd PC28_NAVIGATOR_CLEAN
bash deployment/setup.sh
```

2. **配置API密钥**
```bash
export AIML_API_KEY=your_key
export GOOGLE_CLOUD_PROJECT=wprojectl
```

3. **运行系统**
```bash
python3 navigator_core.py
```

---

**简洁、专注、避免混淆的独立Navigator项目**

## 🧪 运行测试

1. 创建并激活虚拟环境（可选）
```
python3 -m venv .venv
source .venv/bin/activate
```

2. 安装依赖并运行测试
```
./scripts/run_tests.sh
```

3. 可选：启用额外测试
- TurningPoint 算法测试依赖 `ruptures`，若未安装将自动跳过。
- MCP 错误用例仅在设置环境变量时运行：
```
# 一键运行（自动安装依赖、启动/回收 Mock 服务并运行测试）
./scripts/run_mcp_tests.sh
```

---

CI: 已启用 `ruff + black + isort + pytest`，以及所有 Dockerfile 的构建校验。
