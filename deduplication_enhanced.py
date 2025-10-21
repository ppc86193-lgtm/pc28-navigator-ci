#!/usr/bin/env python3
"""
PC28 数据去重增强机制
- 多层次去重策略
- 实时去重检查
- 批量去重优化
- 重复数据清理
"""

import asyncio
from datetime import datetime, timedelta
from google.cloud import bigquery
import logging
import hashlib
import json

logger = logging.getLogger(__name__)

class EnhancedDeduplication:
    """增强的数据去重机制"""

    def __init__(self):
        self.bq_client = bigquery.Client(project="wprojectl", location="us-central1")
        self.table_id = "wprojectl.pc28.draws_clean"

    def create_deduplication_strategy(self):
        """创建多层次去重策略"""
        return {
            "primary_key": "issue",  # 主键去重 - 期号唯一
            "composite_key": ["issue", "timestamp", "a", "b", "c"],  # 复合键去重
            "content_hash": ["a", "b", "c", "sum", "kjtime_raw"],  # 内容哈希去重
            "time_window": 300,  # 5分钟时间窗口内的重复检测
            "batch_size": 100  # 批量处理大小
        }

    def generate_content_hash(self, record):
        """生成内容哈希用于去重"""
        content_fields = [
            str(record.get('issue', '')),
            str(record.get('a', '')),
            str(record.get('b', '')),
            str(record.get('c', '')),
            str(record.get('sum', '')),
            str(record.get('kjtime_raw', ''))
        ]
        content_string = '|'.join(content_fields)
        return hashlib.sha256(content_string.encode()).hexdigest()[:16]

    async def check_duplicates_realtime(self, record):
        """实时去重检查 - 单条记录"""
        try:
            issue = record.get('issue')
            if not issue:
                return {"is_duplicate": True, "reason": "missing_issue"}

            # 1. 主键去重检查
            primary_check_query = """
            SELECT COUNT(*) as count, MAX(created_at) as latest_created
            FROM `wprojectl.pc28.draws_clean`
            WHERE issue = @issue
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("issue", "STRING", str(issue))
                ]
            )

            result = self.bq_client.query(primary_check_query, job_config=job_config).result()
            primary_stats = next(iter(result))

            if primary_stats.count > 0:
                return {
                    "is_duplicate": True,
                    "reason": "primary_key_exists",
                    "existing_count": primary_stats.count,
                    "latest_created": primary_stats.latest_created.isoformat() if primary_stats.latest_created else None
                }

            # 2. 内容哈希去重检查 (防止数据变异后重复)
            content_hash = self.generate_content_hash(record)
            timestamp = record.get('timestamp', datetime.now().isoformat())

            # 检查5分钟内的相似记录
            content_check_query = """
            SELECT COUNT(*) as count, issue, timestamp
            FROM `wprojectl.pc28.draws_clean`
            WHERE a = @a AND b = @b AND c = @c
            AND ABS(TIMESTAMP_DIFF(@current_time, timestamp, SECOND)) <= 300
            LIMIT 1
            """

            current_time = datetime.now().isoformat()
            content_job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("a", "INTEGER", record.get('a')),
                    bigquery.ScalarQueryParameter("b", "INTEGER", record.get('b')),
                    bigquery.ScalarQueryParameter("c", "INTEGER", record.get('c')),
                    bigquery.ScalarQueryParameter("current_time", "TIMESTAMP", current_time)
                ]
            )

            content_result = self.bq_client.query(content_check_query, content_job_config).result()
            content_stats = next(iter(content_result))

            if content_stats.count > 0:
                return {
                    "is_duplicate": True,
                    "reason": "content_similarity",
                    "similar_issue": content_stats.issue,
                    "similar_timestamp": content_stats.timestamp.isoformat() if content_stats.timestamp else None,
                    "content_hash": content_hash
                }

            # 3. 时间窗口逻辑检查
            time_window_query = """
            SELECT COUNT(*) as count, issue
            FROM `wprojectl.pc28.draws_clean`
            WHERE ABS(TIMESTAMP_DIFF(@record_time, timestamp, SECOND)) <= 210
            AND issue != @issue
            LIMIT 1
            """

            time_job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("record_time", "TIMESTAMP", timestamp),
                    bigquery.ScalarQueryParameter("issue", "STRING", str(issue))
                ]
            )

            time_result = self.bq_client.query(time_window_query, time_job_config).result()
            time_stats = next(iter(time_result))

            if time_stats.count > 0:
                logger.warning(f"时间窗口内发现其他期号 {time_stats.issue}，可能存在时序问题")

            return {
                "is_duplicate": False,
                "reason": "unique_record",
                "content_hash": content_hash,
                "validation": "passed"
            }

        except Exception as e:
            logger.error(f"实时去重检查失败: {e}")
            return {"is_duplicate": True, "reason": "check_error", "error": str(e)}

    async def batch_deduplication_check(self, records):
        """批量去重检查 - 优化性能"""
        try:
            if not records:
                return []

            # 提取所有期号进行批量查询
            issues = [str(r.get('issue', '')) for r in records if r.get('issue')]

            if not issues:
                return []

            # 批量查询已存在的期号
            placeholders = ','.join([f"'{issue}'" for issue in issues])
            batch_query = f"""
            SELECT DISTINCT issue FROM `wprojectl.pc28.draws_clean`
            WHERE issue IN ({placeholders})
            """

            result = self.bq_client.query(batch_query).result()
            existing_issues = {row.issue for row in result}

            # 过滤出新记录
            new_records = []
            duplicate_info = []

            for record in records:
                issue = str(record.get('issue', ''))

                if issue in existing_issues:
                    duplicate_info.append({
                        "issue": issue,
                        "reason": "already_exists",
                        "action": "skipped"
                    })
                else:
                    # 添加去重元数据
                    record['content_hash'] = self.generate_content_hash(record)
                    record['dedup_timestamp'] = datetime.now().isoformat()
                    new_records.append(record)

            logger.info(f"批量去重: {len(records)} -> {len(new_records)} (过滤 {len(duplicate_info)} 个重复)")

            return {
                "new_records": new_records,
                "duplicates": duplicate_info,
                "summary": {
                    "total_input": len(records),
                    "unique_records": len(new_records),
                    "duplicates_filtered": len(duplicate_info),
                    "deduplication_ratio": f"{len(duplicate_info)/len(records)*100:.1f}%"
                }
            }

        except Exception as e:
            logger.error(f"批量去重检查失败: {e}")
            return {"new_records": [], "duplicates": [], "error": str(e)}

    def create_duplicate_prevention_constraints(self):
        """创建数据库层面的重复预防约束"""
        # 注意：BigQuery 不支持 UNIQUE 约束，但可以通过其他方式实现
        return {
            "table_clustering": ["issue", "timestamp"],  # 按期号和时间聚类
            "partitioning": "DATE(timestamp)",  # 按日期分区
            "deduplication_view": """
                CREATE OR REPLACE VIEW `wprojectl.pc28.draws_clean_deduped` AS
                SELECT * EXCEPT(row_num)
                FROM (
                    SELECT *,
                           ROW_NUMBER() OVER (
                               PARTITION BY issue
                               ORDER BY created_at DESC, timestamp DESC
                           ) as row_num
                    FROM `wprojectl.pc28.draws_clean`
                )
                WHERE row_num = 1
            """
        }

    async def cleanup_existing_duplicates(self, dry_run=True):
        """清理现有重复数据"""
        try:
            # 1. 识别重复记录
            duplicate_detection_query = """
            WITH duplicates AS (
                SELECT
                    issue,
                    COUNT(*) as dup_count,
                    ARRAY_AGG(
                        STRUCT(timestamp, source, created_at)
                        ORDER BY created_at DESC, timestamp DESC
                    ) as versions
                FROM `wprojectl.pc28.draws_clean`
                GROUP BY issue
                HAVING COUNT(*) > 1
            )
            SELECT
                issue,
                dup_count,
                versions[OFFSET(0)].timestamp as keep_timestamp,
                versions[OFFSET(0)].source as keep_source,
                ARRAY_LENGTH(versions) - 1 as delete_count
            FROM duplicates
            ORDER BY dup_count DESC
            """

            result = self.bq_client.query(duplicate_detection_query).result()
            duplicates = list(result)

            if not duplicates:
                return {
                    "status": "no_duplicates",
                    "message": "未发现重复记录",
                    "total_duplicates": 0
                }

            cleanup_plan = []
            total_to_delete = 0

            for dup in duplicates:
                total_to_delete += dup.delete_count
                cleanup_plan.append({
                    "issue": dup.issue,
                    "duplicate_count": dup.dup_count,
                    "keep_version": {
                        "timestamp": dup.keep_timestamp.isoformat(),
                        "source": dup.keep_source
                    },
                    "will_delete": dup.delete_count
                })

            if dry_run:
                return {
                    "status": "dry_run",
                    "cleanup_plan": cleanup_plan,
                    "total_duplicates": len(duplicates),
                    "total_records_to_delete": total_to_delete,
                    "message": "这是预览模式，没有实际删除数据"
                }

            # 2. 执行清理 (如果不是dry_run)
            deleted_count = 0
            for dup_info in cleanup_plan:
                delete_query = """
                DELETE FROM `wprojectl.pc28.draws_clean`
                WHERE issue = @issue
                AND timestamp != @keep_timestamp
                """

                delete_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("issue", "STRING", dup_info["issue"]),
                        bigquery.ScalarQueryParameter("keep_timestamp", "TIMESTAMP", dup_info["keep_version"]["timestamp"])
                    ]
                )

                delete_result = self.bq_client.query(delete_query, delete_config).result()
                deleted_count += dup_info["will_delete"]

            return {
                "status": "cleanup_completed",
                "deleted_records": deleted_count,
                "cleaned_issues": len(cleanup_plan),
                "message": f"成功清理 {deleted_count} 条重复记录"
            }

        except Exception as e:
            logger.error(f"重复数据清理失败: {e}")
            return {"status": "error", "error": str(e)}

    def create_deduplication_monitoring(self):
        """创建去重监控查询"""
        return {
            "daily_duplicate_check": """
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as total_records,
                    COUNT(DISTINCT issue) as unique_issues,
                    COUNT(*) - COUNT(DISTINCT issue) as potential_duplicates,
                    ROUND((COUNT(*) - COUNT(DISTINCT issue)) / COUNT(*) * 100, 2) as duplicate_ratio_pct
                FROM `wprojectl.pc28.draws_clean`
                WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """,

            "source_duplication_analysis": """
                SELECT
                    source,
                    COUNT(*) as total_records,
                    COUNT(DISTINCT issue) as unique_issues,
                    ROUND(COUNT(DISTINCT issue) / COUNT(*) * 100, 2) as uniqueness_ratio
                FROM `wprojectl.pc28.draws_clean`
                WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
                GROUP BY source
                ORDER BY uniqueness_ratio ASC
            """,

            "time_gap_analysis": """
                WITH time_gaps AS (
                    SELECT
                        issue,
                        timestamp,
                        LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp,
                        TIMESTAMP_DIFF(timestamp, LAG(timestamp) OVER (ORDER BY timestamp), SECOND) as gap_seconds
                    FROM `wprojectl.pc28.draws_clean`
                    WHERE DATE(timestamp) = CURRENT_DATE()
                )
                SELECT
                    COUNT(*) as total_periods,
                    AVG(gap_seconds) as avg_gap_seconds,
                    MIN(gap_seconds) as min_gap_seconds,
                    MAX(gap_seconds) as max_gap_seconds,
                    COUNT(CASE WHEN gap_seconds < 180 THEN 1 END) as too_frequent_count,
                    COUNT(CASE WHEN gap_seconds > 240 THEN 1 END) as too_sparse_count
                FROM time_gaps
                WHERE gap_seconds IS NOT NULL
            """
        }

    async def enhanced_insert_with_deduplication(self, record):
        """增强的插入方法，内置去重检查"""
        try:
            # 1. 实时去重检查
            dup_check = await self.check_duplicates_realtime(record)

            if dup_check["is_duplicate"]:
                logger.info(f"跳过重复记录 {record.get('issue')}: {dup_check['reason']}")
                return {
                    "status": "duplicate_skipped",
                    "issue": record.get('issue'),
                    "reason": dup_check["reason"],
                    "details": dup_check
                }

            # 2. 添加去重元数据
            enhanced_record = record.copy()
            enhanced_record.update({
                'content_hash': dup_check.get('content_hash'),
                'dedup_checked': True,
                'dedup_timestamp': datetime.now().isoformat()
            })

            # 3. 执行插入
            return await self._safe_insert(enhanced_record)

        except Exception as e:
            logger.error(f"增强插入失败: {e}")
            return {"status": "error", "error": str(e)}

    async def _safe_insert(self, record):
        """安全插入单条记录"""
        try:
            # 构建插入查询
            insert_query = """
            INSERT INTO `wprojectl.pc28.draws_clean`
            (issue, timestamp, a, b, c, sum, tail, size, odd_even, patterns, source, created_at,
             api_codeid, api_message, api_curtime, kjtime_raw, next_issue, next_time, award_time, raw_api_response)
            VALUES
            (@issue, @timestamp, @a, @b, @c, @sum, @tail, @size, @odd_even, @patterns, @source, @created_at,
             @api_codeid, @api_message, @api_curtime, @kjtime_raw, @next_issue, @next_time, @award_time, @raw_api_response)
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("issue", "STRING", record['issue']),
                    bigquery.ScalarQueryParameter("timestamp", "TIMESTAMP", record['timestamp']),
                    bigquery.ScalarQueryParameter("a", "INTEGER", record['a']),
                    bigquery.ScalarQueryParameter("b", "INTEGER", record['b']),
                    bigquery.ScalarQueryParameter("c", "INTEGER", record['c']),
                    bigquery.ScalarQueryParameter("sum", "INTEGER", record['sum']),
                    bigquery.ScalarQueryParameter("tail", "INTEGER", record['tail']),
                    bigquery.ScalarQueryParameter("size", "STRING", record['size']),
                    bigquery.ScalarQueryParameter("odd_even", "STRING", record['odd_even']),
                    bigquery.ScalarQueryParameter("patterns", "STRING", record['patterns']),
                    bigquery.ScalarQueryParameter("source", "STRING", record['source']),
                    bigquery.ScalarQueryParameter("created_at", "TIMESTAMP", record['created_at']),
                    bigquery.ScalarQueryParameter("api_codeid", "INTEGER", record.get('api_codeid')),
                    bigquery.ScalarQueryParameter("api_message", "STRING", record.get('api_message', '')),
                    bigquery.ScalarQueryParameter("api_curtime", "INTEGER", record.get('api_curtime')),
                    bigquery.ScalarQueryParameter("kjtime_raw", "STRING", record.get('kjtime_raw')),
                    bigquery.ScalarQueryParameter("next_issue", "STRING", record.get('next_issue', '')),
                    bigquery.ScalarQueryParameter("next_time", "STRING", record.get('next_time')),
                    bigquery.ScalarQueryParameter("award_time", "INTEGER", record.get('award_time')),
                    bigquery.ScalarQueryParameter("raw_api_response", "STRING", record.get('raw_api_response', '')),
                ]
            )

            self.bq_client.query(insert_query, job_config=job_config).result()

            return {
                "status": "inserted",
                "issue": record['issue'],
                "content_hash": record.get('content_hash'),
                "inserted_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"安全插入失败: {e}")
            return {"status": "insert_failed", "error": str(e)}

# 使用示例
def get_deduplication_recommendations():
    """获取去重机制建议"""
    return """
    🔒 PC28 数据去重增强机制

    📋 多层次去重策略:
    1. 主键去重: issue 期号唯一性
    2. 复合键去重: issue + timestamp + a + b + c
    3. 内容哈希去重: 防止数据变异重复
    4. 时间窗口去重: 5分钟内相似记录检测

    ⚡ 性能优化:
    - 批量去重查询 (100条/批)
    - 实时单条记录去重检查
    - 数据库聚类和分区优化

    🔧 实施建议:
    1. 在所有数据入口启用去重检查
    2. 定期运行重复数据清理
    3. 监控去重效果和性能
    4. 设置重复数据告警

    📊 监控指标:
    - 每日重复率 < 0.1%
    - 去重检查耗时 < 100ms
    - 数据完整性 > 99.9%
    """

if __name__ == "__main__":
    dedup = EnhancedDeduplication()
    print(get_deduplication_recommendations())