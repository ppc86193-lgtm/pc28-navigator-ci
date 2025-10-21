#!/usr/bin/env python3
"""
PC28实时观察系统
让项目总指挥大人实时观察开奖和预测结果
"""

import asyncio
import time
from datetime import datetime
from google.cloud import bigquery

class PC28RealtimeObserver:
    """PC28实时观察器"""
    
    def __init__(self):
        self.project_id = "wprojectl"
        self.location = "us-central1"
        self.bq_client = bigquery.Client(project=self.project_id, location=self.location)
        
        print("👁️ PC28实时观察系统启动")
        print("🎯 为项目总指挥大人提供实时观察")
        print("📊 观察内容: 开奖结果 + 预测信号")
    
    def get_latest_draw_result(self):
        """获取最新开奖结果"""
        try:
            query = """
            SELECT 
              issue as period,
              timestamp,
              a, b, c,
              (a + b + c) as sum,
              CASE WHEN (a + b + c) >= 14 THEN 'big' ELSE 'small' END as size,
              CASE WHEN MOD(a + b + c, 2) = 0 THEN 'even' ELSE 'odd' END as oe
            FROM `wprojectl.pc28.draws_14w_dedup_v`
            WHERE DATE(timestamp, 'Asia/Shanghai') = CURRENT_DATE('Asia/Shanghai')
            ORDER BY timestamp DESC
            LIMIT 1
            """
            
            results = list(self.bq_client.query(query).result())
            if results:
                row = results[0]
                return {
                    "period": row.period,
                    "timestamp": row.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "numbers": [row.a, row.b, row.c],
                    "sum": row.sum,
                    "size": row.size,
                    "oe": row.oe,
                    "status": "AVAILABLE"
                }
            else:
                return {"status": "NO_DATA"}
                
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
    
    def get_latest_prediction(self):
        """获取最新预测信号"""
        try:
            query = """
            SELECT 
              period,
              tier_candidate,
              p_star_ens,
              keyB,
              ts_cst,
              (1.95 * p_star_ens - 1.0) as expected_ev
            FROM `wprojectl.pc28.candidates_today_dedup_v`
            WHERE keyB = TRUE
            ORDER BY ts_utc DESC
            LIMIT 1
            """
            
            results = list(self.bq_client.query(query).result())
            if results:
                row = results[0]
                return {
                    "period": row.period,
                    "tier": row.tier_candidate,
                    "probability": float(row.p_star_ens),
                    "expected_ev": float(row.expected_ev),
                    "timestamp": row.ts_cst,
                    "b_key_passed": row.keyB,
                    "status": "AVAILABLE"
                }
            else:
                return {"status": "NO_SIGNALS"}
                
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
    
    def format_observation_report(self, draw_data, prediction_data):
        """格式化观察报告"""
        report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report = f"""
🎯 PC28实时观察报告
时间: {report_time}

📊 最新开奖:
"""
        
        if draw_data.get("status") == "AVAILABLE":
            report += f"""   期号: {draw_data['period']}
   时间: {draw_data['timestamp']}
   号码: {draw_data['numbers'][0]}, {draw_data['numbers'][1]}, {draw_data['numbers'][2]}
   和值: {draw_data['sum']}
   大小: {draw_data['size']}
   奇偶: {draw_data['oe']}
"""
        else:
            report += f"   状态: {draw_data.get('status', 'UNKNOWN')}\n"
        
        report += f"""
🎲 最新预测:
"""
        
        if prediction_data.get("status") == "AVAILABLE":
            report += f"""   期号: {prediction_data['period']}
   时间: {prediction_data['timestamp']}
   等级: {prediction_data['tier']}
   概率: {prediction_data['probability']:.3f}
   期望收益: {prediction_data['expected_ev']:.3f}
   B钥: {'✅ 通过' if prediction_data['b_key_passed'] else '❌ 未通过'}
"""
        else:
            report += f"   状态: {prediction_data.get('status', 'UNKNOWN')}\n"
        
        return report
    
    async def start_realtime_observation(self, duration_minutes=10):
        """开始实时观察"""
        print(f"\n👁️ 开始实时观察 (持续{duration_minutes}分钟)")
        print("🎯 为项目总指挥大人实时显示开奖和预测")
        print("=" * 60)
        
        observation_count = 0
        start_time = time.time()
        
        while time.time() - start_time < duration_minutes * 60:
            observation_count += 1
            
            print(f"\n📊 观察轮次 {observation_count}:")
            
            # 获取最新开奖
            draw_data = self.get_latest_draw_result()
            
            # 获取最新预测
            prediction_data = self.get_latest_prediction()
            
            # 生成观察报告
            report = self.format_observation_report(draw_data, prediction_data)
            print(report)
            
            # 保存观察记录
            observation_record = {
                "observation_time": datetime.now().isoformat(),
                "observation_count": observation_count,
                "draw_data": draw_data,
                "prediction_data": prediction_data
            }
            
            # 等待下次观察 (30秒间隔)
            print(f"⏰ 等待30秒后继续观察...")
            await asyncio.sleep(30)
        
        print(f"\n🏁 实时观察完成！总共观察 {observation_count} 次")
        return observation_count

async def main():
    """主观察函数"""
    print("👁️ PC28实时观察系统")
    print("🎯 为项目总指挥大人提供实时观察")
    print()
    
    observer = PC28RealtimeObserver()
    
    # 先显示当前状态
    print("📊 当前状态快照:")
    draw_data = observer.get_latest_draw_result()
    prediction_data = observer.get_latest_prediction()
    
    current_report = observer.format_observation_report(draw_data, prediction_data)
    print(current_report)
    
    # 询问是否开始持续观察
    print("\n🎯 开始实时观察? (将持续显示开奖和预测)")
    
    # 开始5分钟的实时观察演示
    await observer.start_realtime_observation(duration_minutes=5)

if __name__ == "__main__":
    asyncio.run(main())
