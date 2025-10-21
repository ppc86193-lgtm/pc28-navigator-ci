#!/usr/bin/env python3
import hashlib
import json
import logging
import os
import time
from datetime import datetime

import aiohttp
from flask import Flask, jsonify, request
from google.cloud import bigquery

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bq_client = bigquery.Client(project="wprojectl", location="us-central1")


class PC28APIClient:
    def __init__(self):
        self.appid = "45928"
        self.key = "ca9edbfee35c22a0d6c4cf6722506af0"
        self.api_base = "https://rijb.api.storeapi.net/api/119/259"

    def generate_sign(self, params: dict) -> str:
        """生成API签名"""
        # 按API文档要求对参数进行字典排序，空值不参与签名
        filtered_params = {k: v for k, v in params.items() if v is not None and v != ""}

        # 字典排序并拼接参数
        sorted_params = sorted(filtered_params.items())
        sign_string = ""
        for key, value in sorted_params:
            sign_string += f"{key}{value}"

        # 加上密钥
        sign_string += self.key
        return hashlib.md5(sign_string.encode()).hexdigest()

    async def get_latest_draw(self):
        """获取最新开奖数据"""
        timestamp = str(int(time.time()))
        params = {
            "appid": self.appid,
            "format": "json",
            "time": timestamp,
            "sign": self.generate_sign({"time": timestamp}),
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.api_base, params=params, timeout=10
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("codeid") == 10000:  # 成功状态码
                            return data
                        else:
                            logger.error(f"API返回错误: {data}")
                            return None
                    else:
                        logger.error(f"HTTP错误: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"API调用异常: {e}")
            return None

    async def get_historical_data(self, date=None, limit=30):
        """获取历史开奖数据"""
        timestamp = str(int(time.time()))

        params = {"appid": self.appid, "format": "json", "time": timestamp}

        if date:
            params["date"] = date
        if limit:
            params["limit"] = str(limit)

        params["sign"] = self.generate_sign(params)

        try:
            # 使用历史数据接口
            historical_url = "https://rijb.api.storeapi.net/api/119/260"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    historical_url, params=params, timeout=10
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("codeid") == 10000:
                            return data
                        else:
                            logger.error(f"历史数据API返回错误: {data}")
                            return None
                    else:
                        logger.error(f"历史数据HTTP错误: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"历史数据API调用异常: {e}")
            return None

    async def get_lottery_info(self):
        """获取彩票信息"""
        timestamp = str(int(time.time()))

        params = {"appid": self.appid, "format": "json", "time": timestamp}

        params["sign"] = self.generate_sign(params)

        try:
            # 使用彩票信息接口
            info_url = "https://rijb.api.storeapi.net/api/119/261"
            async with aiohttp.ClientSession() as session:
                async with session.get(info_url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("codeid") == 10000:
                            return data
                        else:
                            logger.error(f"彩票信息API返回错误: {data}")
                            return None
                    else:
                        logger.error(f"彩票信息HTTP错误: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"彩票信息API调用异常: {e}")
            return None

    def save_to_bigquery(self, draw_data: dict):
        """保存开奖数据到BigQuery - 完整利用所有API字段"""
        try:
            if not draw_data or draw_data.get("codeid") != 10000:
                return False

            # 解析当前期开奖数据 - 适应新API结构
            retdata = draw_data.get("retdata", {})
            current = retdata.get("curent", {})
            current_numbers = current.get("number", [])

            # 解析下期预测数据
            next_data = retdata.get("next", {})

            if len(current_numbers) != 3:
                logger.error(f"开奖号码不完整: {current_numbers}")
                return False

            # 构造完整插入数据 - 利用所有API字段
            numbers = [int(n) for n in current_numbers]
            total_sum = sum(numbers)

            current_row = {
                # 基础开奖数据
                "issue": current.get("long_issue"),
                "timestamp": current.get("kjtime", datetime.now().isoformat()),
                "a": numbers[0],
                "b": numbers[1],
                "c": numbers[2],
                "sum": total_sum,
                "tail": total_sum % 10,
                "size": "large" if total_sum > 13 else "small",
                "odd_even": "odd" if total_sum % 2 == 1 else "even",
                "patterns": None,
                "source": "api_realtime_complete",
                "created_at": datetime.now().isoformat(),
                # 完整API字段
                "api_codeid": draw_data.get("codeid"),
                "api_message": draw_data.get("message", ""),
                "api_curtime": draw_data.get("curtime"),
                "kjtime_raw": current.get("kjtime"),
                "next_issue": str(next_data.get("next_issue", "")),
                "next_time": next_data.get("next_time"),
                "award_time": next_data.get("award_time"),
                "raw_api_response": json.dumps(draw_data, ensure_ascii=False),
            }

            # 插入当前期开奖数据
            self._insert_draw_data(current_row)

            # 如果有下期数据，插入预测表
            if next_data and next_data.get("next_issue"):
                self._insert_next_period_info(
                    {
                        "current_issue": current.get("long_issue"),
                        "next_issue": str(next_data.get("next_issue", "")),
                        "next_time": next_data.get("next_time"),
                        "award_time": next_data.get("award_time"),
                        "created_at": datetime.now().isoformat(),
                    }
                )

            logger.info(f"保存完整开奖数据成功: {current_row['issue']}")
            return True

        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            return False

    def save_historical_data_to_bigquery(self, historical_data: dict):
        """保存历史开奖数据到BigQuery"""
        try:
            if not historical_data or historical_data.get("codeid") != 10000:
                return False, 0

            retdata = historical_data.get("retdata", [])
            if not isinstance(retdata, list):
                logger.error("历史数据格式错误，retdata不是数组")
                return False, 0

            saved_count = 0
            for draw_record in retdata:
                try:
                    numbers = draw_record.get("number", [])
                    if len(numbers) != 3:
                        logger.warning(
                            f"期号 {draw_record.get('long_issue')} 开奖号码不完整: {numbers}"
                        )
                        continue

                    # 构造历史数据插入记录
                    numbers_int = [int(n) for n in numbers]
                    total_sum = sum(numbers_int)

                    current_row = {
                        # 基础开奖数据
                        "issue": draw_record.get("long_issue"),
                        "timestamp": draw_record.get(
                            "kjtime", datetime.now().isoformat()
                        ),
                        "a": numbers_int[0],
                        "b": numbers_int[1],
                        "c": numbers_int[2],
                        "sum": total_sum,
                        "tail": total_sum % 10,
                        "size": "large" if total_sum > 13 else "small",
                        "odd_even": "odd" if total_sum % 2 == 1 else "even",
                        "patterns": None,
                        "source": "api_historical_backfill",
                        "created_at": datetime.now().isoformat(),
                        # API字段 - 历史数据结构
                        "api_codeid": historical_data.get("codeid"),
                        "api_message": historical_data.get("message", ""),
                        "api_curtime": historical_data.get("curtime"),
                        "kjtime_raw": draw_record.get("kjtime"),
                        "next_issue": None,
                        "next_time": None,
                        "award_time": None,
                        "raw_api_response": json.dumps(draw_record, ensure_ascii=False),
                    }

                    # 检查是否已存在该期号数据
                    check_query = """
                    SELECT COUNT(*) as count FROM `wprojectl.pc28.draws_clean`
                    WHERE issue = @issue
                    """
                    check_job_config = bigquery.QueryJobConfig(
                        query_parameters=[
                            bigquery.ScalarQueryParameter(
                                "issue", "STRING", current_row["issue"]
                            )
                        ]
                    )

                    result = bq_client.query(
                        check_query, job_config=check_job_config
                    ).result()
                    count = next(iter(result)).count

                    if count == 0:
                        # 数据不存在，插入新记录
                        self._insert_draw_data(current_row)
                        saved_count += 1
                        logger.info(f"保存历史数据: {current_row['issue']}")
                    else:
                        logger.debug(f"期号 {current_row['issue']} 已存在，跳过")

                except Exception as e:
                    logger.error(
                        f"处理历史记录失败 {draw_record.get('long_issue', 'unknown')}: {e}"
                    )
                    continue

            return True, saved_count

        except Exception as e:
            logger.error(f"保存历史数据失败: {e}")
            return False, 0

    def _insert_draw_data(self, row: dict):
        """插入开奖数据 - 完整利用所有API字段"""
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
                bigquery.ScalarQueryParameter("issue", "STRING", row["issue"]),
                bigquery.ScalarQueryParameter(
                    "timestamp", "TIMESTAMP", row["timestamp"]
                ),
                bigquery.ScalarQueryParameter("a", "INTEGER", row["a"]),
                bigquery.ScalarQueryParameter("b", "INTEGER", row["b"]),
                bigquery.ScalarQueryParameter("c", "INTEGER", row["c"]),
                bigquery.ScalarQueryParameter("sum", "INTEGER", row["sum"]),
                bigquery.ScalarQueryParameter("tail", "INTEGER", row["tail"]),
                bigquery.ScalarQueryParameter("size", "STRING", row["size"]),
                bigquery.ScalarQueryParameter("odd_even", "STRING", row["odd_even"]),
                bigquery.ScalarQueryParameter("patterns", "STRING", row["patterns"]),
                bigquery.ScalarQueryParameter("source", "STRING", row["source"]),
                bigquery.ScalarQueryParameter(
                    "created_at", "TIMESTAMP", row["created_at"]
                ),
                bigquery.ScalarQueryParameter(
                    "api_codeid", "INTEGER", row["api_codeid"]
                ),
                bigquery.ScalarQueryParameter(
                    "api_message", "STRING", row["api_message"]
                ),
                bigquery.ScalarQueryParameter(
                    "api_curtime", "INTEGER", row["api_curtime"]
                ),
                bigquery.ScalarQueryParameter(
                    "kjtime_raw", "STRING", row["kjtime_raw"]
                ),
                bigquery.ScalarQueryParameter(
                    "next_issue", "STRING", row["next_issue"]
                ),
                bigquery.ScalarQueryParameter("next_time", "STRING", row["next_time"]),
                bigquery.ScalarQueryParameter(
                    "award_time", "INTEGER", row["award_time"]
                ),
                bigquery.ScalarQueryParameter(
                    "raw_api_response", "STRING", row["raw_api_response"]
                ),
            ]
        )

        bq_client.query(insert_query, job_config=job_config).result()

    def _insert_next_period_info(self, next_info: dict):
        """插入下期信息到预测表"""
        insert_query = """
        INSERT INTO `wprojectl.pc28_monitor.next_period_schedule`
        (current_issue, next_issue, next_time, award_time, created_at)
        VALUES
        (@current_issue, @next_issue, @next_time, @award_time, @created_at)
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "current_issue", "STRING", next_info["current_issue"]
                ),
                bigquery.ScalarQueryParameter(
                    "next_issue", "STRING", next_info["next_issue"]
                ),
                bigquery.ScalarQueryParameter(
                    "next_time", "STRING", next_info["next_time"]
                ),
                bigquery.ScalarQueryParameter(
                    "award_time", "INTEGER", next_info.get("award_time")
                ),
                bigquery.ScalarQueryParameter(
                    "created_at", "TIMESTAMP", next_info["created_at"]
                ),
            ]
        )

        try:
            bq_client.query(insert_query, job_config=job_config).result()
            logger.info(f"保存下期信息成功: {next_info['next_issue']}")
        except Exception as e:
            logger.warning(f"保存下期信息失败 (可忽略): {e}")


api_client = PC28APIClient()


@app.route("/fetch/draws")
async def fetch_draws():
    """获取并保存最新开奖数据 - 完整版"""
    try:
        draw_data = await api_client.get_latest_draw()
        if draw_data:
            success = api_client.save_to_bigquery(draw_data)

            # 返回详细信息用于调试 - 适配新API结构
            retdata = draw_data.get("retdata", {})
            current = retdata.get("curent", {})
            next_data = retdata.get("next", {})

            return jsonify(
                {
                    "status": "success" if success else "failed",
                    "current_issue": current.get("long_issue"),
                    "current_numbers": current.get("number", []),
                    "kjtime": current.get("kjtime"),
                    "next_issue": next_data.get("next_issue"),
                    "next_time": next_data.get("next_time"),
                    "award_time": next_data.get("award_time"),
                    "api_message": draw_data.get("message"),
                    "saved": success,
                    "fields_captured": len(
                        [k for k in draw_data.keys() if draw_data[k] is not None]
                    ),
                }
            )
        else:
            return jsonify({"status": "no_data"}), 404
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/health")
def health():
    """健康检查"""
    return jsonify(
        {
            "status": "healthy",
            "service": "PC28 Realtime API Complete",
            "timestamp": datetime.now().isoformat(),
            "api_endpoint": api_client.api_base,
            "appid": api_client.appid,
        }
    )


@app.route("/api/test")
async def test_api():
    """测试API连接和字段完整性"""
    try:
        draw_data = await api_client.get_latest_draw()
        if draw_data:
            # 分析API字段利用情况
            expected_fields = [
                "award_time",
                "codeid",
                "curent",
                "kjtime",
                "long_issue",
                "message",
                "next",
                "next_issue",
                "next_time",
                "number",
                "retdata",
                "time",
            ]

            available_fields = list(draw_data.keys())
            missing_fields = [f for f in expected_fields if f not in available_fields]

            return jsonify(
                {
                    "status": "success",
                    "api_response": draw_data,
                    "field_analysis": {
                        "total_fields": len(available_fields),
                        "available_fields": available_fields,
                        "expected_fields": expected_fields,
                        "missing_fields": missing_fields,
                        "field_utilization": f"{len(available_fields)}/{len(expected_fields)} ({len(available_fields)/len(expected_fields)*100:.1f}%)",
                    },
                }
            )
        else:
            return jsonify({"status": "api_error"}), 500
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/backfill/historical")
async def backfill_historical():
    """回填历史开奖数据"""
    try:
        date = request.args.get("date")  # 格式: 2025-09-17
        limit = int(request.args.get("limit", 50))

        historical_data = await api_client.get_historical_data(date=date, limit=limit)
        if historical_data:
            success, saved_count = api_client.save_historical_data_to_bigquery(
                historical_data
            )

            return jsonify(
                {
                    "status": "success" if success else "failed",
                    "date": date,
                    "limit": limit,
                    "total_records": len(historical_data.get("retdata", [])),
                    "saved_count": saved_count,
                    "skipped_count": len(historical_data.get("retdata", []))
                    - saved_count,
                    "api_message": historical_data.get("message"),
                }
            )
        else:
            return jsonify({"status": "no_data"}), 404
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/info/lottery")
async def lottery_info():
    """获取彩票信息"""
    try:
        info_data = await api_client.get_lottery_info()
        if info_data:
            return jsonify(
                {
                    "status": "success",
                    "lottery_info": info_data,
                    "api_message": info_data.get("message"),
                }
            )
        else:
            return jsonify({"status": "no_data"}), 404
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/test/historical")
async def test_historical_api():
    """测试历史数据API连接"""
    try:
        # 测试今天的数据
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")

        historical_data = await api_client.get_historical_data(date=today, limit=5)
        if historical_data:
            return jsonify(
                {
                    "status": "success",
                    "date_tested": today,
                    "api_response": historical_data,
                    "total_records": len(historical_data.get("retdata", [])),
                }
            )
        else:
            return jsonify({"status": "api_error"}), 500
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
