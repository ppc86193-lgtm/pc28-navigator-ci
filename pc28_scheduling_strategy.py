#!/usr/bin/env python3
"""
PC28 数据拉取调度策略
- 自有API，无黑名单风险
- 开奖频率: 210秒 (3.5分钟) 一期
- 运行时间: 00:03:46 - 23:58:46
- 维护窗口: 19:00-19:30 (晚上7点到7点30)
- 每日约280期开奖
"""

from datetime import datetime, timedelta, time
import asyncio
import logging

logger = logging.getLogger(__name__)

class PC28SchedulingStrategy:
    """PC28 最优调度策略"""

    def __init__(self):
        self.draw_interval = 210  # 3.5分钟一期
        self.maintenance_start = time(19, 0)   # 19:00
        self.maintenance_end = time(19, 30)    # 19:30
        self.daily_start = time(0, 3, 46)      # 00:03:46
        self.daily_end = time(23, 58, 46)      # 23:58:46

    def is_maintenance_window(self, check_time=None):
        """检查是否在维护窗口"""
        if check_time is None:
            check_time = datetime.now().time()

        return self.maintenance_start <= check_time <= self.maintenance_end

    def is_active_period(self, check_time=None):
        """检查是否在开奖活跃期"""
        if check_time is None:
            check_time = datetime.now().time()

        # 跨日期判断 (00:03:46 - 23:58:46)
        if self.daily_start <= self.daily_end:
            return self.daily_start <= check_time <= self.daily_end
        else:
            return check_time >= self.daily_start or check_time <= self.daily_end

    def get_optimal_schedule(self):
        """获取最优调度方案"""
        return {
            "realtime_fetching": {
                "frequency": "每2分钟",
                "reason": "开奖间隔3.5分钟，2分钟频率确保不遗漏",
                "avoid_windows": ["维护期 19:00-19:30", "非开奖期 23:58:46-00:03:46"],
                "implementation": "Cloud Scheduler + Cloud Run"
            },

            "historical_backfill": {
                "timing": "每日凌晨 01:00-03:00",
                "reason": "非开奖期，系统负载低，有充足时间处理",
                "batch_size": "每次200条，分块处理",
                "target_window": "2小时足够处理任何缺失数据"
            },

            "maintenance_handling": {
                "detection": "API响应监控 + 时间窗口",
                "fallback": "维护期间暂停实时拉取",
                "recovery": "19:31开始立即拉取 + 检查缺失数据"
            }
        }

    async def smart_realtime_fetching(self):
        """智能实时拉取策略"""
        while True:
            current_time = datetime.now().time()

            # 检查是否应该拉取
            if not self.is_active_period(current_time):
                logger.info("非开奖期，暂停拉取")
                await asyncio.sleep(300)  # 5分钟后再检查
                continue

            if self.is_maintenance_window(current_time):
                logger.info("维护窗口，暂停拉取")
                # 等待到维护结束
                wait_until = datetime.combine(datetime.now().date(), self.maintenance_end)
                if wait_until < datetime.now():
                    wait_until += timedelta(days=1)
                wait_seconds = (wait_until - datetime.now()).total_seconds()
                await asyncio.sleep(wait_seconds + 60)  # 维护结束后1分钟开始
                continue

            # 执行实时拉取
            try:
                await self.fetch_realtime_data()
                logger.info(f"实时数据拉取完成: {datetime.now()}")
            except Exception as e:
                logger.error(f"实时拉取失败: {e}")

            # 等待下次拉取 (2分钟)
            await asyncio.sleep(120)

    async def scheduled_historical_backfill(self):
        """定时历史数据回填"""
        while True:
            now = datetime.now()

            # 等待到凌晨1点
            if now.hour != 1 or now.minute < 0:
                next_run = datetime.combine(now.date(), time(1, 0))
                if next_run <= now:
                    next_run += timedelta(days=1)

                wait_seconds = (next_run - now).total_seconds()
                logger.info(f"等待历史回填时间: {next_run}")
                await asyncio.sleep(wait_seconds)
                continue

            # 执行历史回填
            logger.info("开始历史数据回填")
            try:
                # 回填昨天的数据（如果有遗漏）
                yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
                await self.intelligent_backfill(yesterday)

                # 回填前天的数据（双重保险）
                day_before = (now - timedelta(days=2)).strftime('%Y-%m-%d')
                await self.intelligent_backfill(day_before)

                logger.info("历史回填完成")

            except Exception as e:
                logger.error(f"历史回填失败: {e}")

            # 24小时后再次执行
            await asyncio.sleep(86400)

    async def intelligent_backfill(self, date):
        """智能历史回填 - 只回填缺失的数据"""
        # 1. 检查当天应有的期数
        expected_draws_per_day = int((23*3600 + 58*60 + 46 - 3*60 - 46) / 210)  # 约280期

        # 2. 查询已有期数
        existing_count = await self.count_existing_draws(date)

        # 3. 如果缺失较多，执行回填
        missing_ratio = (expected_draws_per_day - existing_count) / expected_draws_per_day

        if missing_ratio > 0.05:  # 缺失5%以上才回填
            logger.info(f"日期 {date} 缺失 {missing_ratio:.1%} 数据，开始回填")

            # 分批回填，避免超时
            batch_size = 100
            total_backfilled = 0

            for offset in range(0, expected_draws_per_day, batch_size):
                try:
                    saved_count = await self.backfill_batch(date, batch_size, offset)
                    total_backfilled += saved_count

                    if saved_count == 0:
                        break  # 没有更多数据了

                    # 防止API压力
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"回填批次失败 {date} offset={offset}: {e}")
                    continue

            logger.info(f"日期 {date} 回填完成，新增 {total_backfilled} 条记录")
        else:
            logger.info(f"日期 {date} 数据完整 ({existing_count}/{expected_draws_per_day})，跳过回填")

