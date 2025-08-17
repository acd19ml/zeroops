#

# utils for our web-agent

import re
import os
import subprocess
import signal
import time
import requests
import base64
import json
from ..base.utils import KwargsInitializable, rprint, zwarn, zlog
import pandas as pd
import numpy as np
from statsmodels.tsa.seasonal import STL
from datetime import datetime, timedelta
import json
import warnings

# --
# web state
class PromState:
    def __init__(self, **kwargs):
        # not-changed
        self.browser_id = ""
        self.page_id = ""
        self.target_url = ""
        self.target_prometheus_metrics = ""  # Add this for Prometheus
        
        # step info
        self.curr_step = 0  # step to the root
        self.curr_screenshot_mode = False  # whether we are using screenshot or not?
        self.total_actual_step = 0  # [no-rev] total actual steps including reverting (can serve as ID)
        self.num_revert_state = 0  # [no-rev] number of state reversion
        # (last) action information
        self.action_string = ""
        self.action = None
        self.error_message = ""
        # --
        self.update(**kwargs)

    def get_id(self):  # use these as ID
        return (self.browser_id, self.page_id, self.total_actual_step)

    def update(self, **kwargs):
        for k, v in kwargs.items():
            assert (k in self.__dict__), f"Attribute not found for {k} <- {v}"
        self.__dict__.update(**kwargs)

    def to_dict(self):
        return self.__dict__.copy()

    def copy(self):
        return PromState(**self.to_dict())

    def __repr__(self):
        return f"PromState({self.__dict__})"



# an opened web browser
class PromEnv(KwargsInitializable):
    def __init__(self, starting=True, starting_target_url=None, **kwargs):
        self.prom_ip = os.getenv("PROM_IP", "localhost:9090")  # allow set by ENV
        self.prom_timeout = 600  # set a timeout!
        self.target_url = starting_target_url if starting_target_url else "http://localhost:9090"  # default Prometheus URL
        # --
        super().__init__(**kwargs)
        # --
        self.state: PromState = None
        self.prom_metrics_path = ""
        # --
        if starting:
            self.start(starting_target_url)  # start at the beginning
        # --

    def start(self, target_url=None):
        self.stop()  # stop first
        # --
        target_url = target_url if target_url is not None else self.target_url  # otherwise use default
        self.init_state(target_url)

    def stop(self):
        # For Prometheus, we don't need to close browser
        # Just clean up the state
        self.state = None

    def __del__(self):
        self.stop()

    # note: return a copy!
    def get_state(self, export_to_dict=True, return_copy=True):
        assert self.state is not None, "Current state is None, should first start it!"
        if export_to_dict:
            ret = self.state.to_dict()
        elif return_copy:
            ret = self.state.copy()
        else:
            ret = self.state
        return ret

    def get_status(self):
        """Get Prometheus connection status and basic info"""
        try:
            # Test connection to Prometheus
            response = requests.get(f"http://{self.prom_ip}/api/v1/status/config", timeout=10)
            if response.status_code == 200:
                return {
                    "status": "connected",
                    "available_metrics": self._get_available_metrics(),
                    "query_history": getattr(self.state, 'query_history', []) if self.state else [],
                    "last_query_result": getattr(self.state, 'last_query_result', "N/A") if self.state else "N/A"
                }
            else:
                return {
                    "status": f"error: HTTP {response.status_code}",
                    "available_metrics": [],
                    "query_history": [],
                    "last_query_result": "N/A"
                }
        except Exception as e:
            return {
                "status": f"error: {e}",
                "available_metrics": [],
                "query_history": [],
                "last_query_result": "N/A"
            }

    def _get_available_metrics(self):
        """Get list of available metrics from Prometheus"""
        try:
            response = requests.get(f"http://{self.prom_ip}/api/v1/label/__name__/values", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])[:50]  # Limit to first 50 metrics
            else:
                return []
        except Exception as e:
            zwarn(f"Failed to get available metrics: {e}")
            return []

    def get_prom_data(self):
        return self.prom_metrics_path
    
    def prometheus_analysis(self, metrics_path):
        return self.prom_analysis_result

    def get_target_url(self):
        return self.target_url

    def step_state(self, action_string: str):
        """Execute a Prometheus action (placeholder for compatibility)"""
        return f"Executed action: {action_string}"

    def sync_files(self):
        """Sync any downloaded files (placeholder for Prometheus)"""
        # For Prometheus, this might not be needed, but keeping for compatibility
        pass

    def init_state(self, target_url: str):
        # For Prometheus, we don't need browser_id and page_id
        # Just initialize the state with basic information
        curr_step = 0
        state = PromState(
            browser_id="", 
            page_id="", 
            target_url=target_url, 
            curr_step=curr_step, 
            total_actual_step=curr_step,
            target_prometheus_metrics=target_url
        )  # start from 0
        # --
        self.state = state  # set the new state!
        # --

    def end_state(self):
        # For Prometheus, we don't need to close browser
        # Just clean up the state
        self.state = None



