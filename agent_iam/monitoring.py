"""
监控和指标收集模块
提供系统性能、业务指标和健康状态的监控
"""
import time
import psutil
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import threading
from dataclasses import dataclass, asdict
import json

from .logger import logger


@dataclass
class SystemMetrics:
    """系统指标数据类"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_usage_percent: float
    network_bytes_sent: int
    network_bytes_recv: int
    process_cpu_percent: float
    process_memory_mb: float
    process_threads: int
    process_open_files: int


@dataclass
class BusinessMetrics:
    """业务指标数据类"""
    timestamp: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time_ms: float
    active_sessions: int
    active_tokens: int
    feishu_api_calls: int
    feishu_api_errors: int
    org_sync_count: int
    user_login_count: int


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self.system_metrics: List[SystemMetrics] = []
        self.business_metrics: List[BusinessMetrics] = []
        self.request_counter = defaultdict(int)
        self.error_counter = defaultdict(str)
        self.lock = threading.RLock()
        
        # 初始化业务指标
        self.current_business_metrics = BusinessMetrics(
            timestamp=time.time(),
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            avg_response_time_ms=0.0,
            active_sessions=0,
            active_tokens=0,
            feishu_api_calls=0,
            feishu_api_errors=0,
            org_sync_count=0,
            user_login_count=0
        )
        
        logger.info("指标收集器已初始化", retention_hours=retention_hours)
    
    def collect_system_metrics(self):
        """收集系统指标"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / (1024 * 1024)
            memory_total_mb = memory.total / (1024 * 1024)
            
            # 磁盘使用情况
            disk = psutil.disk_usage('/')
            disk_usage_percent = disk.percent
            
            # 网络IO
            net_io = psutil.net_io_counters()
            network_bytes_sent = net_io.bytes_sent
            network_bytes_recv = net_io.bytes_recv
            
            # 进程信息
            process = psutil.Process()
            process_cpu_percent = process.cpu_percent()
            process_memory_info = process.memory_info()
            process_memory_mb = process_memory_info.rss / (1024 * 1024)
            process_threads = process.num_threads()
            process_open_files = len(process.open_files())
            
            metrics = SystemMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                memory_total_mb=memory_total_mb,
                disk_usage_percent=disk_usage_percent,
                network_bytes_sent=network_bytes_sent,
                network_bytes_recv=network_bytes_recv,
                process_cpu_percent=process_cpu_percent,
                process_memory_mb=process_memory_mb,
                process_threads=process_threads,
                process_open_files=process_open_files
            )
            
            with self.lock:
                self.system_metrics.append(metrics)
                self._cleanup_old_metrics()
            
            logger.debug("系统指标收集完成", 
                        cpu_percent=cpu_percent,
                        memory_percent=memory_percent)
            
            return metrics
            
        except Exception as e:
            logger.error("收集系统指标失败", error=str(e))
            return None
    
    def record_request(self, endpoint: str, method: str, status_code: int, 
                      duration_ms: float, success: bool = True):
        """记录API请求"""
        with self.lock:
            # 更新业务指标
            self.current_business_metrics.total_requests += 1
            if success:
                self.current_business_metrics.successful_requests += 1
            else:
                self.current_business_metrics.failed_requests += 1
            
            # 更新平均响应时间（加权平均）
            current_avg = self.current_business_metrics.avg_response_time_ms
            total_success = self.current_business_metrics.successful_requests
            if total_success > 0:
                new_avg = (current_avg * (total_success - 1) + duration_ms) / total_success
                self.current_business_metrics.avg_response_time_ms = new_avg
            
            # 记录请求计数器
            key = f"{method}:{endpoint}:{status_code}"
            self.request_counter[key] += 1
            
            # 如果失败，记录错误
            if not success or status_code >= 400:
                error_key = f"{method}:{endpoint}:{status_code}"
                if error_key not in self.error_counter:
                    self.error_counter[error_key] = f"Endpoint: {endpoint}, Method: {method}, Status: {status_code}"
            
            logger.debug("API请求已记录",
                        endpoint=endpoint,
                        method=method,
                        status_code=status_code,
                        duration_ms=duration_ms,
                        success=success)
    
    def record_feishu_api_call(self, success: bool = True):
        """记录飞书API调用"""
        with self.lock:
            self.current_business_metrics.feishu_api_calls += 1
            if not success:
                self.current_business_metrics.feishu_api_errors += 1
    
    def record_org_sync(self):
        """记录组织架构同步"""
        with self.lock:
            self.current_business_metrics.org_sync_count += 1
    
    def record_user_login(self):
        """记录用户登录"""
        with self.lock:
            self.current_business_metrics.user_login_count += 1
    
    def set_active_sessions(self, count: int):
        """设置活动会话数"""
        with self.lock:
            self.current_business_metrics.active_sessions = count
    
    def set_active_tokens(self, count: int):
        """设置活动令牌数"""
        with self.lock:
            self.current_business_metrics.active_tokens = count
    
    def snapshot_business_metrics(self):
        """创建业务指标快照"""
        with self.lock:
            # 复制当前指标并重置计数器
            snapshot = BusinessMetrics(
                timestamp=time.time(),
                total_requests=self.current_business_metrics.total_requests,
                successful_requests=self.current_business_metrics.successful_requests,
                failed_requests=self.current_business_metrics.failed_requests,
                avg_response_time_ms=self.current_business_metrics.avg_response_time_ms,
                active_sessions=self.current_business_metrics.active_sessions,
                active_tokens=self.current_business_metrics.active_tokens,
                feishu_api_calls=self.current_business_metrics.feishu_api_calls,
                feishu_api_errors=self.current_business_metrics.feishu_api_errors,
                org_sync_count=self.current_business_metrics.org_sync_count,
                user_login_count=self.current_business_metrics.user_login_count
            )
            
            # 将快照添加到历史记录
            self.business_metrics.append(snapshot)
            
            # 重置部分计数器（保留活动计数）
            self.current_business_metrics.total_requests = 0
            self.current_business_metrics.successful_requests = 0
            self.current_business_metrics.failed_requests = 0
            self.current_business_metrics.avg_response_time_ms = 0.0
            self.current_business_metrics.feishu_api_calls = 0
            self.current_business_metrics.feishu_api_errors = 0
            self.current_business_metrics.org_sync_count = 0
            self.current_business_metrics.user_login_count = 0
            
            self._cleanup_old_metrics()
            
            logger.debug("业务指标快照已创建",
                        total_requests=snapshot.total_requests,
                        successful_requests=snapshot.successful_requests)
            
            return snapshot
    
    def _cleanup_old_metrics(self):
        """清理过期指标数据"""
        cutoff_time = time.time() - (self.retention_hours * 3600)
        
        # 清理系统指标
        self.system_metrics = [
            m for m in self.system_metrics 
            if m.timestamp >= cutoff_time
        ]
        
        # 清理业务指标
        self.business_metrics = [
            m for m in self.business_metrics
            if m.timestamp >= cutoff_time
        ]
    
    def get_system_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """获取系统指标摘要"""
        cutoff_time = time.time() - (hours * 3600)
        
        with self.lock:
            recent_metrics = [
                m for m in self.system_metrics
                if m.timestamp >= cutoff_time
            ]
        
        if not recent_metrics:
            return {"message": f"过去{hours}小时内无系统指标数据"}
        
        # 计算统计信息
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        response_times = [m.process_cpu_percent for m in recent_metrics]
        
        return {
            "time_range_hours": hours,
            "metric_count": len(recent_metrics),
            "cpu_percent": {
                "avg": sum(cpu_values) / len(cpu_values),
                "max": max(cpu_values),
                "min": min(cpu_values),
                "current": recent_metrics[-1].cpu_percent if recent_metrics else 0
            },
            "memory_percent": {
                "avg": sum(memory_values) / len(memory_values),
                "max": max(memory_values),
                "min": min(memory_values),
                "current": recent_metrics[-1].memory_percent if recent_metrics else 0
            },
            "process_cpu_percent": {
                "avg": sum(response_times) / len(response_times),
                "max": max(response_times),
                "min": min(response_times),
                "current": recent_metrics[-1].process_cpu_percent if recent_metrics else 0
            },
            "recent_metrics": [
                {
                    "timestamp": m.timestamp,
                    "cpu_percent": m.cpu_percent,
                    "memory_percent": m.memory_percent,
                    "process_memory_mb": m.process_memory_mb
                }
                for m in recent_metrics[-10:]  # 返回最近10个数据点
            ]
        }
    
    def get_business_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """获取业务指标摘要"""
        cutoff_time = time.time() - (hours * 3600)
        
        with self.lock:
            recent_metrics = [
                m for m in self.business_metrics
                if m.timestamp >= cutoff_time
            ]
        
        if not recent_metrics:
            return {
                "message": f"过去{hours}小时内无业务指标数据",
                "time_range_hours": hours,
                "metric_count": 0
            }
        
        # 聚合数据
        total_requests = sum(m.total_requests for m in recent_metrics)
        successful_requests = sum(m.successful_requests for m in recent_metrics)
        failed_requests = sum(m.failed_requests for m in recent_metrics)
        feishu_api_calls = sum(m.feishu_api_calls for m in recent_metrics)
        feishu_api_errors = sum(m.feishu_api_errors for m in recent_metrics)
        
        # 计算成功率
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        feishu_success_rate = ((feishu_api_calls - feishu_api_errors) / feishu_api_calls * 100) if feishu_api_calls > 0 else 0
        
        return {
            "time_range_hours": hours,
            "metric_count": len(recent_metrics),
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate_percent": round(success_rate, 2),
            "feishu_api_calls": feishu_api_calls,
            "feishu_api_errors": feishu_api_errors,
            "feishu_success_rate_percent": round(feishu_success_rate, 2),
            "org_sync_count": sum(m.org_sync_count for m in recent_metrics),
            "user_login_count": sum(m.user_login_count for m in recent_metrics),
            "current_active_sessions": self.current_business_metrics.active_sessions,
            "current_active_tokens": self.current_business_metrics.active_tokens,
            "request_distribution": dict(self.request_counter),
            "recent_errors": dict(self.error_counter)
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取系统健康状态"""
        try:
            # 收集当前系统指标
            current_metrics = self.collect_system_metrics()
            
            if not current_metrics:
                return {
                    "status": "unhealthy",
                    "message": "无法收集系统指标",
                    "timestamp": time.time()
                }
            
            # 检查健康状况
            issues = []
            
            if current_metrics.cpu_percent > 90:
                issues.append(f"CPU使用率过高: {current_metrics.cpu_percent}%")
            
            if current_metrics.memory_percent > 90:
                issues.append(f"内存使用率过高: {current_metrics.memory_percent}%")
            
            if current_metrics.disk_usage_percent > 90:
                issues.append(f"磁盘使用率过高: {current_metrics.disk_usage_percent}%")
            
            if current_metrics.process_memory_mb > 1024:  # 1GB
                issues.append(f"进程内存使用过高: {current_metrics.process_memory_mb:.2f}MB")
            
            status = "healthy" if not issues else "degraded"
            
            return {
                "status": status,
                "issues": issues,
                "timestamp": time.time(),
                "metrics": asdict(current_metrics)
            }
            
        except Exception as e:
            logger.error("获取健康状态失败", error=str(e))
            return {
                "status": "unhealthy",
                "message": f"健康检查失败: {str(e)}",
                "timestamp": time.time()
            }
    
    def export_metrics(self, filename: str = "metrics_export.json"):
        """导出所有指标数据"""
        try:
            with self.lock:
                data = {
                    "export_timestamp": time.time(),
                    "system_metrics": [asdict(m) for m in self.system_metrics],
                    "business_metrics": [asdict(m) for m in self.business_metrics],
                    "request_counter": dict(self.request_counter),
                    "error_counter": dict(self.error_counter),
                    "current_business_metrics": asdict(self.current_business_metrics)
                }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info("指标数据已导出", filename=filename)
            return True
            
        except Exception as e:
            logger.error("导出指标数据失败", error=str(e))
            return False


# 全局指标收集器实例
metrics_collector = MetricsCollector()


def start_metrics_collection_interval(interval_seconds: int = 60):
    """启动定期指标收集"""
    def collect_metrics():
        while True:
            try:
                # 收集系统指标
                metrics_collector.collect_system_metrics()
                
                # 创建业务指标快照
                metrics_collector.snapshot_business_metrics()
                
                logger.debug("定期指标收集完成", interval_seconds=interval_seconds)
                
            except Exception as e:
                logger.error("定期指标收集失败", error=str(e))
            
            time.sleep(interval_seconds)
    
    # 启动后台线程
    thread = threading.Thread(target=collect_metrics, daemon=True)
    thread.start()
    
    logger.info("定期指标收集已启动", interval_seconds=interval_seconds)
    return thread