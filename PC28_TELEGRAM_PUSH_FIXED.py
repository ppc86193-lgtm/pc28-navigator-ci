#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PC28 Telegram 推送修复版本
直接集成BigQuery查询和推送功能
"""

import subprocess
import json
import requests
import time
from datetime import datetime, timezone, timedelta
import logging

# 配置
BOT_TOKEN = "8094025881:AAF-7fv6djS0Z8QcgHwHloGSVguXj8XXEC0"
CHAT_ID = "8420412156"

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }

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

            cmd = ['bq', 'query', '--use_legacy_sql=false', '--format=json', '--quiet', query]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if result.stdout.strip():
                data = json.loads(result.stdout)
                return data[0] if data else None
            else:
                logger.warning("BigQuery查询返回空结果")
                return None

        except subprocess.CalledProcessError as e:
            logger.error(f"BigQuery查询失败: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.error(f"原始输出: {result.stdout}")
            return None
        except Exception as e:
            logger.error(f"获取开奖数据失败: {e}")
            return None

    def get_latest_predictions(self):
        """获取最新预测结果"""
        try:
            # 先获取下期期号
            period_query = """
            SELECT
                CAST(REGEXP_EXTRACT(issue, r'(\\d+)$') AS INT64) + 1 as next_period
            FROM `wprojectl.pc28.draws_clean`
            WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            ORDER BY timestamp DESC
            LIMIT 1
            """

            cmd = ['bq', 'query', '--use_legacy_sql=false', '--format=csv', '--quiet', period_query]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if not result.stdout.strip():
                return []

            lines = result.stdout.strip().split('\n')
            if len(lines) < 2:
                return []

            next_period = lines[1].strip()

            # 获取预测数据
            pred_query = f"""
            WITH next_issue AS (
                SELECT CONCAT(FORMAT_DATE('%Y%m%d', CURRENT_DATE('Asia/Shanghai')),
                             LPAD(CAST({next_period} AS STRING), 3, '0')) as issue
            )
            SELECT
                ni.issue,
                'size' as type,
                CASE WHEN prediction_big >= 0.5 THEN '大' ELSE '小' END as prediction,
                prediction_big as confidence,
                'pred_size_simple' as model
            FROM `wprojectl.pc28.pred_size_simple` ps
            CROSS JOIN next_issue ni
            ORDER BY prediction_big DESC
            LIMIT 1
            """

            cmd = ['bq', 'query', '--use_legacy_sql=false', '--format=json', '--quiet', pred_query]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if result.stdout.strip():
                return json.loads(result.stdout)
            else:
                return []

        except Exception as e:
            logger.error(f"获取预测数据失败: {e}")
            return []

    def format_draw_message(self, draw_data):
        """格式化开奖消息"""
        if not draw_data:
            return None

        # 计算时间
        beijing_time = datetime.now(timezone(timedelta(hours=8)))
        time_str = beijing_time.strftime("%H:%M:%S")

        # 预测状态图标
        size_icon = "🔴" if draw_data.get('size') == 'large' else "🟢"
        oddeven_icon = "🔸" if draw_data.get('odd_even') == 'odd' else "🔹"

        # 转换显示名称
        size_cn = "大" if draw_data.get('size') == 'large' else "小"
        oddeven_cn = "奇" if draw_data.get('odd_even') == 'odd' else "偶"

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
            return None

        beijing_time = datetime.now(timezone(timedelta(hours=8)))
        time_str = beijing_time.strftime("%H:%M:%S")

        # 获取下期期号
        next_issue = predictions_data[0].get('issue', '未知') if predictions_data else "未知"

        message = f"""🔮 *PC28预测分析* #{next_issue}

⏰ 分析时间: `{time_str}`

"""

        # 处理预测数据
        for pred in predictions_data:
            if pred.get('type') == 'size':
                confidence = float(pred.get('confidence', 0))
                confidence_icon = "🟢" if confidence >= 0.7 else "🟡" if confidence >= 0.6 else "🔴"
                message += f"""📏 *大小预测*: {confidence_icon}
预测结果: *{pred.get('prediction', '')}*
置信度: `{confidence:.1%}`
模型: {pred.get('model', '')}

"""

        message += """━━━━━━━━━━━━━━━━━
⚠️ 预测仅供参考，请理性投注"""

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
        if not predictions_data:
            logger.warning("无法获取预测数据")
            return False

        message = self.format_prediction_message(predictions_data)
        if not message:
            logger.warning("无法格式化预测消息")
            return False

        return self.send_message(message)

    def push_system_alert(self, alert_type: str, alert_message: str, severity: str = "INFO"):
        """推送系统告警"""
        severity_icons = {
            "INFO": "ℹ️",
            "WARN": "⚠️",
            "ERROR": "🚨",
            "CRITICAL": "🔥"
        }

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

def main():
    pusher = PC28TelegramPusher()

    print("PC28 Telegram推送工具")
    print("1) 推送最新开奖结果")
    print("2) 推送最新预测结果")
    print("3) 发送测试告警")
    print("4) 连续推送(开奖+预测)")

    choice = input("请选择功能 [1-4]: ").strip()

    if choice == "1":
        success = pusher.push_latest_draw()
        print("✅ 开奖结果推送成功" if success else "❌ 开奖结果推送失败")

    elif choice == "2":
        success = pusher.push_latest_predictions()
        print("✅ 预测结果推送成功" if success else "❌ 预测结果推送失败")

    elif choice == "3":
        success = pusher.push_system_alert("TEST_ALERT", "这是一条测试告警消息", "INFO")
        print("✅ 告警推送成功" if success else "❌ 告警推送失败")

    elif choice == "4":
        print("推送开奖结果...")
        success1 = pusher.push_latest_draw()
        time.sleep(3)

        print("推送预测结果...")
        success2 = pusher.push_latest_predictions()

        print(f"✅ 连续推送完成，开奖: {'成功' if success1 else '失败'}, 预测: {'成功' if success2 else '失败'}")

    else:
        print("无效选择")

if __name__ == "__main__":
    main()