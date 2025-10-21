#!/usr/bin/env python3
"""
PC28 上游逻辑改进建议
解决超时和性能问题
"""

import asyncio
import logging
from datetime import datetime

from flask import jsonify, request
from google.cloud import bigquery

logger = logging.getLogger(__name__)


class PC28ImprovedLogic:
    """改进的上游逻辑"""

    def __init__(self):
        self.bq_client = bigquery.Client(project="wprojectl", location="us-central1")

    # 1. 批量查重优化
    def batch_check_duplicates(self, issues):
        """批量检查重复记录，减少数据库查询次数"""
        if not issues:
            return set()

        # 使用IN查询一次性检查所有期号
        placeholders = ",".join(["@issue_" + str(i) for i in range(len(issues))])
        check_query = f"""
        SELECT DISTINCT issue FROM `wprojectl.pc28.draws_clean`
        WHERE issue IN ({placeholders})
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(f"issue_{i}", "STRING", issue)
                for i, issue in enumerate(issues)
            ]
        )

        result = self.bq_client.query(check_query, job_config=job_config).result()
        existing_issues = {row.issue for row in result}
        logger.info(f"批量查重完成: {len(existing_issues)}/{len(issues)} 已存在")
        return existing_issues

    # 2. 分块处理大批量数据
    async def process_historical_data_chunked(self, date, total_limit=500):
        """分块处理历史数据，避免超时"""
        chunk_size = 50  # 每块50条
        total_saved = 0
        total_processed = 0

        for offset in range(0, total_limit, chunk_size):
            current_limit = min(chunk_size, total_limit - offset)

            try:
                # 获取一块数据
                api_response = await self._get_historical_chunk(
                    date, current_limit, offset
                )
                if not api_response:
                    break

                # 解析数据
                parsed_records = self._parse_historical_data(api_response)
                if not parsed_records:
                    continue

                # 批量查重
                issues = [record["issue"] for record in parsed_records]
                existing_issues = self.batch_check_duplicates(issues)

                # 过滤新记录
                new_records = [
                    record
                    for record in parsed_records
                    if record["issue"] not in existing_issues
                ]

                # 批量插入
                if new_records:
                    saved_count = self._batch_insert_records(new_records)
                    total_saved += saved_count
                    logger.info(
                        f"块 {offset}-{offset+current_limit}: 保存 {saved_count} 条"
                    )

                total_processed += len(parsed_records)

                # 防止API限制
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"处理块 {offset}-{offset+current_limit} 失败: {e}")
                continue

        return total_saved, total_processed

    # 3. BigQuery批量插入优化
    def _batch_insert_records(self, records):
        """优化的批量插入方法"""
        if not records:
            return 0

        # 使用BigQuery的streaming insert (更快)
        table_id = "wprojectl.pc28.draws_clean"
        table = self.bq_client.get_table(table_id)

        # 转换为BigQuery rows格式
        rows_to_insert = [
            {
                "issue": record["issue"],
                "timestamp": record["timestamp"],
                "a": record["a"],
                "b": record["b"],
                "c": record["c"],
                "sum": record["sum"],
                "tail": record["tail"],
                "size": record["size"],
                "odd_even": record["odd_even"],
                "patterns": record["patterns"],
                "source": record["source"],
                "created_at": record["created_at"],
                "api_codeid": record["api_codeid"],
                "api_message": record["api_message"],
                "api_curtime": record["api_curtime"],
                "kjtime_raw": record["kjtime_raw"],
                "next_issue": record["next_issue"],
                "next_time": record["next_time"],
                "award_time": record["award_time"],
                "raw_api_response": record["raw_api_response"],
            }
            for record in records
        ]

        # 批量插入
        errors = self.bq_client.insert_rows_json(table, rows_to_insert)

        if errors:
            logger.error(f"批量插入错误: {errors}")
            return 0

        logger.info(f"批量插入成功: {len(records)} 条记录")
        return len(records)

    # 4. 改进的错误重试机制
    async def _make_request_with_retry(self, endpoint, max_retries=3, **kwargs):
        """带重试的API请求"""
        for attempt in range(max_retries):
            try:
                result = await self._make_request(endpoint, **kwargs)
                if result:
                    return result

                # API返回错误，等待后重试
                if attempt < max_retries - 1:
                    wait_time = 2**attempt  # 指数退避
                    logger.warning(
                        f"API请求失败，{wait_time}秒后重试 (尝试 {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"请求异常: {e}，{wait_time}秒后重试 (尝试 {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"请求失败，已达最大重试次数: {e}")

        return None

    # 5. 智能限流控制
    class RateLimiter:
        """API限流控制"""

        def __init__(self, calls_per_minute=30):
            self.calls_per_minute = calls_per_minute
            self.calls = []

        async def wait_if_needed(self):
            """如果需要则等待"""
            now = datetime.now()
            # 清理1分钟前的记录
            self.calls = [
                call_time for call_time in self.calls if (now - call_time).seconds < 60
            ]

            if len(self.calls) >= self.calls_per_minute:
                # 已达限制，等待到最早记录过期
                wait_time = 60 - (now - self.calls[0]).seconds + 1
                logger.info(f"API限流等待 {wait_time} 秒")
                await asyncio.sleep(wait_time)

            self.calls.append(now)

    # 6. 内存优化的数据处理
    def process_large_dataset_memory_efficient(self, data):
        """内存优化的大数据集处理"""

        # 使用生成器避免一次性加载所有数据到内存
        def record_generator():
            for item in data:
                # 处理单条记录
                processed = self._process_single_record(item)
                if processed:
                    yield processed

        # 分批处理，控制内存使用
        batch = []
        batch_size = 100

        for record in record_generator():
            batch.append(record)

            if len(batch) >= batch_size:
                # 处理一批
                self._process_batch(batch)
                batch = []  # 清空内存

        # 处理最后一批
        if batch:
            self._process_batch(batch)


# 建议的新API端点
async def optimized_backfill_endpoint():
    """优化的批量回填端点"""
    try:
        date = request.args.get("date")
        max_records = min(int(request.args.get("limit", 200)), 500)  # 限制最大数量

        improved_client = PC28ImprovedLogic()

        # 使用分块处理
        saved_count, processed_count = (
            await improved_client.process_historical_data_chunked(date, max_records)
        )

        return jsonify(
            {
                "status": "success",
                "date": date,
                "processed": processed_count,
                "saved": saved_count,
                "skipped": processed_count - saved_count,
                "optimization": "chunked_processing_enabled",
            }
        )

    except Exception as e:
        logger.error(f"优化回填失败: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


"""
改进总结：

1. 性能优化：
   - 批量查重减少数据库查询 (N次 → 1次)
   - 分块处理避免超时 (大批量 → 小块)
   - BigQuery streaming insert 提升插入速度

2. 可靠性提升：
   - 指数退避重试机制
   - 智能限流控制
   - 详细错误日志

3. 内存优化：
   - 生成器处理大数据集
   - 及时释放内存
   - 控制批次大小

4. 监控改进：
   - 详细的进度日志
   - 性能指标记录
   - 错误分类统计
"""
