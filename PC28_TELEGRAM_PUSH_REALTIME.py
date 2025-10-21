#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PC28 Telegram 实时推送修复版本
解决时间显示和数据获取问题
"""

import json
import logging
import subprocess
import time
from datetime import datetime, timedelta, timezone

import requests

# 配置
BOT_TOKEN = "8094025881:AAF-7fv6djS0Z8QcgHwHloGSVguXj8XXEC0"
CHAT_ID = "8420412156"

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PC28TelegramPusher:
    def __init__(self):
        self.bot_token = BOT_TOKEN
        self.chat_id = CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """发送消息到Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode}

            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()

            logger.info(f"消息发送成功: {response.status_code}")
            return True

        except Exception as e:
            logger.error(f"消息发送失败: {e}")
            return False

    def get_latest_draw(self):
        """获取最新开奖结果 - 使用实际时间"""
        try:
            query = """
            SELECT
                issue,
                a, b, c, sum, tail, size, odd_even,
                -- 不使用存储的timestamp，使用当前时间作为参考
                CURRENT_TIMESTAMP() as query_time
            FROM `wprojectl.pc28.draws_clean`
            WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            ORDER BY CAST(REGEXP_EXTRACT(issue, r'(\\d+)$') AS INT64) DESC
            LIMIT 1
            """

            cmd = [
                "bq",
                "query",
                "--use_legacy_sql=false",
                "--format=json",
                "--quiet",
                query,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if result.stdout.strip():
                data = json.loads(result.stdout)
                if data:
                    draw = data[0]
                    # 手动添加当前时间作为显示时间
                    draw["display_time"] = datetime.now(
                        timezone(timedelta(hours=8))
                    ).strftime("%Y-%m-%d %H:%M:%S")
                    return draw

            return None

        except Exception as e:
            logger.error(f"获取开奖数据失败: {e}")
            return None

    def get_prediction_status(self):
        """获取预测系统状态"""
        try:
            query = """
            SELECT
                COUNT(*) as total_predictions,
                COUNT(DISTINCT model_id) as active_models,
                FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', MAX(prediction_timestamp), 'Asia/Shanghai') as latest_prediction_time,
                TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(prediction_timestamp), MINUTE) as minutes_since_last_prediction
            FROM `wprojectl.pc28.model_predictions`
            WHERE DATE(prediction_timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            """

            cmd = [
                "bq",
                "query",
                "--use_legacy_sql=false",
                "--format=json",
                "--quiet",
                query,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if result.stdout.strip():
                data = json.loads(result.stdout)
                return data[0] if data else None

            return None

        except Exception as e:
            logger.error(f"获取预测状态失败: {e}")
            return None

    def get_recent_model_performance(self):
        """获取最近模型表现（基于修复后的清洁数据）"""
        try:
            query = """
            WITH recent_predictions AS (
              SELECT
                model_id,
                CAST(period AS STRING) as period_str,
                CASE WHEN prediction_big >= 0.5 THEN 'large' ELSE 'small' END as predicted_size
              FROM `wprojectl.pc28.model_predictions`
              WHERE DATE(prediction_timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            ),
            actual_results AS (
              SELECT
                issue,
                size as actual_size
              FROM `wprojectl.pc28_lab.draws_14w_clean`  -- 使用修复后的清洁数据
              WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            )
            SELECT
              rp.model_id,
              COUNT(*) as total_predictions,
              SUM(CASE WHEN rp.predicted_size = ar.actual_size THEN 1 ELSE 0 END) as correct_predictions,
              SAFE_DIVIDE(SUM(CASE WHEN rp.predicted_size = ar.actual_size THEN 1 ELSE 0 END), COUNT(*)) as accuracy_rate
            FROM recent_predictions rp
            LEFT JOIN actual_results ar ON rp.period_str = ar.issue
            WHERE ar.actual_size IS NOT NULL
            GROUP BY rp.model_id
            ORDER BY accuracy_rate DESC
            """

            cmd = [
                "bq",
                "query",
                "--use_legacy_sql=false",
                "--format=json",
                "--quiet",
                query,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if result.stdout.strip():
                data = json.loads(result.stdout)
                return data

            return []

        except Exception as e:
            logger.error(f"获取模型表现失败: {e}")
            return []

    def format_draw_message(self, draw_data):
        """格式化开奖消息"""
        if not draw_data:
            return None

        current_time = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")

        # 预测状态图标
        size_icon = "🔴" if draw_data.get("size") == "large" else "🟢"
        oddeven_icon = "🔸" if draw_data.get("odd_even") == "odd" else "🔹"

        # 转换显示名称
        size_cn = "大" if draw_data.get("size") == "large" else "小"
        oddeven_cn = "奇" if draw_data.get("odd_even") == "odd" else "偶"

        message = f"""🎯 *PC28开奖结果* #{draw_data.get('issue', '')}

⏰ 推送时间: `{current_time}`
🎲 开奖号码: `{draw_data.get('a', 0)} + {draw_data.get('b', 0)} + {draw_data.get('c', 0)} = {draw_data.get('sum', 0)}`

📊 *结果分析*:
{size_icon} 大小: *{size_cn}* (和值{draw_data.get('sum', 0)})
{oddeven_icon} 单双: *{oddeven_cn}* (尾数{draw_data.get('tail', 0)})

━━━━━━━━━━━━━━━━━
📈 预测系统状态检查中..."""

        return message

    def format_prediction_status_message(self, status_data):
        """格式化预测系统状态消息"""
        if not status_data:
            return "⚠️ 无法获取预测系统状态"

        current_time = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")

        total_preds = status_data.get("total_predictions", 0)
        active_models = status_data.get("active_models", 0)
        last_pred_time = status_data.get("latest_prediction_time", "未知")
        minutes_ago = status_data.get("minutes_since_last_prediction", 0)

        # 根据预测更新时间判断状态
        minutes_ago = int(minutes_ago) if minutes_ago else 9999
        if minutes_ago <= 30:
            status_icon = "🟢"
            status_text = "正常运行"
        elif minutes_ago <= 120:
            status_icon = "🟡"
            status_text = "轻微延迟"
        else:
            status_icon = "🔴"
            status_text = "需要检查"

        message = f"""🔮 *PC28预测系统状态*

⏰ 检查时间: `{current_time}`
📡 系统状态: {status_icon} *{status_text}*

📊 *今日统计*:
• 预测总数: `{total_preds}条`
• 活跃模型: `{active_models}个`
• 最后更新: `{last_pred_time}`
• 距离上次更新: `{minutes_ago}分钟`

━━━━━━━━━━━━━━━━━
{"⚠️ 预测系统超过2小时未更新，请检查" if minutes_ago > 120 else "✅ 预测系统运行正常"}"""

        return message

    def format_model_performance_message(self, performance_data):
        """格式化模型表现消息"""
        if not performance_data:
            return "⚠️ 暂无模型表现数据"

        current_time = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")

        message = f"""📊 *PC28模型今日表现*

⏰ 统计时间: `{current_time}`

🏆 *准确率排行*:
"""

        for i, model in enumerate(performance_data[:5], 1):
            model_id = model.get("model_id", "unknown")
            total_preds = int(model.get("total_predictions", 0))
            correct_preds = int(model.get("correct_predictions", 0))
            accuracy = float(model.get("accuracy_rate", 0))

            # 根据准确率设置图标
            if accuracy >= 0.65:
                perf_icon = "🥇"
            elif accuracy >= 0.60:
                perf_icon = "🥈"
            elif accuracy >= 0.55:
                perf_icon = "🥉"
            else:
                perf_icon = "📊"

            message += f"{perf_icon} *{model_id}*: {accuracy:.1%} ({correct_preds}/{total_preds})\n"

        message += """
━━━━━━━━━━━━━━━━━
📈 基于今日实际开奖结果统计"""

        return message

    def push_latest_draw(self):
        """推送最新开奖结果"""
        logger.info("开始推送最新开奖结果...")

        draw_data = self.get_latest_draw()
        if not draw_data:
            return False

        message = self.format_draw_message(draw_data)
        return self.send_message(message)

    def push_prediction_status(self):
        """推送预测系统状态"""
        logger.info("开始推送预测系统状态...")

        status_data = self.get_prediction_status()
        message = self.format_prediction_status_message(status_data)
        return self.send_message(message)

    def push_model_performance(self):
        """推送模型表现"""
        logger.info("开始推送模型表现...")

        performance_data = self.get_recent_model_performance()
        message = self.format_model_performance_message(performance_data)
        return self.send_message(message)

    def push_system_status(self):
        """推送完整系统状态"""
        logger.info("开始推送系统状态...")

        results = []

        print("📊 推送最新开奖...")
        success1 = self.push_latest_draw()
        results.append(success1)
        time.sleep(2)

        print("🔮 推送预测状态...")
        success2 = self.push_prediction_status()
        results.append(success2)
        time.sleep(2)

        print("🏆 推送模型表现...")
        success3 = self.push_model_performance()
        results.append(success3)

        success_count = sum(results)
        print(f"✅ 系统状态推送完成: {success_count}/3 成功")

        return success_count >= 2  # 至少2个成功就算成功


def main():
    pusher = PC28TelegramPusher()

    print("🎯 PC28 实时推送系统 - 修复版")
    print("=" * 40)
    print("1) 📊 推送最新开奖结果")
    print("2) 🔮 推送预测系统状态")
    print("3) 🏆 推送模型表现")
    print("4) 🎯 推送完整系统状态")
    print("5) 🔧 连接测试")
    print("=" * 40)

    try:
        choice = input("请选择功能 [1-5]: ").strip()

        if choice == "1":
            success = pusher.push_latest_draw()
            print("✅ 开奖推送成功" if success else "❌ 开奖推送失败")

        elif choice == "2":
            success = pusher.push_prediction_status()
            print("✅ 预测状态推送成功" if success else "❌ 预测状态推送失败")

        elif choice == "3":
            success = pusher.push_model_performance()
            print("✅ 模型表现推送成功" if success else "❌ 模型表现推送失败")

        elif choice == "4":
            success = pusher.push_system_status()
            print("✅ 系统状态推送成功" if success else "❌ 系统状态推送失败")

        elif choice == "5":
            test_msg = f"""🔧 *PC28系统连接测试*

⏰ 测试时间: `{datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')}`
📡 连接状态: ✅ *正常*
🔄 推送功能: ✅ *工作中*

━━━━━━━━━━━━━━━━━
📊 系统准备就绪"""
            success = pusher.send_message(test_msg)
            print("✅ 连接测试成功" if success else "❌ 连接测试失败")

        else:
            print("❌ 无效选择")

    except KeyboardInterrupt:
        print("\n👋 用户中断操作")
    except Exception as e:
        print(f"❌ 程序异常: {e}")


if __name__ == "__main__":
    main()