def create_cloud_scheduler_config():
    """生成 Cloud Scheduler 配置"""
    return {
        "realtime_job": {
            "name": "pc28-realtime-fetcher",
            "schedule": "*/2 * * * *",  # 每2分钟
            "time_zone": "Asia/Shanghai",
            "http_target": {
                "uri": "https://pc28-push-endpoints-644485179199.us-central1.run.app/fetch/realtime",
                "http_method": "GET"
            },
            "retry_config": {
                "retry_count": 3,
                "max_retry_duration": "300s",
                "min_backoff_duration": "5s",
                "max_backoff_duration": "60s"
            }
        },

        "historical_backfill_job": {
            "name": "pc28-historical-backfill",
            "schedule": "0 1 * * *",  # 每日凌晨1点
            "time_zone": "Asia/Shanghai",
            "http_target": {
                "uri": "https://pc28-push-endpoints-644485179199.us-central1.run.app/backfill/smart",
                "http_method": "POST",
                "body": '{"days": 2, "intelligent": true}'
            }
        },

        "maintenance_recovery_job": {
            "name": "pc28-maintenance-recovery",
            "schedule": "31 19 * * *",  # 每日19:31 (维护结束后)
            "time_zone": "Asia/Shanghai",
            "http_target": {
                "uri": "https://pc28-push-endpoints-644485179199.us-central1.run.app/recovery/post-maintenance",
                "http_method": "GET"
            }
        }
    }

def get_recommendations():
    """获取调度建议"""
    return """
    🎯 PC28 最优调度策略

    ⏰ 实时拉取:
    - 频率: 每2分钟 (开奖间隔3.5分钟)
    - 时间: 00:03:46 - 23:58:46
    - 避开: 维护期 19:00-19:30
    - 实现: Cloud Scheduler + /fetch/realtime

    🔄 历史回填:
    - 时机: 每日凌晨1:00-3:00
    - 策略: 智能检测缺失数据
    - 批次: 100条/批次，间隔2秒
    - 目标: 确保数据完整性

    🛠 维护期处理:
    - 19:00-19:30 暂停所有拉取
    - 19:31 立即恢复 + 检查缺失
    - 维护期缺失数据自动回填

    📊 监控指标:
    - 每日期数: ~280期
    - 数据完整率: >95%
    - API成功率: >99%
    - 平均延迟: <2分钟

    ✅ 实施建议:
    1. 部署Cloud Scheduler任务
    2. 添加维护期检测逻辑
    3. 实现智能回填端点
    4. 设置监控告警
    """

if __name__ == "__main__":
    strategy = PC28SchedulingStrategy()
    print(strategy.get_optimal_schedule())
    print(get_recommendations())