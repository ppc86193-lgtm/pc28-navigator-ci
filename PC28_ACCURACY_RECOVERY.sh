#!/bin/bash
# PC28 准确率恢复一键脚本
# 零侵入设计：通过请求文件与主系统通信，不重启服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 确保状态目录存在
STATE_DIR="$HOME/.pc28_state"
mkdir -p "$STATE_DIR"

# 显示菜单
show_menu() {
    echo -e "\n${BLUE}=== PC28 准确率恢复控制面板 ===${NC}"
    echo "1) 🚨 启动准确率恢复 (Conservative + 0.67门槛)"
    echo "2) 📊 查看当前60分钟KPI状态"
    echo "3) ✅ 退出恢复模式 (回到Balanced)"
    echo "4) 🔄 立刻撤销门槛收紧"
    echo "5) 📋 查看当前系统状态"
    echo "6) 🤖 自动监控模式 (每3分钟检查KPI)"
    echo "0) 退出"
    echo -e "${BLUE}=======================================${NC}\n"
}

# Step A: 切换到Conservative模式
switch_to_conservative() {
    log_info "切换到Conservative模式（优先拉升准确率）..."

    cat > "$STATE_DIR/mode_switch_request.json" <<EOF
{"mode":"conservative","requested_by":"ops","reason":"recover_acc","ts":"$(date +%s)"}
EOF

    log_success "Conservative模式请求已写入：$STATE_DIR/mode_switch_request.json"
}

# Step B: 临时抬高接受门槛
raise_accept_floor() {
    log_info "临时抬高接受门槛到0.67（30分钟TTL）..."

    TTL=$(($(date +%s) + 30*60))
    cat > "$STATE_DIR/param_tweak_request.json" <<EOF
{"accept_floor":0.67,"ttl_epoch":$TTL,"requested_by":"ops","reason":"recover_acc"}
EOF

    log_success "门槛抬高请求已写入：$STATE_DIR/param_tweak_request.json"
    log_info "TTL到期时间：$(date -r $TTL)"
}