class AnomalyDetectionAPI:
    """异常检测接口类"""
    
    def __init__(self, data='yzh_mirror_data.csv'):
        """
        初始化异常检测接口
        
        Args:
            data_file: 数据文件路径
        """
        self.data = data
        self.df = None
        self.anomaly_results = []
        
    def load_data(self):
        """加载数据"""
        self.df = self.data
        self.df['Time'] = pd.to_datetime(self.df['Time'])
        self.df = self.df.sort_values('Time').reset_index(drop=True)
        
    def detect_anomalies(self, period=144, percentile_lower=0.5, percentile_upper=99.5):
        """
        使用STL分解进行异常检测
        
        Args:
            period: STL分解周期
            percentile_lower: 下分位数阈值
            percentile_upper: 上分位数阈值
        """
        
        # 设置时间索引
        df_temp = self.df.set_index('Time')
        
        # STL分解
        stl = STL(df_temp['Value'], period=period, robust=True)
        result = stl.fit()
        
        # 提取分解结果
        trend = result.trend
        seasonal = result.seasonal
        residual = result.resid
        
        # 计算分位数阈值
        lower_threshold = np.percentile(residual, percentile_lower)
        upper_threshold = np.percentile(residual, percentile_upper)
        
        # 检测异常
        anomalies = (residual < lower_threshold) | (residual > upper_threshold)
        anomaly_indices = anomalies[anomalies].index
        
        return anomaly_indices, residual, lower_threshold, upper_threshold
    
    def analyze_anomaly_intervals(self, anomaly_indices, residual, window_minutes=30):
        """
        分析异常区间，确定开始和结束时间
        
        Args:
            anomaly_indices: 异常点时间索引
            residual: 残差序列
            window_minutes: 异常区间窗口大小（分钟）
        """
        
        anomaly_intervals = []
        
        for anomaly_time in anomaly_indices:
            # 计算异常区间
            start_time = anomaly_time - timedelta(minutes=window_minutes)
            end_time = anomaly_time + timedelta(minutes=window_minutes)
            
            # 获取区间数据
            interval_data = self.df[(self.df['Time'] >= start_time) & (self.df['Time'] <= end_time)]
            
            if len(interval_data) > 0:
                # 计算异常描述信息
                anomaly_value = interval_data[interval_data['Time'] == anomaly_time]['Value'].iloc[0]
                anomaly_residual = residual[anomaly_time]
                
                # 计算区间统计信息
                interval_mean = interval_data['Value'].mean()
                interval_std = interval_data['Value'].std()
                
                # 判断异常类型和描述
                if anomaly_residual > 0:
                    anomaly_type = "偏高"
                    deviation = (anomaly_value - interval_mean) / interval_std if interval_std > 0 else 0
                else:
                    anomaly_type = "偏低"
                    deviation = (interval_mean - anomaly_value) / interval_std if interval_std > 0 else 0
                
                # 确定指标名称和单位（根据数据特征推断）
                metric_name = "yzh mirror指标"  # 可根据实际业务调整
                unit = "数值单位"  # 可根据实际业务调整
                
                # 生成异常描述
                if abs(deviation) > 3:
                    severity = "严重"
                elif abs(deviation) > 2:
                    severity = "明显"
                else:
                    severity = "轻微"
                
                anomaly_description = f"{severity}{anomaly_type}：{metric_name}在{anomaly_time.strftime('%Y-%m-%d %H:%M')}时达到{anomaly_value:.2f}{unit}，偏离正常值{deviation:.2f}个标准差"
                
                anomaly_intervals.append({
                    "label": "PromQL",
                    "timestamp_start": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "timestamp_end": end_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "异常描述": anomaly_description,
                    "异常类型": anomaly_type,
                    "异常值": anomaly_value,
                    "正常范围均值": interval_mean,
                    "偏离标准差数": deviation,
                    "异常强度": abs(anomaly_residual)
                })
        
        return anomaly_intervals
    
    def generate_anomaly_report(self, output_format='json'):
        """
        生成异常检测报告
        
        Args:
            output_format: 输出格式 ('json', 'csv', 'txt')
        """
        # 加载数据
        self.load_data()
        
        # 检测异常
        anomaly_indices, residual, lower_threshold, upper_threshold = self.detect_anomalies()
        
        # 分析异常区间
        anomaly_intervals = self.analyze_anomaly_intervals(anomaly_indices, residual)
        
        # 生成报告
        report = {
            "检测时间": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "数据文件": self.data_file,
            "数据时间范围": f"{self.df['Time'].min()} 到 {self.df['Time'].max()}",
            "总数据点数": len(self.df),
            "异常检测参数": {
                "下阈值分位数": 0.5,
                "上阈值分位数": 99.5,
                "下阈值": lower_threshold,
                "上阈值": upper_threshold
            },
            "异常区间数量": len(anomaly_intervals),
            "异常区间详情": anomaly_intervals
        }
        return report
    
    def get_anomaly_summary(self):
        """获取异常检测摘要"""
        report = self.generate_anomaly_report('json')
        
        return report

