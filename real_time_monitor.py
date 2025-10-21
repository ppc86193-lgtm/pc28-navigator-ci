#!/usr/bin/env python3
import asyncio

import aiohttp
from google.cloud import bigquery


class RealTimeMonitor:
    def __init__(self):
        self.bot_token = "8094025881:AAF-7fv6djS0Z8QcgHwHloGSVguXj8XXEC0"
        self.chat_id = "8420412156"
        self.telegram_api = f"https://api.telegram.org/bot{self.bot_token}"
        self.bq_client = bigquery.Client(project="wprojectl", location="us-central1")
        self.last_issue = None

    async def send_message(self, text):
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.telegram_api}/sendMessage"
                payload = {"chat_id": self.chat_id, "text": text}
                async with session.post(url, json=payload) as response:
                    result = await response.json()
                    return result.get("ok", False)
            except Exception:
                return False

    async def check_new_draws(self):
        try:
            query = """
            SELECT issue, timestamp, a, b, c, (a + b + c) as sum
            FROM `wprojectl.pc28.draws_14w_dedup_v`
            ORDER BY timestamp DESC
            LIMIT 1
            """
            results = list(self.bq_client.query(query).result())

            if results:
                latest = results[0]
                if self.last_issue != latest.issue:
                    self.last_issue = latest.issue

                    message = f"""🎲 PC28开奖结果推送

👑 项目总指挥大人"小财神"

📅 开奖时间: {latest.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

🎯 开奖结果:
📊 期号: {latest.issue}
🎲 开奖号码: {latest.a} + {latest.b} + {latest.c} = {latest.sum}
📏 大小: {'BIG' if latest.sum >= 14 else 'SMALL'}
🎲 奇偶: {'ODD' if latest.sum % 2 == 1 else 'EVEN'}
🔢 尾数: {latest.sum % 10}

⚡ 系统状态:
🤖 实时监控: 正常运行
📡 自动推送: 已激活

🎪 PC28为您实时服务！"""

                    await self.send_message(message)
                    print(f"推送开奖: 期号{latest.issue}, 结果{latest.sum}")

        except Exception as e:
            print(f"检查开奖失败: {e}")

    async def monitor_loop(self):
        print("🔄 实时监控启动...")
        while True:
            await self.check_new_draws()
            await asyncio.sleep(60)  # 每分钟检查一次


if __name__ == "__main__":
    monitor = RealTimeMonitor()
    asyncio.run(monitor.monitor_loop())
