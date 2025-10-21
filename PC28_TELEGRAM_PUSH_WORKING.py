#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PC28 Telegram 推送工作版本 - 修复实时推送问题
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
        """获取最新开奖结果"""
        try:
            query = """
            SELECT
                issue,
                FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', timestamp, 'Asia/Shanghai') as timestamp,
                a, b, c, sum, tail, size, odd_even
            FROM `wprojectl.pc28.draws_clean`
            WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            ORDER BY timestamp DESC
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
                return data[0] if data else None
            else:
                logger.warning("BigQuery查询返回空结果")
                return None

        except Exception as e:
            logger.error(f"获取开奖数据失败: {e}")
            return None

    def get_next_predictions(self):
        """获取下期预测结果"""
        try:
            # 获取最新开奖期号，计算下期
            latest_query = """
            SELECT
                CAST(REGEXP_EXTRACT(issue, r'(\\d+)$') AS INT64) as current_period
            FROM `wprojectl.pc28.draws_clean`
            WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            ORDER BY timestamp DESC
            LIMIT 1
            """

            cmd = [
                "bq",
                "query",
                "--use_legacy_sql=false",
                "--format=csv",
                "--quiet",
                latest_query,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if not result.stdout.strip():
                return []

            lines = result.stdout.strip().split("\n")
            if len(lines) < 2:
                return []

            current_period = int(lines[1].strip())
            next_period = current_period + 1

            # 构建下期期号
            today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")
            next_issue = f"{today}{next_period:03d}"

            # 获取大小预测
            size_query = f"""
            SELECT
                '{next_issue}' as issue,
                'size' as type,
                CASE WHEN prediction_big >= 0.5 THEN '大' ELSE '小' END as prediction,
                prediction_big as confidence,
                'pred_size_simple' as model,
                FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', timestamp, 'Asia/Shanghai') as timestamp
            FROM `wprojectl.pc28.pred_size_simple`
            ORDER BY timestamp DESC
            LIMIT 1
            """

            cmd = [
                "bq",
                "query",
                "--use_legacy_sql=false",
                "--format=json",
                "--quiet",
                size_query,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if result.stdout.strip():
                data = json.loads(result.stdout)
                return data
            else:
                return []

        except Exception as e:
            logger.error(f"获取预测数据失败: {e}")
            return []

    def get_model_predictions_summary(self):
        """获取今日模型预测汇总"""
        try:
            query = """
            SELECT
                model_id,
                COUNT(*) as prediction_count,
                AVG(prediction_big) as avg_confidence,
                FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', MAX(prediction_timestamp), 'Asia/Shanghai') as latest_prediction
            FROM `wprojectl.pc28.model_predictions`
            WHERE DATE(prediction_timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            GROUP BY model_id
            ORDER BY avg_confidence DESC
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
            else:
                return []

        except Exception as e:
            logger.error(f"获取模型汇总失败: {e}")
            return []

    def format_draw_message(self, draw_data):
        """格式化开奖消息"""
        if not draw_data:
            return None

        beijing_time = datetime.now(timezone(timedelta(hours=8)))
        time_str = beijing_time.strftime("%H:%M:%S")

        # 预测状态图标
        size_icon = "🔴" if draw_data.get("size") == "large" else "🟢"
        oddeven_icon = "🔸" if draw_data.get("odd_even") == "odd" else "🔹"

        # 转换显示名称
        size_cn = "大" if draw_data.get("size") == "large" else "小"
        oddeven_cn = "奇" if draw_data.get("odd_even") == "odd" else "偶"

        message = f"""🎯 *PC28开奖结果* #{draw_data.get('issue', '')}

⏰ 开奖时间: `{draw_data.get('timestamp', time_str)}`
🎲 开奖号码: `{draw_data.get('a', 0)} + {draw_data.get('b', 0)} + {draw_data.get('c', 0)} = {draw_data.get('sum', 0)}`

📊 *结果分析*:
{size_icon} 大小: *{size_cn}* (和值{draw_data.get('sum', 0)})
{oddeven_icon} 单双: *{oddeven_cn}* (尾数{draw_data.get('tail', 0)})

━━━━━━━━━━━━━━━━━
📈 下期预测分析即将发布..."""

        return message

    def format_prediction_message(self, predictions_data):
        """格式化预测消息"""
        if not predictions_data:
            return "⚠️ 暂无下期预测数据"

        beijing_time = datetime.now(timezone(timedelta(hours=8)))
        time_str = beijing_time.strftime("%H:%M:%S")

        pred = predictions_data[0]  # 取第一条预测
        next_issue = pred.get("issue", "未知")

        confidence = float(pred.get("confidence", 0))
        prediction = pred.get("prediction", "")

        # 处理置信度显示
        if prediction == "大":
            actual_confidence = confidence
        else:
            actual_confidence = 1.0 - confidence

        confidence_icon = (
            "🟢"
            if actual_confidence >= 0.7
            else "🟡" if actual_confidence >= 0.6 else "🔴"
        )

        message = f"""🔮 *PC28预测分析* #{next_issue}

⏰ 分析时间: `{time_str}`

📏 *大小预测*: {confidence_icon}
预测结果: *{prediction}*
置信度: `{actual_confidence:.1%}`
数据源: {pred.get('model', '')}
更新时间: `{pred.get('timestamp', '')}`

━━━━━━━━━━━━━━━━━
⚠️ 预测仅供参考，请理性投注"""

        return message

    def format_model_summary(self, model_data):
        """格式化模型汇总"""
        if not model_data:
            return None

        beijing_time = datetime.now(timezone(timedelta(hours=8)))
        time_str = beijing_time.strftime("%H:%M:%S")

        total_models = len(model_data)
        total_predictions = sum(int(m.get("prediction_count", 0)) for m in model_data)

        message = f"""📊 *PC28模型状态汇总*

⏰ 更新时间: `{time_str}`

🤖 *今日统计*:
• 活跃模型: `{total_models}个`
• 预测总数: `{total_predictions}条`

🎯 *模型表现* (按置信度排序):
"""

        for i, model in enumerate(model_data[:5], 1):
            confidence = float(model.get("avg_confidence", 0))
            prediction_text = "偏向大" if confidence >= 0.5 else "偏向小"
            count = model.get("prediction_count", 0)

            message += f"• {model.get('model_id')}: {prediction_text} ({confidence:.1%}) - {count}条\n"

        message += """
━━━━━━━━━━━━━━━━━
📈 基于历史数据的AI预测分析"""

        return message

    def push_latest_draw(self):
        """推送最新开奖结果"""
        logger.info("开始推送最新开奖结果...")

        draw_data = self.get_latest_draw()
        if not draw_data:
            logger.warning("无法获取开奖数据")
            return False

        message = self.format_draw_message(draw_data)
        if not message:
            logger.warning("无法格式化开奖消息")
            return False

        return self.send_message(message)

    def push_next_predictions(self):
        """推送下期预测结果"""
        logger.info("开始推送下期预测结果...")

        predictions_data = self.get_next_predictions()
        message = self.format_prediction_message(predictions_data)

        if not message:
            logger.warning("无法格式化预测消息")
            return False

        return self.send_message(message)

    def push_model_summary(self):
        """推送模型汇总"""
        logger.info("开始推送模型汇总...")

        model_data = self.get_model_predictions_summary()
        if not model_data:
            logger.warning("无法获取模型数据")
            return False

        message = self.format_model_summary(model_data)
        if not message:
            logger.warning("无法格式化模型汇总消息")
            return False

        return self.send_message(message)

    def push_complete_analysis(self):
        """推送完整分析"""
        logger.info("开始推送完整分析...")

        results = []

        print("📊 推送最新开奖结果...")
        success1 = self.push_latest_draw()
        results.append(success1)
        time.sleep(3)

        print("🔮 推送下期预测...")
        success2 = self.push_next_predictions()
        results.append(success2)
        time.sleep(3)

        print("🤖 推送模型汇总...")
        success3 = self.push_model_summary()
        results.append(success3)

        success_count = sum(results)
        print(f"✅ 完整分析推送完成: {success_count}/3 成功")

        return success_count == 3


def main():
    pusher = PC28TelegramPusher()

    print("🎯 PC28 Telegram推送工具 - 修复版")
    print("=" * 40)
    print("1) 📊 推送最新开奖结果")
    print("2) 🔮 推送下期预测结果")
    print("3) 🤖 推送模型预测汇总")
    print("4) 🎯 完整分析推送")
    print("5) 🔄 测试连接")
    print("=" * 40)

    try:
        choice = input("请选择功能 [1-5]: ").strip()

        if choice == "1":
            success = pusher.push_latest_draw()
            print("✅ 开奖结果推送成功" if success else "❌ 开奖结果推送失败")

        elif choice == "2":
            success = pusher.push_next_predictions()
            print("✅ 预测结果推送成功" if success else "❌ 预测结果推送失败")

        elif choice == "3":
            success = pusher.push_model_summary()
            print("✅ 模型汇总推送成功" if success else "❌ 模型汇总推送失败")

        elif choice == "4":
            success = pusher.push_complete_analysis()
            print("✅ 完整分析推送成功" if success else "❌ 部分推送失败")

        elif choice == "5":
            # 测试连接
            test_msg = f"🔧 PC28系统连接测试\n\n⏰ 测试时间: {datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')}\n📡 系统状态: 正常"
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
