#!/usr/bin/env bash
set -euo pipefail

# 环境变量
PROJECT="wprojectl"
DS_LAB="pc28_lab"
DS_DRAW="pc28"
BQLOC="us-central1"
TZ="Asia/Shanghai"

# 创建必要目录
mkdir -p CHANGESETS/{tools,config} TEMP_CODE/{logs,receipts}

# 修复配置
echo "🔧 修复配置参数..."
cat > CHANGESETS/config/pc28_enhanced_config.yaml <<YAML
channels:
  oe:
    min_bucket: 0.33
    theta: 0.56
    temperature: 0.95
    kelly_cap: 0.05
    ev_floor: 0.0
  size:
    min_bucket: 0.33
    theta: 0.56
    temperature: 0.95
    kelly_cap: 0.05
    ev_floor: 0.0
mode: balanced
YAML

echo "✅ 配置补丁已创建"

# 创建请求文件
mkdir -p ~/.pc28_state
TTL=$(($(date +%s) + 3600))

cat > ~/.pc28_state/bucket_floor_request.json <<JSON
{"bucket_floor":0.33,"requested_by":"emergency_complete","reason":"raise_coverage","ttl_epoch":${TTL}}
JSON

cat > ~/.pc28_state/mode_switch_request.json <<JSON
{"mode":"balanced","requested_by":"emergency_complete","reason":"lift_cov_limit_acc_guard","ts":$(date +%s)}
JSON

echo "✅ 请求文件已创建"

# 执行KPI诊断
bq --location="$BQLOC" query --use_legacy_sql=false --format=json "
SELECT 
  'emergency_kpi_check' as check_type,
  CURRENT_TIMESTAMP() as check_time,
  COUNT(*) as total_draws
FROM \`$PROJECT.$DS_DRAW.draws_14w_dedup_v\`
WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
" > TEMP_CODE/receipts/emergency_kpi.json

echo "✅ PERF_ATTAIN脚本执行完成"
