#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PC28 Telegram 推送最终版本
完整支持开奖结果和预测结果推送
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

    def get_latest_predictions(self):
        """获取最新预测结果"""
        try:
            # 获取大小预测
            size_query = """
            SELECT
                issue,
                big_probability,
                predicted_size,
                FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', timestamp, 'Asia/Shanghai') as timestamp
            FROM `wprojectl.pc28.pred_size_simple`
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
                size_query,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            size_pred = None
            if result.stdout.strip():
                size_data = json.loads(result.stdout)
                if size_data:
                    size_pred = {
                        "issue": size_data[0].get("issue"),
                        "type": "size",
                        "prediction": (
                            "大"
                            if size_data[0].get("predicted_size") == "big"
                            else "小"
                        ),
                        "confidence": float(size_data[0].get("big_probability", 0)),
                        "model": "pred_size_simple",
                        "timestamp": size_data[0].get("timestamp"),
                    }

            # 获取单双预测
            oddeven_query = """
            SELECT
                issue,
                odd_probability,
                predicted_oddeven,
                FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', timestamp, 'Asia/Shanghai') as timestamp
            FROM `wprojectl.pc28.pred_oddeven_simple`
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
                oddeven_query,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            oddeven_pred = None
            if result.stdout.strip():
                oddeven_data = json.loads(result.stdout)
                if oddeven_data:
                    oddeven_pred = {
                        "issue": oddeven_data[0].get("issue"),
                        "type": "odd_even",
                        "prediction": (
                            "奇"
                            if oddeven_data[0].get("predicted_oddeven") == "odd"
                            else "偶"
                        ),
                        "confidence": float(oddeven_data[0].get("odd_probability", 0)),
                        "model": "pred_oddeven_simple",
                        "timestamp": oddeven_data[0].get("timestamp"),
                    }

            # 组合结果
            predictions = []
            if size_pred:
                predictions.append(size_pred)
            if oddeven_pred:
                predictions.append(oddeven_pred)

            return predictions

        except Exception as e:
            logger.error(f"获取预测数据失败: {e}")
            return []

    def get_model_predictions(self):
        """获取模型预测数据"""
        try:
            query = """
            SELECT
                model_id,
                period,
                prediction_big,
                FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', prediction_timestamp, 'Asia/Shanghai') as timestamp
            FROM `wprojectl.pc28.model_predictions`
            WHERE DATE(prediction_timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            ORDER BY prediction_timestamp DESC
            LIMIT 5
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
            logger.error(f"获取模型预测失败: {e}")
            return []

    def format_draw_message(self, draw_data):
        """格式化开奖消息"""
        if not draw_data:
            return None

        # 预测状态图标
        size_icon = "🔴" if draw_data.get("size") == "large" else "🟢"
        oddeven_icon = "🔸" if draw_data.get("odd_even") == "odd" else "🔹"

        # 转换显示名称
        size_cn = "大" if draw_data.get("size") == "large" else "小"
        oddeven_cn = "奇" if draw_data.get("odd_even") == "odd" else "偶"

        message = f"""🎯 *PC28开奖结果* #{draw_data.get('issue', '')}

