"""
生产环境日志配置
支持结构化日志、日志轮转、多输出（文件、控制台、远程服务）
"""
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional


class ProductionLogger:
    """生产环境日志管理器"""
    
    def __init__(self, name: str = "agent_iam", log_level: Optional[str] = None):
        self.name = name
        self.log_level = log_level or os.environ.get("LOG_LEVEL", "INFO").upper()
        
        # 创建logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self._get_log_level())
        
        # 避免重复添加handler
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _get_log_level(self) -> int:
        """将字符串日志级别转换为logging常量"""
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        return level_map.get(self.log_level, logging.INFO)
    
    def _setup_handlers(self):
        """设置日志处理器"""
        # 日志格式
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(module)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器（标准输出）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # 文件处理器（日志轮转）
        log_dir = os.environ.get("LOG_DIR", "./logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # 应用日志文件
        app_log_file = os.path.join(log_dir, f"{self.name}.log")
        file_handler = logging.handlers.RotatingFileHandler(
            app_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # 错误日志文件（单独记录ERROR及以上级别）
        error_log_file = os.path.join(log_dir, f"{self.name}_error.log")
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)
        self.logger.addHandler(error_handler)
        
        # 如果配置了Sentry，添加Sentry处理器
        sentry_dsn = os.environ.get("SENTRY_DSN")
        if sentry_dsn:
            self._add_sentry_handler(sentry_dsn)
    
    def _add_sentry_handler(self, sentry_dsn: str):
        """添加Sentry错误监控（需要安装sentry-sdk）"""
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration
            
            # 初始化Sentry
            sentry_logging = LoggingIntegration(
                level=logging.INFO,          # 捕获INFO及以上级别
                event_level=logging.ERROR    # 发送ERROR及以上级别事件到Sentry
            )
            
            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[sentry_logging],
                traces_sample_rate=0.1,      # 性能监控采样率
                environment=os.environ.get("ENVIRONMENT", "production"),
                release=os.environ.get("RELEASE_VERSION", "1.0.0")
            )
            
            self.logger.info("Sentry日志监控已启用")
        except ImportError:
            self.logger.warning("Sentry SDK未安装，跳过Sentry监控")
    
    def debug(self, message: str, **kwargs):
        """记录调试日志"""
        self.logger.debug(self._format_message(message, **kwargs))
    
    def info(self, message: str, **kwargs):
        """记录信息日志"""
        self.logger.info(self._format_message(message, **kwargs))
    
    def warning(self, message: str, **kwargs):
        """记录警告日志"""
        self.logger.warning(self._format_message(message, **kwargs))
    
    def error(self, message: str, **kwargs):
        """记录错误日志"""
        self.logger.error(self._format_message(message, **kwargs))
    
    def critical(self, message: str, **kwargs):
        """记录严重错误日志"""
        self.logger.critical(self._format_message(message, **kwargs))
    
    def _format_message(self, message: str, **kwargs) -> str:
        """格式化日志消息（支持结构化日志）"""
        if not kwargs:
            return message
        
        # 结构化日志格式: message key1=value1 key2=value2
        structured_parts = [message]
        for key, value in kwargs.items():
            # 确保值可以安全转换为字符串
            try:
                structured_parts.append(f"{key}={value}")
            except:
                structured_parts.append(f"{key}=<unserializable>")
        
        return " | ".join(structured_parts)
    
    def log_performance(self, operation: str, duration_ms: float, **kwargs):
        """记录性能指标"""
        self.info(f"Performance: {operation}", 
                  duration_ms=duration_ms, 
                  operation=operation,
                  **kwargs)
    
    def log_security_event(self, event_type: str, actor_id: str, **kwargs):
        """记录安全事件"""
        self.warning(f"Security Event: {event_type}",
                     event_type=event_type,
                     actor_id=actor_id,
                     **kwargs)


# 全局日志实例
logger = ProductionLogger()


def setup_logging():
    """设置全局日志配置（供应用启动时调用）"""
    # 设置第三方库的日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("sentry_sdk").setLevel(logging.WARNING)
    
    logger.info("日志系统已初始化", 
                log_level=logger.log_level,
                environment=os.environ.get("ENVIRONMENT", "unknown"))


class AuditLoggerWrapper:
    """审计日志包装器（与现有审计日志集成）"""
    
    def __init__(self, audit_logger):
        self.audit_logger = audit_logger
        self.app_logger = logger
    
    def log_event(self, actor_id: str, action: str, resource: str, 
                 result: str, details: dict):
        """记录审计事件（同时记录到应用日志）"""
        # 调用原始审计日志
        self.audit_logger.log_event(actor_id, action, resource, result, details)
        
        # 同时记录到应用日志
        log_method = self.app_logger.info if result == "allow" else self.app_logger.warning
        log_method(f"审计事件: {action}", 
                   actor_id=actor_id,
                   resource=resource,
                   result=result,
                   **details)


def send_alert(message: str, level: str = "ERROR", **kwargs):
    """发送告警（支持Slack、钉钉等）"""
    # 检查是否启用告警
    if os.environ.get("ALERTS_ENABLED", "false").lower() != "true":
        return
    
    alert_methods = []
    
    # Slack告警
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if slack_webhook:
        alert_methods.append(("slack", slack_webhook))
    
    # 钉钉告警（可选）
    dingtalk_webhook = os.environ.get("DINGTALK_WEBHOOK_URL")
    if dingtalk_webhook:
        alert_methods.append(("dingtalk", dingtalk_webhook))
    
    # 发送告警（简化实现，实际应该使用异步任务）
    for alert_type, webhook in alert_methods:
        try:
            # 这里应该实现具体的Webhook调用
            # 为了简化，只记录日志
            logger.warning(f"告警发送到{alert_type}: {message}", 
                          alert_type=alert_type,
                          alert_level=level,
                          **kwargs)
        except Exception as e:
            logger.error(f"发送告警失败: {e}", 
                        alert_type=alert_type,
                        error=str(e))


# 监控装饰器
def monitor_performance(operation_name: str):
    """性能监控装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                logger.log_performance(operation_name, duration_ms, success=True)
                return result
            except Exception as e:
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                logger.log_performance(operation_name, duration_ms, success=False, error=str(e))
                raise
        return wrapper
    return decorator


def get_logger(name: str = "agent_iam"):
    """获取日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        ProductionLogger: 日志记录器实例
    """
    return ProductionLogger(name)