# Step C: 查看60分钟KPI
check_kpi() {
    log_info "查询最近60分钟KPI状态..."

    bq --location=us-central1 query --use_legacy_sql=false --format=prettyjson "
DECLARE since_ts TIMESTAMP DEFAULT TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 MINUTE);
WITH L AS (
  SELECT market,outcome,created_at
  FROM \`wprojectl.pc28_lab.score_ledger\`
  WHERE created_at >= since_ts AND (tag IS NULL OR tag='prod')
),
KPI AS (
  SELECT 'oe' market,
         COUNTIF(outcome IN ('win','lose')) n_set,
         COUNT(*) n_ord,
         SAFE_DIVIDE(COUNTIF(outcome='win'), NULLIF(COUNTIF(outcome IN ('win','lose')),0)) acc
  FROM L WHERE market='oe'
  UNION ALL
  SELECT 'size',
         COUNTIF(outcome IN ('win','lose')),
         COUNT(*),
         SAFE_DIVIDE(COUNTIF(outcome='win'), NULLIF(COUNTIF(outcome IN ('win','lose')),0))
  FROM L WHERE market='size'
)
SELECT
  market,
  n_set,
  n_ord,
  ROUND(acc * 100, 2) as accuracy_pct,
  ROUND(SAFE_DIVIDE(n_set, n_ord) * 100, 2) as coverage_pct,
  CASE
    WHEN acc >= 0.80 AND SAFE_DIVIDE(n_set, n_ord) >= 0.50 THEN 'PASS'
    WHEN acc >= 0.80 THEN 'ACC_OK_COV_LOW'
    WHEN SAFE_DIVIDE(n_set, n_ord) >= 0.50 THEN 'COV_OK_ACC_LOW'
    ELSE 'NEED_RECOVERY'
  END as status
FROM KPI
ORDER BY market;" 2>/dev/null || {
        log_error "BigQuery查询失败，请检查网络连接和认证状态"
        return 1
    }
}

# 退出到Balanced模式
switch_to_balanced() {
    log_info "切换回Balanced模式..."

    cat > "$STATE_DIR/mode_switch_request.json" <<EOF
{"mode":"balanced","requested_by":"ops","reason":"recover_done","ts":"$(date +%s)"}
EOF

    log_success "Balanced模式请求已写入"
}

# 立刻撤销门槛收紧
remove_floor_tweak() {
    log_info "撤销门槛收紧设置..."

    if [ -f "$STATE_DIR/param_tweak_request.json" ]; then
        rm -f "$STATE_DIR/param_tweak_request.json"
        log_success "门槛收紧请求文件已删除"
    else
        log_warn "门槛收紧文件不存在，可能已经被处理或过期"
    fi
}

# 查看系统状态
check_system_status() {
    log_info "当前系统状态："

    echo -e "\n📁 状态文件："
    ls -la "$STATE_DIR/" 2>/dev/null || log_warn "状态目录为空"

    if [ -f "$STATE_DIR/mode_switch_request.json" ]; then
        echo -e "\n🔄 模式切换请求："
        cat "$STATE_DIR/mode_switch_request.json" | python3 -m json.tool 2>/dev/null || cat "$STATE_DIR/mode_switch_request.json"
    fi

    if [ -f "$STATE_DIR/param_tweak_request.json" ]; then
        echo -e "\n🎛️ 参数调整请求："
        cat "$STATE_DIR/param_tweak_request.json" | python3 -m json.tool 2>/dev/null || cat "$STATE_DIR/param_tweak_request.json"

        # 检查TTL状态
        TTL=$(cat "$STATE_DIR/param_tweak_request.json" | python3 -c "import sys,json; print(json.load(sys.stdin)['ttl_epoch'])" 2>/dev/null || echo "0")
        if [ "$TTL" != "0" ] && [ "$TTL" -gt "$(date +%s)" ]; then
            log_info "TTL剩余时间：$((TTL - $(date +%s)))秒"
        elif [ "$TTL" != "0" ]; then
            log_warn "TTL已过期，参数应该已自动撤销"
        fi
    fi
}

# 自动监控模式
auto_monitor() {
    log_info "进入自动监控模式（每3分钟检查KPI，按Ctrl+C退出）"

    consecutive_pass=0
    required_pass=2

    trap 'log_info "自动监控已停止"; exit 0' INT

    while true; do
        log_info "执行KPI检查... ($(date))"

        # 检查KPI并解析结果
        kpi_result=$(bq --location=us-central1 query --use_legacy_sql=false --format=csv --quiet "
DECLARE since_ts TIMESTAMP DEFAULT TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 MINUTE);
WITH L AS (
  SELECT market,outcome,created_at
  FROM \`wprojectl.pc28_lab.score_ledger\`
  WHERE created_at >= since_ts AND (tag IS NULL OR tag='prod')
),
KPI AS (
  SELECT 'oe' market,
         COUNTIF(outcome IN ('win','lose')) n_set,
         COUNT(*) n_ord,
         SAFE_DIVIDE(COUNTIF(outcome='win'), NULLIF(COUNTIF(outcome IN ('win','lose')),0)) acc
  FROM L WHERE market='oe'
  UNION ALL
  SELECT 'size',
         COUNTIF(outcome IN ('win','lose')),
         COUNT(*),
         SAFE_DIVIDE(COUNTIF(outcome='win'), NULLIF(COUNTIF(outcome IN ('win','lose')),0))
  FROM L WHERE market='size'
)
SELECT
  COUNT(*) as pass_count
FROM KPI
WHERE acc >= 0.80 AND SAFE_DIVIDE(n_set, n_ord) >= 0.50;" 2>/dev/null)

        # 解析通过的通道数量
        pass_count=$(echo "$kpi_result" | tail -n1 | tr -d '\r\n')

        if [ "$pass_count" = "2" ]; then
            consecutive_pass=$((consecutive_pass + 1))
            log_success "✅ 两通道都达标！连续成功次数：$consecutive_pass/$required_pass"

            if [ $consecutive_pass -ge $required_pass ]; then
                log_success "🎉 连续$required_pass次达标，自动退出恢复模式！"
                switch_to_balanced
                remove_floor_tweak
                log_success "✅ 准确率恢复完成，系统已切回Balanced模式"
                break
            fi
        else
            consecutive_pass=0
            log_warn "⚠️ 仍有通道未达标，继续恢复中...（达标通道：$pass_count/2）"
        fi

        log_info "等待3分钟后继续检查..."
        sleep 180
    done
}

# 一键启动完整恢复流程
start_recovery() {
    log_info "🚨 启动准确率恢复流程..."

    switch_to_conservative
    sleep 1
    raise_accept_floor

    log_success "✅ 恢复流程已启动！"
    echo -e "\n${YELLOW}当前设置：${NC}"
    echo "• 模式：Conservative (优先准确率)"
    echo "• 接受门槛：0.67 (30分钟TTL)"
    echo "• 目标：双通道ACC≥80% 且 COV≥50%"

    echo -e "\n${BLUE}建议：${NC}"
    echo "1. 等待5-10分钟让设置生效"
    echo "2. 使用选项2查看KPI变化"
    echo "3. 达标后使用选项3退出恢复模式"
    echo "4. 或使用选项6进入自动监控模式"
}

# 主程序
main() {
    while true; do
        show_menu
        read -p "请选择操作 [0-6]: " choice

        case $choice in
            1)
                start_recovery
                ;;
            2)
                check_kpi
                ;;
            3)
                switch_to_balanced
                ;;
            4)
                remove_floor_tweak
                ;;
            5)
                check_system_status
                ;;
            6)
                auto_monitor
                ;;
            0)
                log_info "退出程序"
                exit 0
                ;;
            *)
                log_error "无效选择，请重新输入"
                ;;
        esac

        echo -e "\n按Enter键继续..."
        read
    done
}

# 如果直接执行脚本，显示使用说明
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    echo -e "${GREEN}PC28 准确率恢复工具${NC}"
    echo "使用方法："
    echo "  $0                    # 交互式菜单"
    echo "  $0 start             # 直接启动恢复"
    echo "  $0 check             # 查看KPI"
    echo "  $0 stop              # 停止恢复"
    echo "  $0 monitor           # 自动监控"
    echo ""

    case "${1:-menu}" in
        start)
            start_recovery
            ;;
        check)
            check_kpi
            ;;
        stop)
            switch_to_balanced
            remove_floor_tweak
            ;;
        monitor)
            auto_monitor
            ;;
        menu|*)
            main
            ;;
    esac
fi