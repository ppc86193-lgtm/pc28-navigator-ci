#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PC28 Telegram 实时推送系统
支持开奖结果和预测结果的实时推送
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import requests

# Telegram Bot 配置
BOT_TOKEN = "8094025881:AAF-7fv6djS0Z8QcgHwHloGSVguXj8XXEC0"
CHAT_ID = "8420412156"  # 小财神

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class DrawResult:
    """开奖结果数据类"""

    issue: str
    timestamp: str
    a: int
    b: int
    c: int
    sum_value: int
    tail: int
    size: str
    odd_even: str


@dataclass
class PredictionResult:
    """预测结果数据类"""

    issue: str
    timestamp: str
    prediction_type: str
    prediction: str
    confidence: float
    model_name: str


class TelegramPusher:
    """Telegram推送类"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

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


class MessageTemplates:
    """消息模板类"""

    @staticmethod
    def draw_result_template(draw: DrawResult) -> str:
        """开奖结果推送模板"""

        # 计算时间
        beijing_time = datetime.now(timezone(timedelta(hours=8)))
        time_str = beijing_time.strftime("%H:%M:%S")

        # 预测状态图标
        size_icon = "🔴" if draw.size == "大" else "🟢"
        oddeven_icon = "🔸" if draw.odd_even == "奇" else "🔹"

        template = f"""
🎯 *PC28开奖结果* #{draw.issue}

⏰ 开奖时间: `{time_str}`
🎲 开奖号码: `{draw.a} + {draw.b} + {draw.c} = {draw.sum_value}`

📊 *结果分析*:
{size_icon} 大小: *{draw.size}* (和值{draw.sum_value})
{oddeven_icon} 单双: *{draw.odd_even}* (尾数{draw.tail})

━━━━━━━━━━━━━━━━━
📈 下期预测分析即将发布...
"""
        return template

    @staticmethod
    def prediction_template(predictions: List[PredictionResult]) -> str:
        """预测结果推送模板"""

        beijing_time = datetime.now(timezone(timedelta(hours=8)))
        time_str = beijing_time.strftime("%H:%M:%S")

        # 获取下期期号
        next_issue = predictions[0].issue if predictions else "未知"

        template = f"""
🔮 *PC28预测分析* #{next_issue}

⏰ 分析时间: `{time_str}`

"""

        # 大小预测
        size_predictions = [p for p in predictions if p.prediction_type == "size"]
        if size_predictions:
            best_size = max(size_predictions, key=lambda x: x.confidence)
            confidence_icon = (
                "🟢"
                if best_size.confidence >= 0.7
                else "🟡" if best_size.confidence >= 0.6 else "🔴"
            )
            template += f"""
📏 *大小预测*: {confidence_icon}
预测结果: *{best_size.prediction}*
置信度: `{best_size.confidence:.1%}`
模型: {best_size.model_name}

"""

        # 单双预测
        oddeven_predictions = [
            p for p in predictions if p.prediction_type == "odd_even"
        ]
        if oddeven_predictions:
            best_oddeven = max(oddeven_predictions, key=lambda x: x.confidence)
            confidence_icon = (
                "🟢"
                if best_oddeven.confidence >= 0.7
                else "🟡" if best_oddeven.confidence >= 0.6 else "🔴"
            )
            template += f"""
🎯 *单双预测*: {confidence_icon}
预测结果: *{best_oddeven.prediction}*
置信度: `{best_oddeven.confidence:.1%}`
模型: {best_oddeven.model_name}

"""

        # 和值预测（如果有）
        sum_predictions = [p for p in predictions if p.prediction_type == "sum"]
        if sum_predictions:
            best_sum = max(sum_predictions, key=lambda x: x.confidence)
            template += f"""
➕ *和值预测*:
预测区间: *{best_sum.prediction}*
置信度: `{best_sum.confidence:.1%}`

"""

        template += """━━━━━━━━━━━━━━━━━
⚠️ 预测仅供参考，请理性投注"""

        return template

    @staticmethod
    def accuracy_report_template(stats: Dict) -> str:
        """准确率报告模板"""

        template = f"""
📊 *PC28准确率日报*

📅 统计时间: `{stats.get('date', '今日')}`

🎯 *预测准确率*:
• 大小预测: `{stats.get('size_accuracy', 0):.1%}` ({stats.get('size_count', 0)}次)
• 单双预测: `{stats.get('oddeven_accuracy', 0):.1%}` ({stats.get('oddeven_count', 0)}次)
• 综合准确率: `{stats.get('overall_accuracy', 0):.1%}`

📈 *系统状态*:
• Gate通过率: `{stats.get('gate_pass_rate', 0):.1%}`
• 活跃模型: `{stats.get('active_models', 0)}`个
• 监控覆盖: `{stats.get('monitoring_coverage', 0):.1%}`

🔄 *数据更新*:
• 最后更新: `{stats.get('last_update', '未知')}`
• 数据完整性: `{stats.get('data_integrity', 0):.1%}`

━━━━━━━━━━━━━━━━━
🚀 系统运行状态: {stats.get('system_status', '正常')}
"""
        return template

    @staticmethod
    def system_alert_template(
        alert_type: str, message: str, severity: str = "INFO"
    ) -> str:
        """系统告警模板"""

        severity_icons = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "🚨", "CRITICAL": "🔥"}

        icon = severity_icons.get(severity, "ℹ️")
        beijing_time = datetime.now(timezone(timedelta(hours=8)))
        time_str = beijing_time.strftime("%H:%M:%S")

        template = f"""
{icon} *PC28系统告警*

