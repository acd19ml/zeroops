#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试异常检测系统
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from .anomaly_detection import AnomalyDetector

def create_test_data():
    """创建测试数据"""
    # 生成时间序列
    start_time = datetime(2025, 8, 14, 13, 11, 1)
    times = [start_time + timedelta(seconds=i*3) for i in range(100)]
    
    # 生成正常数据（带有一些趋势和噪声）
    np.random.seed(42)
    base_trend = np.linspace(25, 30, 100)
    noise = np.random.normal(0, 0.5, 100)
    normal_values = base_trend + noise
    
    # 添加一些异常值
    normal_values[20] = 15.0  # 异常偏低
    normal_values[40] = 45.0  # 异常偏高
    normal_values[60] = 10.0  # 异常偏低
    normal_values[80] = 50.0  # 异常偏高
    
    # 创建DataFrame
    data = {
        'name': ['test_metric'] * 100,
        'host': ['test_host:8080'] * 100,
        'time': [t.strftime('%Y-%m-%dT%H:%M:%S+00:00') for t in times],
        'value': normal_values
    }
    
    df = pd.DataFrame(data)
    return df

def test_anomaly_detection():
    """测试异常检测功能"""
    print("开始测试异常检测系统...")
    
    # 创建测试数据
    test_df = create_test_data()
    test_file = 'test_data.csv'
    test_df.to_csv(test_file, index=False)
    
    print(f"创建测试数据文件: {test_file}")
    print(f"数据点数量: {len(test_df)}")
    print(f"包含4个预设异常值")
    
    # 创建检测器
    detector = AnomalyDetector(lower_percentile=0.5, upper_percentile=99.5)
    
    # 执行检测
    results = detector.process_file(test_file)
    
    print(f"\n检测结果:")
    print(f"总异常数: {results['total_anomalies']}")
    
    if results['total_anomalies'] > 0:
        print("\n检测到的异常值:")
        for i, anomaly in enumerate(results['anomalies'], 1):
            print(f"  {i}. {anomaly['startTime']} - {anomaly['异常描述']}")
            print(f"     原始值: {anomaly['original_value']:.2f}")
            print(f"     残差: {anomaly['residual']:.2f}")
            print(f"     阈值: {anomaly['threshold']:.2f}")
    
    # 验证结果
    expected_anomalies = 4  # 我们预设了4个异常值
    detected_anomalies = results['total_anomalies']
    
    print(f"\n验证结果:")
    print(f"预期异常数: {expected_anomalies}")
    print(f"检测到异常数: {detected_anomalies}")
    
    if detected_anomalies >= expected_anomalies:
        print("✅ 测试通过: 成功检测到异常值")
    else:
        print("❌ 测试失败: 未检测到足够的异常值")
    
    # 清理测试文件
    import os
    if os.path.exists(test_file):
        os.remove(test_file)
        print(f"已清理测试文件: {test_file}")

if __name__ == "__main__":
    test_anomaly_detection()
