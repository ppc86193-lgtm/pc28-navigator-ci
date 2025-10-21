#!/usr/bin/env python3
import asyncio
import aiohttp
import os
import time
import hashlib
import json
from flask import Flask, jsonify
from datetime import datetime
from google.cloud import bigquery, secretmanager
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bq_client = bigquery.Client(project="wprojectl", location="us-central1")

class PC28APIClient:
    def __init__(self):
        self.appid = "45928"
        self.key = "ca9edbfee35c22a0d6c4cf6722506af0"
        self.api_base = "https://rijb.api.storeapi.net/api/119"

    def generate_sign(self, params: dict) -> str:
        """生成API签名"""
        # 按API文档要求: sign = MD5(appid + appid_value + format + format_value + time + time_value + key)
        timestamp = str(int(time.time()))
        sign_string = f"appid{self.appid}formatjsontime{timestamp}{self.key}"
        return hashlib.md5(sign_string.encode()).hexdigest()

    async def get_latest_draw(self):
        """获取最新开奖数据"""
        timestamp = str(int(time.time()))
        params = {
            'appid': self.appid,
            'format': 'json',
            'time': timestamp,
            'sign': self.generate_sign({'time': timestamp})
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_base, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('codeid') == 10000:  # 成功状态码
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

    def save_to_bigquery(self, draw_data: dict):
        """保存开奖数据到BigQuery"""
        try:
            if not draw_data or 'curent' not in draw_data:
                return False

            current = draw_data['curent']
            if not current or 'number' not in current:
                return False

            numbers = current['number']
            if len(numbers) != 3:
                return False

            # 构造插入数据
            row = {
                'issue': draw_data.get('long_issue'),
                'timestamp': datetime.now().isoformat(),
                'a': int(numbers[0]),
                'b': int(numbers[1]),
                'c': int(numbers[2]),
                'sum': sum([int(n) for n in numbers]),
                'source': 'api_realtime',
                'created_at': datetime.now().isoformat()
            }

            # 插入到draws_clean表
            insert_query = f"""
            INSERT INTO `wprojectl.pc28.draws_clean`
            (issue, timestamp, a, b, c, sum, source, created_at)
            VALUES
            ('{row['issue']}', '{row['timestamp']}', {row['a']}, {row['b']}, {row['c']}, {row['sum']}, '{row['source']}', '{row['created_at']}')
            """

            bq_client.query(insert_query).result()
            logger.info(f"保存开奖数据成功: {row['issue']}")
            return True

        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            return False

api_client = PC28APIClient()

@app.route('/fetch/draws')
async def fetch_draws():
    """获取并保存最新开奖数据"""
    try:
        draw_data = await api_client.get_latest_draw()
        if draw_data:
            success = api_client.save_to_bigquery(draw_data)
            return jsonify({
                'status': 'success' if success else 'failed',
                'data': draw_data,
                'saved': success
            })
        else:
            return jsonify({'status': 'no_data'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({
        'status': 'healthy',
        'service': 'PC28 Realtime API',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/')
def home():
    """首页"""
    return jsonify({
        'message': 'PC28 Realtime API Service',
        'endpoints': ['/fetch/draws', '/health']
    })

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)