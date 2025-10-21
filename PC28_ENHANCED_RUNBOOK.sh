#!/bin/bash
# PC28 Enhanced Operations Runbook
# 基于现有稳定化清单的增强版运维手册
# Version: 2.0 - 支持UPDATE分支、时区统一、Gate诊断

set -e

echo "🚀 PC28 Enhanced Operations Runbook"
echo "===================================="

# 配置区域
PROJECT_ID="wprojectl"
DATASET_PC28="pc28"
DATASET_LAB="pc28_lab"
WEBHOOK_URL=${PC28_WEBHOOK_URL:-""}

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# 1. 增强健康检查函数
health_check() {
    log "执行增强健康检查..."

    # 基础三表检查
    log "检查核心数据表..."
    bq query --use_legacy_sql=false --format=table "
    SELECT
        'draws_today_v2' AS view_name,
        COUNT(*) AS row_count,
        CASE WHEN COUNT(*) = 0 THEN '🔴 CRITICAL' ELSE '🟢 OK' END as status
    FROM \`$PROJECT_ID.$DATASET_PC28.draws_today_v2\`
    UNION ALL
    SELECT 'signal_pool_auto_v2', COUNT(*),
        CASE WHEN COUNT(*) = 0 THEN '🔴 CRITICAL' ELSE '🟢 OK' END
    FROM \`$PROJECT_ID.$DATASET_LAB.signal_pool_auto_v2\`
    UNION ALL
    SELECT 'consensus_candidates_api_v', COUNT(*),
        CASE WHEN COUNT(*) = 0 THEN '🔴 CRITICAL' ELSE '🟢 OK' END
    FROM \`$PROJECT_ID.$DATASET_PC28.consensus_candidates_api_v\`"

    # 重复期号检查
    log "检查重复期号..."
    DUPLICATE_COUNT=$(bq query --use_legacy_sql=false --format=csv "
    SELECT COUNT(*) AS dup_count FROM (
        SELECT issue FROM \`$PROJECT_ID.$DATASET_PC28.draws_14w\`
        WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
        GROUP BY issue HAVING COUNT(*) > 1
    )" | tail -1)

    if [ "$DUPLICATE_COUNT" -gt 0 ]; then
        error "发现 $DUPLICATE_COUNT 个重复期号"
    else
        log "重复期号检查: 🟢 正常"
    fi

    # 迟到数据检查
    log "检查迟到数据..."
    LATE_ARRIVALS=$(bq query --use_legacy_sql=false --format=csv "
    SELECT COUNT(*) AS late_arrivals FROM \`$PROJECT_ID.$DATASET_PC28.draws_14w\`
    WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 MINUTE)
        AND DATE(timestamp, 'Asia/Shanghai') < CURRENT_DATE('Asia/Shanghai')" | tail -1)

    if [ "$LATE_ARRIVALS" -gt 0 ]; then
        warn "发现 $LATE_ARRIVALS 条迟到数据"
    else
        log "迟到数据检查: 🟢 正常"
    fi

    # Gate输出检查
    log "检查Gate输出..."
    GATE_OUTPUT=$(bq query --use_legacy_sql=false --format=csv "
    SELECT COUNT(*) FROM \`$PROJECT_ID.$DATASET_PC28.consensus_gate_api_v\`" | tail -1)

    if [ "$GATE_OUTPUT" -eq 0 ]; then
        warn "Gate输出为0，可能需要调参"
    else
        log "Gate输出: 🟢 $GATE_OUTPUT 条"
    fi

    # 时区自检
    log "检查时区偏移..."
    OFFSET=$(bq query --use_legacy_sql=false --format=csv "
    SELECT ROUND(TIMESTAMP_DIFF(
        CURRENT_TIMESTAMP(),
        TIMESTAMP(DATETIME(CURRENT_DATETIME('Asia/Shanghai')), 'Asia/Shanghai'),
        MINUTE
    ), 0) AS offset_minute" | tail -1)

    if [ "$OFFSET" -ne 480 ] && [ "$OFFSET" -ne -480 ]; then
        error "时区偏移异常: ${OFFSET}分钟 (期望±480)"
    else
        log "时区偏移检查: 🟢 正常($OFFSET分钟)"
    fi
}

# 2. 增强MERGE同步（支持UPDATE+INSERT）
enhanced_merge_sync() {
    log "执行增强MERGE同步..."

    bq query --use_legacy_sql=false "
    MERGE \`$PROJECT_ID.$DATASET_PC28.draws_14w\` T
    USING (
        SELECT issue, timestamp, a, b, c, sum, tail, size, odd_even,
               EXTRACT(HOUR FROM DATETIME(timestamp, 'Asia/Shanghai')) AS hour,
               CASE WHEN EXTRACT(HOUR FROM DATETIME(timestamp, 'Asia/Shanghai')) BETWEEN 0 AND 12
                    THEN 'morning' ELSE 'afternoon' END AS session,
               source
        FROM \`$PROJECT_ID.$DATASET_PC28.draws_clean\`
        WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
    ) S
    ON T.issue = S.issue
    WHEN MATCHED AND TO_JSON_STRING(T) != TO_JSON_STRING(S) THEN
        UPDATE SET
            T.timestamp = S.timestamp, T.a = S.a, T.b = S.b, T.c = S.c,
            T.sum = S.sum, T.tail = S.tail, T.size = S.size, T.odd_even = S.odd_even,
            T.hour = S.hour, T.session = S.session, T.source = S.source
    WHEN NOT MATCHED THEN
        INSERT (issue, timestamp, a, b, c, sum, tail, size, odd_even, hour, session, source)
        VALUES (S.issue, S.timestamp, S.a, S.b, S.c, S.sum, S.tail, S.size, S.odd_even, S.hour, S.session, S.source);"

    AFFECTED_ROWS=$(bq query --use_legacy_sql=false --format=csv "
    SELECT COUNT(*) FROM \`$PROJECT_ID.$DATASET_PC28.draws_14w\`
    WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')" | tail -1)

    log "MERGE同步完成，当日数据: $AFFECTED_ROWS 行"
}

# 3. Gate诊断功能
gate_diagnosis() {
    log "执行Gate诊断..."

    bq query --use_legacy_sql=false --format=table "
    WITH candidates AS (
        SELECT * FROM \`$PROJECT_ID.$DATASET_PC28.consensus_candidates_api_v\`
    ),
    rules AS (
        SELECT c.*,
            -- 示例规则诊断（根据实际规则调整）
            (COALESCE(c.confidence, 0) >= 0.65) AS pass_conf,
            (COALESCE(c.voters_agree, 0) >= 3) AS pass_voters,
            (COALESCE(c.recent_hit_rate, 0.5) >= 0.55) AS pass_stability
        FROM candidates c
    )
    SELECT
        issue,
        confidence,
        voters_agree,
        recent_hit_rate,
        pass_conf,
        pass_voters,
        pass_stability,
        (pass_conf AND pass_voters AND pass_stability) AS pass_all
    FROM rules
    ORDER BY timestamp DESC
    LIMIT 10;"

    # 统计通过率
    PASS_RATE=$(bq query --use_legacy_sql=false --format=csv "
    WITH candidates AS (
        SELECT * FROM \`$PROJECT_ID.$DATASET_PC28.consensus_candidates_api_v\`
    ),
    rules AS (
        SELECT
            (COALESCE(confidence, 0) >= 0.65 AND
             COALESCE(voters_agree, 0) >= 3 AND
             COALESCE(recent_hit_rate, 0.5) >= 0.55) AS would_pass
        FROM candidates
    )
    SELECT ROUND(AVG(CASE WHEN would_pass THEN 1.0 ELSE 0.0 END) * 100, 2) as pass_rate
    FROM rules" | tail -1)

    log "Gate预期通过率: ${PASS_RATE}%"

    if (( $(echo "$PASS_RATE < 1" | bc -l) )); then
        warn "Gate通过率过低，建议调整阈值参数"
    fi
}

# 4. 数据清理（更精确的时间窗口）
precise_cleanup() {
    log "执行精确数据清理..."

    # 清理过期fallback数据（保留未来窗口）
    DELETED_COUNT=$(bq query --use_legacy_sql=false --format=csv "
    DELETE FROM \`$PROJECT_ID.$DATASET_LAB.signal_pool_fallback_today\`
    WHERE timestamp < CURRENT_TIMESTAMP();
    SELECT @@row_count as deleted_rows" | tail -1)

    log "清理过期fallback数据: $DELETED_COUNT 行"

    # 清理历史数据（保留24小时滑窗）
    if [ "$(date +%H)" -eq 1 ]; then  # 凌晨1点执行日清理
        log "执行日度数据清理..."
        bq query --use_legacy_sql=false "
        DELETE FROM \`$PROJECT_ID.$DATASET_LAB.signal_pool_fallback_today\`
        WHERE DATE(timestamp, 'Asia/Shanghai') < CURRENT_DATE('Asia/Shanghai');"
        log "历史数据清理完成"
    fi
}

# 5. 发送告警通知
send_alert() {
    local message="$1"
    local level="$2"  # INFO, WARN, ERROR

    if [ -n "$WEBHOOK_URL" ]; then
        curl -X POST "$WEBHOOK_URL" \
             -H "Content-Type: application/json" \
             -d "{\"text\":\"[$level] PC28: $message\", \"timestamp\":\"$(date -Iseconds)\"}" \
             -s -o /dev/null
    fi

    # 也记录到BigQuery告警表
    bq query --use_legacy_sql=false "
    INSERT INTO \`$PROJECT_ID.$DATASET_PC28.monitoring_alerts\`
    (alert_type, message, severity, timestamp)
    VALUES ('$level', '$message', '$level', CURRENT_TIMESTAMP());" || true
}

# 6. 应急恢复函数
emergency_recovery() {
    log "执行应急恢复程序..."

    # 检查关键表状态
    CRITICAL_ZERO=$(bq query --use_legacy_sql=false --format=csv "
    SELECT COUNT(*) as zero_tables FROM (
        SELECT COUNT(*) as cnt FROM \`$PROJECT_ID.$DATASET_PC28.draws_today_v2\`
        UNION ALL
        SELECT COUNT(*) FROM \`$PROJECT_ID.$DATASET_LAB.signal_pool_auto_v2\`
        UNION ALL
        SELECT COUNT(*) FROM \`$PROJECT_ID.$DATASET_PC28.consensus_candidates_api_v\`
    ) WHERE cnt = 0" | tail -1)

    if [ "$CRITICAL_ZERO" -gt 0 ]; then
        error "发现 $CRITICAL_ZERO 个关键表为空，启动应急恢复"
        send_alert "发现关键表为空，启动应急恢复程序" "ERROR"

        # 强制同步
        enhanced_merge_sync

        # 等待30秒后重新检查
        sleep 30
        health_check
    else
        log "系统状态正常，无需应急恢复"
    fi
}

# 主执行逻辑
main() {
    case "${1:-health}" in
        "health")
            health_check
            ;;
        "sync")
            enhanced_merge_sync
            ;;
        "diagnose")
            gate_diagnosis
            ;;
        "cleanup")
            precise_cleanup
            ;;
        "emergency")
            emergency_recovery
            ;;
        "full")
            log "执行完整运维检查..."
            health_check
            enhanced_merge_sync
            gate_diagnosis
            precise_cleanup
            log "完整运维检查完成"
            ;;
        *)
            echo "使用方法: $0 [health|sync|diagnose|cleanup|emergency|full]"
            echo ""
            echo "操作说明:"
            echo "  health    - 执行健康检查"
            echo "  sync      - 执行增强MERGE同步"
            echo "  diagnose  - Gate诊断分析"
            echo "  cleanup   - 精确数据清理"
            echo "  emergency - 应急恢复程序"
            echo "  full      - 执行完整运维流程"
            exit 1
            ;;
    esac
}

# 脚本入口点
main "$@"