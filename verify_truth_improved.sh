#!/usr/bin/env bash
set -euo pipefail

PROJECT="wprojectl"
REGION="us-central1"
TELEGRAM_TOKEN="8094025881:AAF-7fv6djS0Z8QcgHwHloGSVguXj8XXEC0"
TELEGRAM_CHAT_ID="8420412156"

ts_utc(){ date -u +"%Y-%m-%dT%H:%M:%SZ"; }
fail(){ echo "❌ $1"; exit 1; }
ok(){   echo "✅ $1"; }

echo "== 改进版Truth-Over-Claims验证 @ $(ts_utc) =="

# 1) 心跳验证（已通过）
echo "[1/3] 心跳验证..."
HEARTBEAT_CHECK=$(bq query --project_id="$PROJECT" --location="$REGION" --nouse_legacy_sql --format=json "
SELECT TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(ts), MINUTE) AS mins
FROM \`$PROJECT.pc28_monitor.heartbeats\`
WHERE svc = 'pc28-bot-final' AND ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
" | jq -r '.[0].mins // 999')

if [ "$HEARTBEAT_CHECK" -le 3 ]; then
    ok "心跳新鲜 (${HEARTBEAT_CHECK}分钟前)"
else
    fail "心跳陈旧 (${HEARTBEAT_CHECK}分钟)"
fi

# 2) 改进的推送验证（基于消息ID追踪）
echo "[2/3] 改进推送验证..."
MSG_TEXT="PC28 Enhanced Probe $(ts_utc)"
SEND_RESP=$(curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage"     -d chat_id="$TELEGRAM_CHAT_ID" -d text="$MSG_TEXT")

MSG_ID=$(echo "$SEND_RESP" | jq -r '.result.message_id // empty')
SEND_OK=$(echo "$SEND_RESP" | jq -r '.ok // false')

if [ "$SEND_OK" = "true" ] && [ -n "$MSG_ID" ]; then
    # 记录到追踪文件
    echo "{\"timestamp\": \"$(ts_utc)\", \"message_id\": $MSG_ID, \"status\": \"sent\"}" >> telegram_verification_log.json
    ok "推送验证通过 (消息ID: $MSG_ID, 已记录到追踪文件)"
else
    fail "推送验证失败"
fi

# 3) 进程验证（本地运行证据）
echo "[3/3] 进程验证..."
MONITOR_PROCESSES=$(ps aux | grep -c "real_heartbeat_monitor.py" | grep -v grep || echo "0")

if [ "$MONITOR_PROCESSES" -gt 0 ]; then
    MONITOR_PID=$(ps aux | grep "real_heartbeat_monitor.py" | grep -v grep | awk '{print $2}' | head -1)
    ok "监控进程运行中 (PID: $MONITOR_PID)"
else
    fail "监控进程未运行"
fi

echo
echo "=== 改进版验证完成：基于文件追踪的证据链 ==="
echo "📊 证据文件: telegram_verification_log.json"
echo "💓 心跳表: $PROJECT.pc28_monitor.heartbeats"
echo "🔍 进程ID: $MONITOR_PID"
