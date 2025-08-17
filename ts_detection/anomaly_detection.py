import pandas as pd
import numpy as np
import json
from datetime import datetime
from statsmodels.tsa.seasonal import STL
import warnings
warnings.filterwarnings('ignore')

class AnomalyDetector:
    def __init__(self, lower_percentile=0.5, upper_percentile=99.5):
        """
        初始化异常检测器
        
        Args:
            lower_percentile (float): 下界百分位数，默认0.5%
            upper_percentile (float): 上界百分位数，默认99.5%
        """
        self.lower_percentile = lower_percentile
        self.upper_percentile = upper_percentile
    
    def load_data(self, file_path):
        """
        加载CSV数据文件
        
        Args:
            file_path (str): CSV文件路径
            
        Returns:
            pandas.DataFrame: 加载的数据
        """
        try:
            df = pd.read_csv(file_path)
            # 确保时间列格式正确
            df['time'] = pd.to_datetime(df['time'])
            return df
        except Exception as e:
            raise Exception(f"数据加载失败: {str(e)}")
    
    def stl_decomposition(self, data, period=None):
        """
        执行STL分解
        
        Args:
            data (array-like): 时间序列数据
            period (int): 季节性周期，如果为None则自动推断
            
        Returns:
            dict: 包含trend, seasonal, residual的字典
        """
        if period is None:
            # 自动推断周期，这里假设数据是3秒间隔，一天有28800个点
            # 可以根据实际数据调整
            period = min(len(data) // 4, 28800)  # 避免周期过大
        
        # 确保周期至少为2
        period = max(2, period)
        
        try:
            stl_result = STL(data, period=period, robust=True).fit()
            return {
                'trend': stl_result.trend,
                'seasonal': stl_result.seasonal,
                'residual': stl_result.resid
            }
        except Exception as e:
            # 如果STL分解失败，使用简单的移动平均作为趋势
            print(f"STL分解失败，使用移动平均替代: {str(e)}")
            trend = data.rolling(window=min(10, len(data)//10), center=True).mean()
            trend = trend.fillna(method='bfill').fillna(method='ffill')
            residual = data - trend
            return {
                'trend': trend,
                'seasonal': np.zeros_like(data),
                'residual': residual
            }
    
    def detect_anomalies(self, data, metric_name, host):
        """
        检测异常值
        
        Args:
            data (pandas.DataFrame): 包含time和value列的数据
            metric_name (str): 指标名称
            host (str): 主机地址
            
        Returns:
            list: 异常值列表
        """
        # 按时间排序
        data = data.sort_values('time').reset_index(drop=True)
        
        # 执行STL分解
        decomposition = self.stl_decomposition(data['value'].values)
        residuals = decomposition['residual']
        
        # 计算残差的百分位数
        lower_bound = np.percentile(residuals, self.lower_percentile)
        upper_bound = np.percentile(residuals, self.upper_percentile)
        
        # 找出异常值
        anomalies = []
        for idx, (time, value, residual) in enumerate(zip(data['time'], data['value'], residuals)):
            if residual < lower_bound or residual > upper_bound:
                # 判断异常类型
                if residual < lower_bound:
                    anomaly_type = "偏低"
                    threshold = lower_bound
                else:
                    anomaly_type = "偏高"
                    threshold = upper_bound
                
                # 获取单位（从指标名称推断）
                unit = self._extract_unit(metric_name)
                
                anomalies.append({
                    "label": f"{metric_name}{{host=\"{host}\"}}",  # PromQL格式
                    "host": host,
                    "startTime": time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "endTime": time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "异常描述": f"({metric_name},{unit},{anomaly_type})",
                    "original_value": float(value),
                    "residual": float(residual),
                    "threshold": float(threshold),
                    "anomaly_type": anomaly_type
                })
        
        return anomalies
    
    def _extract_unit(self, metric_name):
        """
        从指标名称中提取单位
        
        Args:
            metric_name (str): 指标名称
            
        Returns:
            str: 单位
        """
        metric_name_lower = metric_name.lower()
        
        if 'cpu' in metric_name_lower and 'percentage' in metric_name_lower:
            return "百分比"
        elif 'memory' in metric_name_lower:
            return "字节"
        elif 'disk' in metric_name_lower:
            return "字节"
        elif 'network' in metric_name_lower:
            return "字节/秒"
        elif 'response_time' in metric_name_lower or 'latency' in metric_name_lower:
            return "毫秒"
        else:
            return "单位"
    
    def process_file(self, file_path):
        """
        处理整个文件并检测异常
        
        Args:
            file_path (str): CSV文件路径
            
        Returns:
            dict: 包含异常检测结果的字典
        """
        # 加载数据
        df = self.load_data(file_path)
        
        # 按指标名称和主机分组
        results = []
        
        for (metric_name, host), group in df.groupby(['name', 'host']):
            anomalies = self.detect_anomalies(group, metric_name, host)
            results.extend(anomalies)
        
        return {
            "total_anomalies": len(results),
            "anomalies": results,
            "detection_params": {
                "lower_percentile": self.lower_percentile,
                "upper_percentile": self.upper_percentile,
                "method": "STL分解 + 百分位数检测"
            }
        }

def detect_cpu_anomalies():
    """
    检测CPU使用率异常值
    
    Returns:
        dict: 包含CPU异常检测结果的字典
    """
    import os
    detector = AnomalyDetector(lower_percentile=0.5, upper_percentile=99.5)
    try:
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, 'data', 'cpu_usage_percentage_filtered.csv')
        results = detector.process_file(file_path)
        return results
    except Exception as e:
        return {
            "error": f"CPU异常检测失败: {str(e)}",
            "total_anomalies": 0,
            "anomalies": [],
            "detection_params": {
                "lower_percentile": 0.5,
                "upper_percentile": 99.5,
                "method": "STL分解 + 百分位数检测"
            }
        }

def detect_memory_anomalies():
    """
    检测内存使用异常值
    
    Returns:
        dict: 包含内存异常检测结果的字典
    """
    import os
    detector = AnomalyDetector(lower_percentile=0.5, upper_percentile=99.5)
    try:
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, 'data', 'heap_memory_filtered.csv')
        results = detector.process_file(file_path)
        return results
    except Exception as e:
        return {
            "error": f"内存异常检测失败: {str(e)}",
            "total_anomalies": 0,
            "anomalies": [],
            "detection_params": {
                "lower_percentile": 0.5,
                "upper_percentile": 99.5,
                "method": "STL分解 + 百分位数检测"
            }
        }

def main():
    """
    主函数，演示如何使用异常检测器
    """
    # 检测CPU异常
    cpu_results = detect_cpu_anomalies()
    if "error" in cpu_results:
        print(f"CPU异常检测错误: {cpu_results['error']}")
    
    # 检测内存异常
    memory_results = detect_memory_anomalies()
    if "error" in memory_results:
        print(f"内存异常检测错误: {memory_results['error']}")
    
    # 如果没有错误，显示检测结果统计
    if "error" not in cpu_results and "error" not in memory_results:
        print(f"CPU异常检测完成，发现 {cpu_results['total_anomalies']} 个异常")
        print(f"内存异常检测完成，发现 {memory_results['total_anomalies']} 个异常")

if __name__ == "__main__":
    main()