⏰ 告警时间: `{time_str}`
🏷️ 告警类型: `{alert_type}`
📢 严重程度: `{severity}`

📋 *告警详情*:
{message}

━━━━━━━━━━━━━━━━━
🔧 请及时检查系统状态
"""
        return template


class PC28TelegramBot:
    """PC28 Telegram Bot主类"""

    def __init__(self):
        self.pusher = TelegramPusher(BOT_TOKEN, CHAT_ID)
        self.templates = MessageTemplates()

    def push_draw_result(self, draw_data: Dict) -> bool:
        """推送开奖结果"""
        try:
            draw = DrawResult(
                issue=draw_data.get("issue", ""),
                timestamp=draw_data.get("timestamp", ""),
                a=draw_data.get("a", 0),
                b=draw_data.get("b", 0),
                c=draw_data.get("c", 0),
                sum_value=draw_data.get("sum", 0),
                tail=draw_data.get("tail", 0),
                size=draw_data.get("size", ""),
                odd_even=draw_data.get("odd_even", ""),
            )

            message = self.templates.draw_result_template(draw)
            return self.pusher.send_message(message)

        except Exception as e:
            logger.error(f"推送开奖结果失败: {e}")
            return False

    def push_predictions(self, predictions_data: List[Dict]) -> bool:
        """推送预测结果"""
        try:
            predictions = []
            for pred_data in predictions_data:
                prediction = PredictionResult(
                    issue=pred_data.get("issue", ""),
                    timestamp=pred_data.get("timestamp", ""),
                    prediction_type=pred_data.get("type", ""),
                    prediction=pred_data.get("prediction", ""),
                    confidence=pred_data.get("confidence", 0.0),
                    model_name=pred_data.get("model", ""),
                )
                predictions.append(prediction)

            message = self.templates.prediction_template(predictions)
            return self.pusher.send_message(message)

        except Exception as e:
            logger.error(f"推送预测结果失败: {e}")
            return False

    def push_accuracy_report(self, stats_data: Dict) -> bool:
        """推送准确率报告"""
        try:
            message = self.templates.accuracy_report_template(stats_data)
            return self.pusher.send_message(message)

        except Exception as e:
            logger.error(f"推送准确率报告失败: {e}")
            return False

    def push_system_alert(
        self, alert_type: str, message: str, severity: str = "INFO"
    ) -> bool:
        """推送系统告警"""
        try:
            alert_message = self.templates.system_alert_template(
                alert_type, message, severity
            )
            return self.pusher.send_message(alert_message)

        except Exception as e:
            logger.error(f"推送系统告警失败: {e}")
            return False


def test_telegram_bot():
    """测试Telegram Bot功能"""
    bot = PC28TelegramBot()

    # 测试开奖结果推送
    test_draw = {
        "issue": "20250919001",
        "timestamp": "2025-09-19 05:30:00",
        "a": 3,
        "b": 7,
        "c": 2,
        "sum": 12,
        "tail": 2,
        "size": "小",
        "odd_even": "偶",
    }

    # 测试预测结果推送
    test_predictions = [
        {
            "issue": "20250919002",
            "timestamp": "2025-09-19 05:33:00",
            "type": "size",
            "prediction": "大",
            "confidence": 0.72,
            "model": "pred_size_simple",
        },
        {
            "issue": "20250919002",
            "timestamp": "2025-09-19 05:33:00",
            "type": "odd_even",
            "prediction": "奇",
            "confidence": 0.68,
            "model": "pred_oddeven_simple",
        },
    ]

    # 测试系统状态报告
    test_stats = {
        "date": "2025-09-19",
        "size_accuracy": 0.745,
        "size_count": 134,
        "oddeven_accuracy": 0.723,
        "oddeven_count": 134,
        "overall_accuracy": 0.734,
        "gate_pass_rate": 0.8881,
        "active_models": 5,
        "monitoring_coverage": 1.0,
        "last_update": "05:30:00",
        "data_integrity": 1.0,
        "system_status": "L4自动驾驶",
    }

    print("🚀 开始测试Telegram推送...")

    # 测试开奖结果
    success1 = bot.push_draw_result(test_draw)
    print(f"开奖结果推送: {'✅' if success1 else '❌'}")

    time.sleep(2)

    # 测试预测结果
    success2 = bot.push_predictions(test_predictions)
    print(f"预测结果推送: {'✅' if success2 else '❌'}")

    time.sleep(2)

    # 测试状态报告
    success3 = bot.push_accuracy_report(test_stats)
    print(f"状态报告推送: {'✅' if success3 else '❌'}")

    time.sleep(2)

    # 测试系统告警
    success4 = bot.push_system_alert(
        "ACCURACY_RECOVERY", "准确率恢复流程已启动，切换到Conservative模式", "WARN"
    )
    print(f"系统告警推送: {'✅' if success4 else '❌'}")

    return all([success1, success2, success3, success4])


if __name__ == "__main__":
    # 运行测试
    test_success = test_telegram_bot()
    print(f"\n🎯 测试结果: {'全部成功 ✅' if test_success else '部分失败 ❌'}")
