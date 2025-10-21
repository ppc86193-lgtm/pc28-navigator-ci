#!/usr/bin/env python3
"""
PC28 开奖数据服务 - 优化版
- 简洁高效的代码结构
- 完整的API字段利用
- 优化的历史数据回填
- 可靠的错误处理
"""

import asyncio
import aiohttp
import os
import time
import hashlib
import json
from flask import Flask, jsonify, request
from datetime import datetime, timedelta
from google.cloud import bigquery
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bq_client = bigquery.Client(project="wprojectl", location="us-central1")

class PC28APIOptimized:
    """优化的PC28 API客户端"""

    def __init__(self):
        self.appid = "45928"
        self.key = "ca9edbfee35c22a0d6c4cf6722506af0"
        self.base_url = "https://rijb.api.storeapi.net/api/119"

    def _generate_sign(self, params):
        """生成API签名"""
        filtered_params = {k: v for k, v in params.items() if v is not None and v != ''}
        sorted_params = sorted(filtered_params.items())
        sign_string = "".join([f"{k}{v}" for k, v in sorted_params]) + self.key
        return hashlib.md5(sign_string.encode()).hexdigest()

    async def _make_request(self, endpoint, **kwargs):
        """统一的API请求方法"""
        timestamp = str(int(time.time()))
        params = {
            'appid': self.appid,
            'format': 'json',
            'time': timestamp,
            **kwargs
        }
        params['sign'] = self._generate_sign(params)

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(f"{self.base_url}/{endpoint}", params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('codeid') == 10000:
                            return data
                        else:
                            logger.error(f"API错误 {endpoint}: {data.get('message', 'unknown')}")
                    else:
                        logger.error(f"HTTP错误 {endpoint}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"请求异常 {endpoint}: {e}")
            return None

    async def get_realtime_draw(self):
        """获取实时开奖数据"""
        return await self._make_request("259")

    async def get_historical_draws(self, date=None, limit=50):
        """获取历史开奖数据"""
        kwargs = {}
        if date:
            kwargs['date'] = date
        if limit:
            kwargs['limit'] = str(limit)
        return await self._make_request("260", **kwargs)

    async def get_lottery_info(self):
        """获取彩票信息"""
        return await self._make_request("261")

    def _parse_draw_data(self, api_response, source="realtime"):
        """解析开奖数据"""
        try:
            if source == "realtime":
                retdata = api_response.get('retdata', {})
                current = retdata.get('curent', {})
                next_data = retdata.get('next', {})
                numbers = current.get('number', [])

                if len(numbers) != 3:
                    return None

                return {
                    'draw_data': {
                        'issue': current.get('long_issue'),
                        'timestamp': current.get('kjtime', datetime.now().isoformat()),
                        'numbers': [int(n) for n in numbers],
                        'kjtime_raw': current.get('kjtime'),
                        'next_issue': str(next_data.get('next_issue', '')),
                        'next_time': next_data.get('next_time'),
                        'award_time': next_data.get('award_time')
                    },
                    'api_meta': {
                        'codeid': api_response.get('codeid'),
                        'message': api_response.get('message', ''),
                        'curtime': api_response.get('curtime'),
                        'raw_response': json.dumps(api_response, ensure_ascii=False)
                    }
                }

            elif source == "historical":
                retdata = api_response.get('retdata', [])
                if not isinstance(retdata, list):
                    return []

                parsed_draws = []
                for record in retdata:
                    numbers = record.get('number', [])
                    if len(numbers) == 3:
                        parsed_draws.append({
                            'draw_data': {
                                'issue': record.get('long_issue'),
                                'timestamp': record.get('kjtime', datetime.now().isoformat()),
                                'numbers': [int(n) for n in numbers],
                                'kjtime_raw': record.get('kjtime'),
                                'next_issue': None,
                                'next_time': None,
                                'award_time': None
                            },
                            'api_meta': {
                                'codeid': api_response.get('codeid'),
                                'message': api_response.get('message', ''),
                                'curtime': api_response.get('curtime'),
                                'raw_response': json.dumps(record, ensure_ascii=False)
                            }
                        })
                return parsed_draws

            return None
        except Exception as e:
            logger.error(f"解析数据失败: {e}")
            return None

    def _build_bigquery_record(self, parsed_data, source):
        """构建BigQuery插入记录"""
        draw_data = parsed_data['draw_data']
        api_meta = parsed_data['api_meta']
        numbers = draw_data['numbers']
        total_sum = sum(numbers)

        return {
            # 基础数据
            'issue': draw_data['issue'],
            'timestamp': draw_data['timestamp'],
            'a': numbers[0],
            'b': numbers[1],
            'c': numbers[2],
            'sum': total_sum,
            'tail': total_sum % 10,
            'size': 'large' if total_sum > 13 else 'small',
            'odd_even': 'odd' if total_sum % 2 == 1 else 'even',
            'patterns': None,
            'source': source,
            'created_at': datetime.now().isoformat(),

            # API元数据
            'api_codeid': api_meta['codeid'],
            'api_message': api_meta['message'],
            'api_curtime': api_meta['curtime'],
            'kjtime_raw': draw_data['kjtime_raw'],
            'next_issue': draw_data['next_issue'],
            'next_time': draw_data['next_time'],
            'award_time': draw_data['award_time'],
            'raw_api_response': api_meta['raw_response']
        }

    def save_to_bigquery(self, records, check_duplicates=True):
        """增强的BigQuery保存方法 - 优化去重机制"""
        if not isinstance(records, list):
            records = [records]

        if not records:
            return 0

        # 批量去重检查 - 性能优化
        if check_duplicates and len(records) > 1:
            return self._batch_save_with_deduplication(records)

        # 单条记录保存
        saved_count = 0
        for record in records:
            try:
                if check_duplicates:
                    # 增强的去重检查
                    if self._is_duplicate_record(record):
                        logger.debug(f"跳过重复记录: {record.get('issue')}")
                        continue

                # 插入数据
                self._insert_record(record)
                saved_count += 1
                logger.info(f"保存成功: {record['issue']}")

            except Exception as e:
                logger.error(f"保存失败 {record.get('issue', 'unknown')}: {e}")
                continue

        return saved_count

    def _batch_save_with_deduplication(self, records):
        """批量保存with增强去重"""
        try:
            # 提取所有期号进行批量检查
            issues = [str(r.get('issue', '')) for r in records if r.get('issue')]

            if not issues:
                return 0

            # 批量查询已存在的期号 - 单次查询优化
            placeholders = ','.join([f"'{issue}'" for issue in issues])
            batch_query = f"""
            SELECT DISTINCT issue FROM `wprojectl.pc28.draws_clean`
            WHERE issue IN ({placeholders})
            """

            result = bq_client.query(batch_query).result()
            existing_issues = {row.issue for row in result}

            # 过滤新记录
            new_records = [
                record for record in records
                if str(record.get('issue', '')) not in existing_issues
            ]

            logger.info(f"批量去重: {len(records)} -> {len(new_records)} (过滤{len(records)-len(new_records)}重复)")

            # 批量插入新记录
            saved_count = 0
            for record in new_records:
                try:
                    self._insert_record(record)
                    saved_count += 1
                except Exception as e:
                    logger.error(f"批量插入失败 {record.get('issue')}: {e}")

            return saved_count

        except Exception as e:
            logger.error(f"批量去重保存失败: {e}")
            return 0

    def _is_duplicate_record(self, record):
        """增强的单条记录重复检查"""
        try:
            issue = record.get('issue')
            if not issue:
                return True  # 没有期号的记录视为重复

            # 1. 主键重复检查
            primary_query = """
            SELECT COUNT(*) as count FROM `wprojectl.pc28.draws_clean`
            WHERE issue = @issue
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("issue", "STRING", str(issue))
                ]
            )

            result = bq_client.query(primary_query, job_config=job_config).result()
            if next(iter(result)).count > 0:
                return True

            # 2. 内容相似度检查 (时间窗口内的相同数据)
            timestamp = record.get('timestamp', datetime.now().isoformat())
            a, b, c = record.get('a', 0), record.get('b', 0), record.get('c', 0)

            similarity_query = """
            SELECT COUNT(*) as count FROM `wprojectl.pc28.draws_clean`
            WHERE a = @a AND b = @b AND c = @c
            AND ABS(TIMESTAMP_DIFF(@record_time, timestamp, SECOND)) <= 300
            AND issue != @issue
            """

            similarity_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("a", "INTEGER", a),
                    bigquery.ScalarQueryParameter("b", "INTEGER", b),
                    bigquery.ScalarQueryParameter("c", "INTEGER", c),
                    bigquery.ScalarQueryParameter("record_time", "TIMESTAMP", timestamp),
                    bigquery.ScalarQueryParameter("issue", "STRING", str(issue))
                ]
            )

            similarity_result = bq_client.query(similarity_query, similarity_config).result()
            if next(iter(similarity_result)).count > 0:
                logger.warning(f"发现相似记录: {issue} [{a},{b},{c}] 在5分钟内")
                # 不直接拒绝，但记录警告
                return False

            return False  # 不是重复记录

        except Exception as e:
            logger.error(f"重复检查失败: {e}")
            return True  # 出错时谨慎处理，视为重复

    def _insert_record(self, record):
        """插入单条记录到BigQuery"""
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
                bigquery.ScalarQueryParameter("api_codeid", "INTEGER", record['api_codeid']),
                bigquery.ScalarQueryParameter("api_message", "STRING", record['api_message']),
                bigquery.ScalarQueryParameter("api_curtime", "INTEGER", record['api_curtime']),
                bigquery.ScalarQueryParameter("kjtime_raw", "STRING", record['kjtime_raw']),
                bigquery.ScalarQueryParameter("next_issue", "STRING", record['next_issue']),
                bigquery.ScalarQueryParameter("next_time", "STRING", record['next_time']),
                bigquery.ScalarQueryParameter("award_time", "INTEGER", record['award_time']),
                bigquery.ScalarQueryParameter("raw_api_response", "STRING", record['raw_api_response']),
            ]
        )

        bq_client.query(insert_query, job_config=job_config).result()


# 全局API客户端实例
api_client = PC28APIOptimized()

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({
        'status': 'healthy',
        'service': 'PC28 Optimized API Service',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0'
    })

@app.route('/fetch/realtime')
async def fetch_realtime():
    """获取并保存实时开奖数据"""
    try:
        api_response = await api_client.get_realtime_draw()
        if not api_response:
            return jsonify({'status': 'api_error'}), 500

        parsed = api_client._parse_draw_data(api_response, "realtime")
        if not parsed:
            return jsonify({'status': 'parse_error'}), 400

        record = api_client._build_bigquery_record(parsed, "api_realtime_optimized")
        saved_count = api_client.save_to_bigquery([record])

        return jsonify({
            'status': 'success' if saved_count > 0 else 'duplicate',
            'issue': record['issue'],
            'numbers': [record['a'], record['b'], record['c']],
            'sum': record['sum'],
            'kjtime': record['kjtime_raw'],
            'next_issue': record['next_issue'],
            'saved': saved_count > 0
        })

    except Exception as e:
        logger.error(f"实时数据获取失败: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/backfill/batch')
async def backfill_batch():
    """批量回填历史数据"""
    try:
        # 获取参数
        date = request.args.get('date')  # 格式: 2025-09-18
        days = int(request.args.get('days', 1))  # 回填天数
        limit_per_day = int(request.args.get('limit', 100))  # 每天最大记录数

        if not date:
            return jsonify({'status': 'error', 'message': '需要提供date参数'}), 400

        total_saved = 0
        total_processed = 0
        results = []

        # 处理多天回填
        base_date = datetime.strptime(date, '%Y-%m-%d')
        for i in range(days):
            target_date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')

            api_response = await api_client.get_historical_draws(target_date, limit_per_day)
            if not api_response:
                results.append({
                    'date': target_date,
                    'status': 'api_error',
                    'saved': 0,
                    'processed': 0
                })
                continue

            parsed_list = api_client._parse_draw_data(api_response, "historical")
            if not parsed_list:
                results.append({
                    'date': target_date,
                    'status': 'parse_error',
                    'saved': 0,
                    'processed': 0
                })
                continue

            # 构建记录并保存
            records = [
                api_client._build_bigquery_record(parsed, "api_historical_backfill")
                for parsed in parsed_list
            ]

            saved_count = api_client.save_to_bigquery(records)
            total_saved += saved_count
            total_processed += len(records)

            results.append({
                'date': target_date,
                'status': 'success',
                'saved': saved_count,
                'processed': len(records),
                'skipped': len(records) - saved_count
            })

            # 添加延时避免API限制
            if i < days - 1:
                await asyncio.sleep(1)

        return jsonify({
            'status': 'completed',
            'total_saved': total_saved,
            'total_processed': total_processed,
            'date_range': f"{date} - {(base_date + timedelta(days=days-1)).strftime('%Y-%m-%d')}",
            'results': results
        })

    except Exception as e:
        logger.error(f"批量回填失败: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/info/lottery')
async def get_lottery_info():
    """获取彩票信息"""
    try:
        info_data = await api_client.get_lottery_info()
        if info_data:
            return jsonify({
                'status': 'success',
                'lottery_info': info_data.get('retdata', {}),
                'api_status': info_data.get('message')
            })
        else:
            return jsonify({'status': 'api_error'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/backfill/smart')
async def smart_backfill():
    """智能历史数据回填 - 只回填缺失的数据"""
    try:
        days = int(request.json.get('days', 1) if request.is_json else request.args.get('days', 1))

        results = []
        total_saved = 0

        for i in range(days):
            target_date = (datetime.now() - timedelta(days=i+1)).strftime('%Y-%m-%d')

            # 检查当天数据完整性 - 使用精确期数
            expected_draws = 403  # 精确计算: 理论411期 - 维护期8期 (每期3.5分钟)
            existing_query = """
            SELECT COUNT(*) as count FROM `wprojectl.pc28.draws_clean`
            WHERE DATE(timestamp) = @date
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("date", "DATE", target_date)
                ]
            )

            result = bq_client.query(existing_query, job_config=job_config).result()
            existing_count = next(iter(result)).count
            missing_ratio = (expected_draws - existing_count) / expected_draws

            if missing_ratio > 0.05:  # 缺失5%以上才回填
                logger.info(f"日期 {target_date} 缺失 {missing_ratio:.1%} 数据，开始智能回填 (期望{expected_draws}期)")

                # 分批回填
                batch_saved = 0
                for batch_start in range(0, 300, 50):  # 每批50条，最多6批
                    api_response = await api_client.get_historical_draws(target_date, 50)
                    if not api_response:
                        break

                    parsed_list = api_client._parse_draw_data(api_response, "historical")
                    if not parsed_list:
                        break

                    # 批量检查重复
                    issues = [p['draw_data']['issue'] for p in parsed_list]
                    existing_issues = await check_existing_issues_batch(issues)

                    # 过滤新记录
                    new_records = [
                        api_client._build_bigquery_record(p, "api_smart_backfill")
                        for p in parsed_list
                        if p['draw_data']['issue'] not in existing_issues
                    ]

                    if new_records:
                        saved_count = api_client.save_to_bigquery(new_records, check_duplicates=False)
                        batch_saved += saved_count

                    await asyncio.sleep(1)  # 防止API限制

                    if len(parsed_list) < 50:  # 没有更多数据了
                        break

                total_saved += batch_saved
                results.append({
                    'date': target_date,
                    'existing': existing_count,
                    'expected': expected_draws,
                    'missing_ratio': f"{missing_ratio:.1%}",
                    'backfilled': batch_saved,
                    'status': 'backfilled'
                })
            else:
                results.append({
                    'date': target_date,
                    'existing': existing_count,
                    'expected': expected_draws,
                    'missing_ratio': f"{missing_ratio:.1%}",
                    'backfilled': 0,
                    'status': 'complete'
                })

        return jsonify({
            'status': 'success',
            'total_backfilled': total_saved,
            'results': results,
            'strategy': 'intelligent_gap_filling'
        })

    except Exception as e:
        logger.error(f"智能回填失败: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

async def check_existing_issues_batch(issues):
    """批量检查已存在的期号"""
    if not issues:
        return set()

    placeholders = ','.join([f"'{issue}'" for issue in issues])
    check_query = f"""
    SELECT DISTINCT issue FROM `wprojectl.pc28.draws_clean`
    WHERE issue IN ({placeholders})
    """

    result = bq_client.query(check_query).result()
    return {row.issue for row in result}

@app.route('/recovery/post-maintenance')
async def post_maintenance_recovery():
    """维护期后数据恢复"""
    try:
        current_time = datetime.now().time()
        maintenance_end = time(19, 30)

        # 检查是否刚过维护期
        if current_time < maintenance_end or current_time > time(20, 0):
            return jsonify({
                'status': 'skip',
                'message': '非维护恢复时间窗口',
                'current_time': current_time.isoformat()
            })

        logger.info("维护期后恢复检查开始")

        # 1. 立即拉取最新数据
        latest_data = await api_client.get_realtime_draw()
        if latest_data:
            parsed = api_client._parse_draw_data(latest_data, "realtime")
            if parsed:
                record = api_client._build_bigquery_record(parsed, "post_maintenance_recovery")
                saved = api_client.save_to_bigquery([record])
                logger.info(f"维护后立即拉取: {record['issue']}")

        # 2. 检查维护期间的数据缺失 (19:00-19:30)
        today = datetime.now().strftime('%Y-%m-%d')
        maintenance_gap_query = """
        SELECT COUNT(*) as count FROM `wprojectl.pc28.draws_clean`
        WHERE DATE(timestamp) = @date
        AND TIME(timestamp) BETWEEN '19:00:00' AND '19:30:00'
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("date", "DATE", today)
            ]
        )

        result = bq_client.query(maintenance_gap_query, job_config=job_config).result()
        maintenance_records = next(iter(result)).count

        # 维护期应该有0期开奖，但如果系统异常可能有遗漏
        gap_filled = 0
        if maintenance_records < 2:  # 预期维护期间数据很少
            # 尝试回填今日数据
            api_response = await api_client.get_historical_draws(today, 50)
            if api_response:
                parsed_list = api_client._parse_draw_data(api_response, "historical")
                if parsed_list:
                    # 只回填维护期间的数据
                    maintenance_records = [
                        api_client._build_bigquery_record(p, "maintenance_gap_fill")
                        for p in parsed_list
                        if '19:' in p['draw_data']['timestamp']
                    ]

                    if maintenance_records:
                        gap_filled = api_client.save_to_bigquery(maintenance_records)

        return jsonify({
            'status': 'success',
            'recovery_time': datetime.now().isoformat(),
            'latest_fetch': latest_data.get('curent', {}).get('long_issue') if latest_data else None,
            'maintenance_gap_filled': gap_filled,
            'next_action': 'resume_normal_schedule'
        })

    except Exception as e:
        logger.error(f"维护后恢复失败: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/schedule/status')
def schedule_status():
    """获取调度状态和建议"""
    try:
        current_time = datetime.now()
        current_time_only = current_time.time()

        # 判断当前状态
        is_active_period = time(0, 3, 46) <= current_time_only <= time(23, 58, 46)
        is_maintenance = time(19, 0) <= current_time_only <= time(19, 30)

        # 计算下次调度时间
        if is_maintenance:
            next_action_time = datetime.combine(current_time.date(), time(19, 31))
            next_action = "post_maintenance_recovery"
        elif not is_active_period:
            if current_time_only < time(0, 3, 46):
                next_action_time = datetime.combine(current_time.date(), time(0, 3, 46))
            else:
                next_action_time = datetime.combine(current_time.date() + timedelta(days=1), time(0, 3, 46))
            next_action = "resume_active_period"
        else:
            # 下次实时拉取时间 (2分钟间隔)
            next_action_time = current_time + timedelta(minutes=2)
            next_action = "realtime_fetch"

        return jsonify({
            'current_time': current_time.isoformat(),
            'status': {
                'active_period': is_active_period,
                'maintenance_window': is_maintenance,
                'should_fetch': is_active_period and not is_maintenance
            },
            'schedule': {
                'next_action': next_action,
                'next_action_time': next_action_time.isoformat(),
                'seconds_until_next': int((next_action_time - current_time).total_seconds())
            },
            'recommendations': {
                'realtime_frequency': '2分钟间隔',
                'historical_backfill': '每日01:00',
                'maintenance_recovery': '每日19:31'
            }
        })

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/stats')
def get_stats():
    """获取数据统计"""
    try:
        stats_query = """
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT source) as sources,
            MAX(timestamp) as latest_data,
            MIN(timestamp) as earliest_data,
            COUNT(CASE WHEN DATE(timestamp) = CURRENT_DATE() THEN 1 END) as today_count,
            COUNT(CASE WHEN source LIKE '%realtime%' THEN 1 END) as realtime_count,
            COUNT(CASE WHEN source LIKE '%historical%' THEN 1 END) as historical_count
        FROM `wprojectl.pc28.draws_clean`
        """

        result = bq_client.query(stats_query).result()
        stats = next(iter(result))

        return jsonify({
            'status': 'success',
            'total_records': stats.total_records,
            'data_sources': stats.sources,
            'latest_data': stats.latest_data.isoformat() if stats.latest_data else None,
            'earliest_data': stats.earliest_data.isoformat() if stats.earliest_data else None,
            'today_count': stats.today_count,
            'realtime_count': stats.realtime_count,
            'historical_count': stats.historical_count,
            'generated_at': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/validate/accuracy')
def validate_data_accuracy():
    """数据准确性验证 - 基于403期/天标准"""
    try:
        days_to_check = int(request.args.get('days', 7))
        results = []

        for i in range(days_to_check):
            target_date = (datetime.now() - timedelta(days=i)).date()

            # 详细数据分析
            accuracy_query = """
            SELECT
                COUNT(*) as actual_count,
                COUNT(CASE WHEN a + b + c = sum THEN 1 END) as sum_accurate_count,
                COUNT(CASE WHEN sum % 10 = tail THEN 1 END) as tail_accurate_count,
                COUNT(CASE WHEN
                    (sum > 13 AND size = 'large') OR
                    (sum <= 13 AND size = 'small')
                THEN 1 END) as size_accurate_count,
                COUNT(CASE WHEN
                    (sum % 2 = 1 AND odd_even = 'odd') OR
                    (sum % 2 = 0 AND odd_even = 'even')
                THEN 1 END) as odd_even_accurate_count,
                MIN(timestamp) as first_draw,
                MAX(timestamp) as last_draw,
                COUNT(DISTINCT source) as source_count,
                AVG(CASE WHEN api_codeid = 10000 THEN 1.0 ELSE 0.0 END) * 100 as api_success_rate
            FROM `wprojectl.pc28.draws_clean`
            WHERE DATE(timestamp) = @target_date
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("target_date", "DATE", target_date)
                ]
            )

            result = bq_client.query(accuracy_query, job_config=job_config).result()
            stats = next(iter(result))

            if stats.actual_count > 0:
                # 计算准确率
                sum_accuracy = (stats.sum_accurate_count / stats.actual_count) * 100
                tail_accuracy = (stats.tail_accurate_count / stats.actual_count) * 100
                size_accuracy = (stats.size_accurate_count / stats.actual_count) * 100
                odd_even_accuracy = (stats.odd_even_accurate_count / stats.actual_count) * 100

                # 计算完整性
                expected_draws = 403
                completeness = (stats.actual_count / expected_draws) * 100

                # 时间范围验证
                time_span_hours = 0
                if stats.first_draw and stats.last_draw:
                    time_span = stats.last_draw - stats.first_draw
                    time_span_hours = time_span.total_seconds() / 3600

                results.append({
                    "date": target_date.isoformat(),
                    "completeness": {
                        "expected_draws": expected_draws,
                        "actual_draws": stats.actual_count,
                        "completeness_pct": round(completeness, 1),
                        "missing_draws": expected_draws - stats.actual_count
                    },
                    "accuracy": {
                        "sum_calculation": round(sum_accuracy, 2),
                        "tail_calculation": round(tail_accuracy, 2),
                        "size_classification": round(size_accuracy, 2),
                        "odd_even_classification": round(odd_even_accuracy, 2),
                        "overall_accuracy": round((sum_accuracy + tail_accuracy + size_accuracy + odd_even_accuracy) / 4, 2)
                    },
                    "quality": {
                        "api_success_rate": round(stats.api_success_rate or 0, 1),
                        "data_sources": stats.source_count,
                        "time_span_hours": round(time_span_hours, 1),
                        "first_draw": stats.first_draw.isoformat() if stats.first_draw else None,
                        "last_draw": stats.last_draw.isoformat() if stats.last_draw else None
                    },
                    "status": "excellent" if completeness >= 98 and sum_accuracy >= 99.5
                             else "good" if completeness >= 95 and sum_accuracy >= 99
                             else "needs_attention"
                })
            else:
                results.append({
                    "date": target_date.isoformat(),
                    "completeness": {"expected_draws": 403, "actual_draws": 0, "completeness_pct": 0.0},
                    "accuracy": {"overall_accuracy": 0.0},
                    "quality": {"api_success_rate": 0.0},
                    "status": "no_data"
                })

        # 计算整体统计
        valid_days = [r for r in results if r["status"] != "no_data"]
        if valid_days:
            avg_completeness = sum(r["completeness"]["completeness_pct"] for r in valid_days) / len(valid_days)
            avg_accuracy = sum(r["accuracy"]["overall_accuracy"] for r in valid_days) / len(valid_days)

            return jsonify({
                "status": "success",
                "period": f"{days_to_check} days",
                "summary": {
                    "daily_expected_draws": 403,
                    "avg_completeness_pct": round(avg_completeness, 1),
                    "avg_accuracy_pct": round(avg_accuracy, 2),
                    "days_excellent": len([r for r in valid_days if r["status"] == "excellent"]),
                    "days_good": len([r for r in valid_days if r["status"] == "good"]),
                    "days_needs_attention": len([r for r in valid_days if r["status"] == "needs_attention"])
                },
                "daily_results": results,
                "recommendations": {
                    "target_completeness": "≥98% (≥396期/天)",
                    "target_accuracy": "≥99.5%",
                    "monitoring_frequency": "每日检查",
                    "alert_threshold": "<95% completeness or <99% accuracy"
                }
            })
        else:
            return jsonify({"status": "no_data", "message": "指定期间无有效数据"})

    except Exception as e:
        logger.error(f"数据准确性验证失败: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/enhance/field-utilization')
def enhance_field_utilization():
    """展示字段利用情况和增强建议"""
    try:
        # 分析最新数据的字段利用情况
        utilization_query = """
        SELECT
            COUNT(*) as total_records,
            COUNT(CASE WHEN api_codeid IS NOT NULL THEN 1 END) as has_api_codeid,
            COUNT(CASE WHEN api_message IS NOT NULL THEN 1 END) as has_api_message,
            COUNT(CASE WHEN kjtime_raw IS NOT NULL THEN 1 END) as has_kjtime_raw,
            COUNT(CASE WHEN next_issue IS NOT NULL AND next_issue != '' THEN 1 END) as has_next_issue,
            COUNT(CASE WHEN next_time IS NOT NULL THEN 1 END) as has_next_time,
            COUNT(CASE WHEN award_time IS NOT NULL THEN 1 END) as has_award_time,
            COUNT(CASE WHEN raw_api_response IS NOT NULL THEN 1 END) as has_raw_response,
            COUNT(DISTINCT source) as source_types
        FROM `wprojectl.pc28.draws_clean`
        WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
        """

        result = bq_client.query(utilization_query).result()
        stats = next(iter(result))

        if stats.total_records > 0:
            field_utilization = {
                "basic_fields": {
                    "issue_timestamp_abc": "100%",  # 基础字段总是完整
                    "sum_tail_size_odd_even": "100%"  # 计算字段总是完整
                },
                "api_fields": {
                    "api_codeid": f"{(stats.has_api_codeid / stats.total_records * 100):.1f}%",
                    "api_message": f"{(stats.has_api_message / stats.total_records * 100):.1f}%",
                    "kjtime_raw": f"{(stats.has_kjtime_raw / stats.total_records * 100):.1f}%",
                    "next_issue": f"{(stats.has_next_issue / stats.total_records * 100):.1f}%",
                    "next_time": f"{(stats.has_next_time / stats.total_records * 100):.1f}%",
                    "award_time": f"{(stats.has_award_time / stats.total_records * 100):.1f}%"
                },
                "audit_fields": {
                    "raw_api_response": f"{(stats.has_raw_response / stats.total_records * 100):.1f}%",
                    "data_sources": f"{stats.source_types} types"
                }
            }

            # 可以增强的字段建议
            enhancement_suggestions = [
                {
                    "field": "number_pattern",
                    "description": "号码模式分析 (豹子、对子、顺子等)",
                    "benefit": "提供更深入的号码特征分析",
                    "implementation": "基于a,b,c三个号码计算模式"
                },
                {
                    "field": "sum_range_category",
                    "description": "和值区间分类 (ultra_small: 0-4, small: 5-9, etc.)",
                    "benefit": "更精细的和值分析维度",
                    "implementation": "基于sum字段扩展分类"
                },
                {
                    "field": "time_slot_analysis",
                    "description": "时段分析 (上午、下午、晚上开奖特征)",
                    "benefit": "时间维度的开奖规律分析",
                    "implementation": "基于kjtime_raw提取时段信息"
                },
                {
                    "field": "consecutive_tracking",
                    "description": "连续期号跟踪和缺失检测",
                    "benefit": "自动化数据完整性监控",
                    "implementation": "基于issue字段序列分析"
                }
            ]

            return jsonify({
                "status": "success",
                "analysis_period": "最近3天",
                "total_records_analyzed": stats.total_records,
                "current_field_utilization": field_utilization,
                "enhancement_opportunities": enhancement_suggestions,
                "utilization_summary": {
                    "basic_coverage": "100% (完整)",
                    "api_coverage": f"{(stats.has_api_codeid / stats.total_records * 100):.1f}% (核心API字段)",
                    "audit_coverage": f"{(stats.has_raw_response / stats.total_records * 100):.1f}% (完整审计)",
                    "overall_rating": "excellent" if stats.has_raw_response / stats.total_records >= 0.95 else "good"
                }
            })

        else:
            return jsonify({"status": "no_data", "message": "最近3天无数据用于分析"})

    except Exception as e:
        logger.error(f"字段利用分析失败: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/dedup/monitor')
def deduplication_monitor():
    """去重效果监控"""
    try:
        days = int(request.args.get('days', 7))

        # 每日重复率分析
        duplicate_analysis_query = """
        SELECT
            DATE(timestamp) as date,
            COUNT(*) as total_records,
            COUNT(DISTINCT issue) as unique_issues,
            COUNT(*) - COUNT(DISTINCT issue) as duplicate_count,
            ROUND((COUNT(*) - COUNT(DISTINCT issue)) / COUNT(*) * 100, 3) as duplicate_rate_pct,
            COUNT(DISTINCT source) as source_count
        FROM `wprojectl.pc28.draws_clean`
        WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
        GROUP BY DATE(timestamp)
        ORDER BY date DESC
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INTEGER", days)
            ]
        )

        result = bq_client.query(duplicate_analysis_query, job_config=job_config).result()
        daily_stats = []
        total_duplicates = 0
        total_records = 0

        for row in result:
            daily_stats.append({
                "date": row.date.isoformat(),
                "total_records": row.total_records,
                "unique_issues": row.unique_issues,
                "duplicate_count": row.duplicate_count,
                "duplicate_rate_pct": row.duplicate_rate_pct,
                "source_count": row.source_count,
                "data_quality": "excellent" if row.duplicate_rate_pct == 0
                               else "good" if row.duplicate_rate_pct < 0.1
                               else "needs_attention"
            })
            total_duplicates += row.duplicate_count
            total_records += row.total_records

        # 数据源重复分析
        source_analysis_query = """
        SELECT
            source,
            COUNT(*) as total_records,
            COUNT(DISTINCT issue) as unique_issues,
            ROUND(COUNT(DISTINCT issue) / COUNT(*) * 100, 2) as uniqueness_pct
        FROM `wprojectl.pc28.draws_clean`
        WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
        GROUP BY source
        ORDER BY uniqueness_pct ASC
        """

        source_result = bq_client.query(source_analysis_query, job_config=job_config).result()
        source_stats = []

        for row in source_result:
            source_stats.append({
                "source": row.source,
                "total_records": row.total_records,
                "unique_issues": row.unique_issues,
                "uniqueness_pct": row.uniqueness_pct,
                "potential_duplicates": row.total_records - row.unique_issues,
                "quality_rating": "excellent" if row.uniqueness_pct >= 99.9
                                 else "good" if row.uniqueness_pct >= 99
                                 else "poor"
            })

        # 时间间隔分析 (检测异常频繁的数据)
        time_gap_query = """
        WITH time_gaps AS (
            SELECT
                issue,
                timestamp,
                LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp,
                TIMESTAMP_DIFF(timestamp, LAG(timestamp) OVER (ORDER BY timestamp), SECOND) as gap_seconds
            FROM `wprojectl.pc28.draws_clean`
            WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
        )
        SELECT
            COUNT(*) as total_intervals,
            ROUND(AVG(gap_seconds), 1) as avg_gap_seconds,
            MIN(gap_seconds) as min_gap_seconds,
            MAX(gap_seconds) as max_gap_seconds,
            COUNT(CASE WHEN gap_seconds < 180 THEN 1 END) as too_frequent_count,
            COUNT(CASE WHEN gap_seconds > 300 THEN 1 END) as too_sparse_count
        FROM time_gaps
        WHERE gap_seconds IS NOT NULL
        """

        gap_result = bq_client.query(time_gap_query).result()
        gap_stats = next(iter(gap_result))

        return jsonify({
            "status": "success",
            "analysis_period": f"{days} days",
            "summary": {
                "total_records": total_records,
                "total_duplicates": total_duplicates,
                "overall_duplicate_rate": round(total_duplicates / total_records * 100, 3) if total_records > 0 else 0,
                "deduplication_effectiveness": "excellent" if total_duplicates == 0 else "good"
            },
            "daily_analysis": daily_stats,
            "source_analysis": source_stats,
            "timing_analysis": {
                "avg_interval_seconds": gap_stats.avg_gap_seconds,
                "expected_interval": 210,
                "interval_variance": abs(gap_stats.avg_gap_seconds - 210) if gap_stats.avg_gap_seconds else 0,
                "anomalous_intervals": {
                    "too_frequent": gap_stats.too_frequent_count,
                    "too_sparse": gap_stats.too_sparse_count
                }
            },
            "recommendations": {
                "target_duplicate_rate": "0%",
                "monitoring_frequency": "每日检查",
                "alert_threshold": ">0.1% duplicate rate",
                "optimization_needed": total_duplicates > 0
            }
        })

    except Exception as e:
        logger.error(f"去重监控失败: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/dedup/cleanup')
def cleanup_duplicates():
    """重复数据清理"""
    try:
        dry_run = request.args.get('dry_run', 'true').lower() == 'true'

        # 查找重复记录
        duplicate_query = """
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
        LIMIT 20
        """

        result = bq_client.query(duplicate_query).result()
        duplicates = list(result)

        if not duplicates:
            return jsonify({
                "status": "no_duplicates",
                "message": "未发现重复记录",
                "cleanup_needed": False
            })

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
            return jsonify({
                "status": "dry_run_complete",
                "cleanup_plan": cleanup_plan,
                "summary": {
                    "duplicated_issues": len(duplicates),
                    "total_records_to_delete": total_to_delete,
                    "largest_duplicate_count": max(dup["duplicate_count"] for dup in cleanup_plan)
                },
                "next_step": "设置 dry_run=false 执行实际清理",
                "warning": "执行清理前请确认计划无误"
            })

        # 执行实际清理
        deleted_count = 0
        cleanup_results = []

        for dup_info in cleanup_plan:
            try:
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

                bq_client.query(delete_query, delete_config).result()
                deleted_count += dup_info["will_delete"]

                cleanup_results.append({
                    "issue": dup_info["issue"],
                    "deleted_count": dup_info["will_delete"],
                    "status": "success"
                })

            except Exception as e:
                logger.error(f"清理期号 {dup_info['issue']} 失败: {e}")
                cleanup_results.append({
                    "issue": dup_info["issue"],
                    "deleted_count": 0,
                    "status": "failed",
                    "error": str(e)
                })

        return jsonify({
            "status": "cleanup_completed",
            "summary": {
                "total_deleted": deleted_count,
                "issues_processed": len(cleanup_results),
                "success_count": len([r for r in cleanup_results if r["status"] == "success"]),
                "failure_count": len([r for r in cleanup_results if r["status"] == "failed"])
            },
            "cleanup_details": cleanup_results,
            "message": f"成功清理 {deleted_count} 条重复记录"
        })

    except Exception as e:
        logger.error(f"重复数据清理失败: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

# 兼容性路由 - 保持与旧版本的兼容
@app.route('/fetch/draws')
async def fetch_draws_legacy():
    """兼容旧版本的端点"""
    return await fetch_realtime()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"启动 PC28 优化服务，端口: {port}")
    app.run(host='0.0.0.0', port=port, debug=False)