⏰ 开奖时间: `{draw_data.get('timestamp', '')}`
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
            return "⚠️ 暂无预测数据"

        beijing_time = datetime.now(timezone(timedelta(hours=8)))
        time_str = beijing_time.strftime("%H:%M:%S")

        # 获取下期期号 - 基于最新的预测数据
        next_issue = (
            predictions_data[0].get("issue", "未知") if predictions_data else "未知"
        )

        message = f"""🔮 *PC28预测分析* #{next_issue}

⏰ 分析时间: `{time_str}`

"""

        # 处理预测数据
        for pred in predictions_data:
            if pred.get("type") == "size":
                confidence = pred.get("confidence", 0)
                # 大小预测的置信度处理
                if pred.get("prediction") == "大":
                    actual_confidence = confidence
                else:
                    actual_confidence = 1.0 - confidence

                confidence_icon = (
                    "🟢"
                    if actual_confidence >= 0.7
                    else "🟡" if actual_confidence >= 0.6 else "🔴"
                )

                message += f"""📏 *大小预测*: {confidence_icon}
预测结果: *{pred.get('prediction', '')}*
置信度: `{actual_confidence:.1%}`
模型: {pred.get('model', '')}

"""

            elif pred.get("type") == "odd_even":
                confidence = pred.get("confidence", 0)
                # 单双预测的置信度处理
                if pred.get("prediction") == "奇":
                    actual_confidence = confidence
                else:
                    actual_confidence = 1.0 - confidence

                confidence_icon = (
                    "🟢"
                    if actual_confidence >= 0.7
                    else "🟡" if actual_confidence >= 0.6 else "🔴"
                )

                message += f"""🎯 *单双预测*: {confidence_icon}
预测结果: *{pred.get('prediction', '')}*
置信度: `{actual_confidence:.1%}`
模型: {pred.get('model', '')}

"""

        message += """━━━━━━━━━━━━━━━━━
⚠️ 预测仅供参考，请理性投注"""

        return message

    def format_model_summary_message(self, model_data):
        """格式化模型汇总消息"""
        if not model_data:
            return None

        beijing_time = datetime.now(timezone(timedelta(hours=8)))
        time_str = beijing_time.strftime("%H:%M:%S")

        message = f"""📊 *PC28模型预测汇总*

⏰ 更新时间: `{time_str}`

"""

        # 统计模型预测
        model_count = len(set(item.get("model_id") for item in model_data))
        avg_prediction = sum(
            float(item.get("prediction_big", 0)) for item in model_data
        ) / len(model_data)

        big_count = sum(
            1 for item in model_data if float(item.get("prediction_big", 0)) >= 0.5
        )
        small_count = len(model_data) - big_count

        message += f"""🤖 *活跃模型*: `{model_count}个`

🔢 *预测统计*:
• 预测"大": `{big_count}个模型`
• 预测"小": `{small_count}个模型`
• 平均置信度: `{avg_prediction:.1%}`

"""

        # 显示前3个模型的详细预测
        message += "🎯 *模型详情*:\n"
        for i, model in enumerate(model_data[:3]):
            prediction_text = (
                "大" if float(model.get("prediction_big", 0)) >= 0.5 else "小"
            )
            confidence = float(model.get("prediction_big", 0))
            actual_conf = confidence if prediction_text == "大" else 1.0 - confidence

            message += (
                f"• {model.get('model_id')}: {prediction_text} ({actual_conf:.1%})\n"
            )

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

    def push_latest_predictions(self):
        """推送最新预测结果"""
        logger.info("开始推送最新预测结果...")

        predictions_data = self.get_latest_predictions()

        message = self.format_prediction_message(predictions_data)
        if not message:
            logger.warning("无法格式化预测消息")
            return False

        return self.send_message(message)

    def push_model_summary(self):
        """推送模型预测汇总"""
        logger.info("开始推送模型预测汇总...")

        model_data = self.get_model_predictions()
        if not model_data:
            logger.warning("无法获取模型数据")
            return False

        message = self.format_model_summary_message(model_data)
        if not message:
            logger.warning("无法格式化模型汇总消息")
            return False

        return self.send_message(message)

    def push_system_alert(
        self, alert_type: str, alert_message: str, severity: str = "INFO"
    ):
        """推送系统告警"""
        severity_icons = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "🚨", "CRITICAL": "🔥"}

        icon = severity_icons.get(severity, "ℹ️")
        beijing_time = datetime.now(timezone(timedelta(hours=8)))
        time_str = beijing_time.strftime("%H:%M:%S")

        message = f"""{icon} *PC28系统告警*

⏰ 告警时间: `{time_str}`
🏷️ 告警类型: `{alert_type}`
📢 严重程度: `{severity}`

📋 *告警详情*:
{alert_message}

━━━━━━━━━━━━━━━━━
🔧 请及时检查系统状态"""

        return self.send_message(message)

    def push_complete_analysis(self):
        """推送完整分析（开奖+预测+模型）"""
        logger.info("开始推送完整分析...")

        # 推送开奖结果
        print("📊 推送开奖结果...")
        success1 = self.push_latest_draw()
        time.sleep(3)

        # 推送预测分析
        print("🔮 推送预测分析...")
        success2 = self.push_latest_predictions()
        time.sleep(3)

        # 推送模型汇总
        print("🤖 推送模型汇总...")
        success3 = self.push_model_summary()

        results = [success1, success2, success3]
        success_count = sum(results)

        print(f"✅ 完整分析推送完成: {success_count}/3 成功")
        return success_count == 3


def main():
    pusher = PC28TelegramPusher()

    print("🎯 PC28 Telegram推送工具 - 最终版")
    print("=" * 40)
    print("1) 📊 推送最新开奖结果")
    print("2) 🔮 推送最新预测结果")
    print("3) 🤖 推送模型预测汇总")
    print("4) 🚨 发送测试告警")
    print("5) 🎯 完整分析推送(开奖+预测+模型)")
    print("6) 🔄 自动监控模式")
    print("=" * 40)

    choice = input("请选择功能 [1-6]: ").strip()

    if choice == "1":
        success = pusher.push_latest_draw()
        print("✅ 开奖结果推送成功" if success else "❌ 开奖结果推送失败")

    elif choice == "2":
        success = pusher.push_latest_predictions()
        print("✅ 预测结果推送成功" if success else "❌ 预测结果推送失败")

    elif choice == "3":
        success = pusher.push_model_summary()
        print("✅ 模型汇总推送成功" if success else "❌ 模型汇总推送失败")

    elif choice == "4":
        success = pusher.push_system_alert("TEST_ALERT", "这是一条测试告警消息", "INFO")
        print("✅ 告警推送成功" if success else "❌ 告警推送失败")

    elif choice == "5":
        success = pusher.push_complete_analysis()
        print("✅ 完整分析推送成功" if success else "❌ 部分推送失败")

    elif choice == "6":
        print("🔄 自动监控模式启动...")
        print("每10分钟推送一次完整分析，按Ctrl+C退出")

        try:
            while True:
                print(
                    f"\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 执行推送..."
                )
                pusher.push_complete_analysis()
                print("⏳ 等待10分钟...")
                time.sleep(600)  # 10分钟
        except KeyboardInterrupt:
            print("\n👋 自动监控已停止")

    else:
        print("❌ 无效选择")


if __name__ == "__main__":
    main()
