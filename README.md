# PC28 Navigator - 独立项目

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


