"""
错误处理和重试机制模块
提供企业级的错误处理、重试策略和断路器模式
"""
import time
import logging
from typing import Any, Callable, TypeVar, Optional, Dict, List
from functools import wraps
from enum import Enum
from dataclasses import dataclass
import asyncio

from .logger import logger

T = TypeVar('T')


class RetryStrategy(Enum):
    """重试策略枚举"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 指数退避
    FIXED_INTERVAL = "fixed_interval"  # 固定间隔
    LINEAR_BACKOFF = "linear_backoff"  # 线性退避


class CircuitState(Enum):
    """断路器状态枚举"""
    CLOSED = "closed"  # 正常状态，请求通过
    OPEN = "open"  # 断路状态，请求被拒绝
    HALF_OPEN = "half_open"  # 半开状态，尝试恢复


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0  # 基础延迟（秒）
    max_delay: float = 30.0  # 最大延迟（秒）
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    retry_on_exceptions: tuple = (Exception,)  # 重试的异常类型
    
    def calculate_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        if self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        elif self.strategy == RetryStrategy.FIXED_INTERVAL:
            delay = self.base_delay
        elif self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = min(self.base_delay * attempt, self.max_delay)
        else:
            delay = self.base_delay
        
        # 添加随机抖动（避免惊群效应）
        jitter = delay * 0.1  # 10%的抖动
        delay += jitter
        
        return delay


@dataclass
class CircuitBreakerConfig:
    """断路器配置"""
    failure_threshold: int = 5  # 失败阈值
    recovery_timeout: float = 30.0  # 恢复超时（秒）
    half_open_max_requests: int = 3  # 半开状态最大请求数
    name: str = "default"  # 断路器名称


class CircuitBreaker:
    """断路器模式实现"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.half_open_success_count = 0
        self.lock = asyncio.Lock()
        
        logger.info(f"断路器已初始化: {config.name}", 
                   failure_threshold=config.failure_threshold,
                   recovery_timeout=config.recovery_timeout)
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """在断路器保护下执行函数"""
        async with self.lock:
            # 检查断路器状态
            if self.state == CircuitState.OPEN:
                # 检查是否应该尝试恢复
                if time.time() - self.last_failure_time > self.config.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_success_count = 0
                    logger.info(f"断路器进入半开状态: {self.config.name}")
                else:
                    raise CircuitBreakerOpenError(
                        f"断路器已打开: {self.config.name}",
                        self.config.name,
                        self.state.value
                    )
            
            # 执行函数
            try:
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                
                # 更新状态
                if self.state == CircuitState.HALF_OPEN:
                    self.half_open_success_count += 1
                    if self.half_open_success_count >= self.config.half_open_max_requests:
                        self.state = CircuitState.CLOSED
                        self.failure_count = 0
                        logger.info(f"断路器恢复正常状态: {self.config.name}")
                
                elif self.state == CircuitState.CLOSED:
                    # 重置失败计数
                    self.failure_count = 0
                
                return result
                
            except Exception as e:
                # 处理失败
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                logger.warning(f"断路器记录失败: {self.config.name}",
                             failure_count=self.failure_count,
                             error=str(e),
                             error_type=type(e).__name__)
                
                # 检查是否需要打开断路器
                if self.failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.error(f"断路器已打开: {self.config.name}",
                               failure_count=self.failure_count,
                               threshold=self.config.failure_threshold)
                
                raise
    
    def get_status(self) -> Dict[str, Any]:
        """获取断路器状态"""
        return {
            "name": self.config.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "half_open_success_count": self.half_open_success_count,
            "threshold": self.config.failure_threshold,
            "recovery_timeout": self.config.recovery_timeout
        }


class CircuitBreakerOpenError(Exception):
    """断路器打开异常"""
    
    def __init__(self, message: str, circuit_name: str, state: str):
        super().__init__(message)
        self.circuit_name = circuit_name
        self.state = state


def retry(config: RetryConfig = None):
    """
    重试装饰器
    
    Args:
        config: 重试配置，默认使用指数退避策略
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(1, config.max_retries + 2):  # 最大尝试次数 = 最大重试次数 + 1
                try:
                    result = await func(*args, **kwargs)
                    
                    # 如果成功且有重试，记录信息
                    if attempt > 1:
                        logger.info(f"重试成功: {func.__name__}",
                                   function=func.__name__,
                                   attempts=attempt,
                                   success=True)
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # 检查是否应该重试
                    should_retry = (
                        attempt <= config.max_retries and
                        isinstance(e, config.retry_on_exceptions)
                    )
                    
                    if should_retry:
                        # 计算延迟
                        delay = config.calculate_delay(attempt)
                        
                        logger.warning(f"重试中: {func.__name__}",
                                     function=func.__name__,
                                     attempt=attempt,
                                     max_retries=config.max_retries,
                                     delay=delay,
                                     error=str(e),
                                     error_type=type(e).__name__)
                        
                        # 等待重试
                        await asyncio.sleep(delay)
                    else:
                        # 不重试或已达到最大重试次数
                        logger.error(f"重试失败: {func.__name__}",
                                   function=func.__name__,
                                   attempts=attempt,
                                   max_retries=config.max_retries,
                                   error=str(e),
                                   error_type=type(e).__name__)
                        break
            
            # 所有重试都失败，抛出最后一个异常
            if last_exception:
                raise RetryExhaustedError(
                    f"重试耗尽: {func.__name__} 在 {config.max_retries} 次重试后失败",
                    func.__name__,
                    config.max_retries,
                    last_exception
                ) from last_exception
            else:
                raise RuntimeError(f"未知错误: {func.__name__}")
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(1, config.max_retries + 2):
                try:
                    result = func(*args, **kwargs)
                    
                    if attempt > 1:
                        logger.info(f"重试成功: {func.__name__}",
                                   function=func.__name__,
                                   attempts=attempt,
                                   success=True)
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    should_retry = (
                        attempt <= config.max_retries and
                        isinstance(e, config.retry_on_exceptions)
                    )
                    
                    if should_retry:
                        delay = config.calculate_delay(attempt)
                        
                        logger.warning(f"重试中: {func.__name__}",
                                     function=func.__name__,
                                     attempt=attempt,
                                     max_retries=config.max_retries,
                                     delay=delay,
                                     error=str(e),
                                     error_type=type(e).__name__)
                        
                        time.sleep(delay)
                    else:
                        logger.error(f"重试失败: {func.__name__}",
                                   function=func.__name__,
                                   attempts=attempt,
                                   max_retries=config.max_retries,
                                   error=str(e),
                                   error_type=type(e).__name__)
                        break
            
            if last_exception:
                raise RetryExhaustedError(
                    f"重试耗尽: {func.__name__} 在 {config.max_retries} 次重试后失败",
                    func.__name__,
                    config.max_retries,
                    last_exception
                ) from last_exception
            else:
                raise RuntimeError(f"未知错误: {func.__name__}")
        
        # 根据函数类型返回对应的包装器
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


class RetryExhaustedError(Exception):
    """重试耗尽异常"""
    
    def __init__(self, message: str, function_name: str, max_retries: int, last_exception: Exception):
        super().__init__(message)
        self.function_name = function_name
        self.max_retries = max_retries
        self.last_exception = last_exception


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.logger = logger
    
    def get_circuit_breaker(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """获取或创建断路器"""
        if name not in self.circuit_breakers:
            if config is None:
                config = CircuitBreakerConfig(name=name)
            self.circuit_breakers[name] = CircuitBreaker(config)
        
        return self.circuit_breakers[name]
    
    async def execute_with_circuit_breaker(self, circuit_name: str, func: Callable, 
                                          *args, **kwargs) -> Any:
        """使用断路器执行函数"""
        circuit_breaker = self.get_circuit_breaker(circuit_name)
        return await circuit_breaker.execute(func, *args, **kwargs)
    
    def execute_with_retry(self, func: Callable, config: RetryConfig = None, 
                          *args, **kwargs) -> Any:
        """使用重试执行函数"""
        retry_decorator = retry(config)
        decorated_func = retry_decorator(func)
        return decorated_func(*args, **kwargs)
    
    async def execute_with_retry_and_circuit_breaker(self, circuit_name: str, 
                                                    func: Callable, 
                                                    retry_config: RetryConfig = None,
                                                    *args, **kwargs) -> Any:
        """使用重试和断路器执行函数"""
        # 创建带重试的函数
        retry_decorator = retry(retry_config)
        retry_func = retry_decorator(func)
        
        # 使用断路器执行
        return await self.execute_with_circuit_breaker(circuit_name, retry_func, 
                                                      *args, **kwargs)
    
    def get_all_circuit_breaker_status(self) -> List[Dict[str, Any]]:
        """获取所有断路器状态"""
        return [cb.get_status() for cb in self.circuit_breakers.values()]
    
    def handle_api_error(self, error: Exception, context: str = "", 
                        retryable: bool = True) -> Dict[str, Any]:
        """处理API错误，返回标准格式的错误响应"""
        error_type = type(error).__name__
        error_message = str(error)
        
        # 根据错误类型分类
        if isinstance(error, (ConnectionError, TimeoutError)):
            error_category = "network"
            suggested_action = "检查网络连接并重试"
        elif isinstance(error, RetryExhaustedError):
            error_category = "retry_exhausted"
            suggested_action = "联系系统管理员"
        elif isinstance(error, CircuitBreakerOpenError):
            error_category = "circuit_breaker"
            suggested_action = "等待系统恢复或联系管理员"
        else:
            error_category = "unknown"
            suggested_action = "检查请求参数和系统状态"
        
        # 记录错误
        log_level = logging.ERROR if not retryable else logging.WARNING
        logger.log(log_level, f"API错误处理: {context}",
                  error_type=error_type,
                  error_message=error_message,
                  error_category=error_category,
                  context=context,
                  retryable=retryable)
        
        # 返回标准错误响应
        return {
            "success": False,
            "error": {
                "type": error_type,
                "message": error_message,
                "category": error_category,
                "context": context,
                "retryable": retryable,
                "suggested_action": suggested_action,
                "timestamp": time.time()
            }
        }


# 全局错误处理器实例
error_handler = ErrorHandler()


# 飞书API特定的错误处理器
class FeishuErrorHandler:
    """飞书API错误处理器"""
    
    # 飞书API错误码映射
    ERROR_CODE_MAP = {
        99991663: ("TOKEN_EXPIRED", "访问令牌已过期", True),
        99991664: ("TOKEN_INVALID", "访问令牌无效", True),
        99991668: ("NO_PERMISSION", "没有权限", False),
        99991669: ("RATE_LIMIT", "接口调用频率超限", True),
        99991672: ("APP_TICKET_INVALID", "app_ticket无效", False),
        99991673: ("APP_TICKET_EXPIRED", "app_ticket已过期", True),
        99991677: ("TENANT_ACCESS_TOKEN_INVALID", "租户访问令牌无效", True),
        99991678: ("TENANT_ACCESS_TOKEN_EXPIRED", "租户访问令牌过期", True),
    }
    
    @classmethod
    def handle_feishu_error(cls, error_data: Dict[str, Any], operation: str = "") -> Dict[str, Any]:
        """处理飞书API错误响应"""
        code = error_data.get("code", 0)
        msg = error_data.get("msg", "未知错误")
        
        if code == 0:
            # 成功，没有错误
            return {"success": True, "code": code}
        
        # 查找错误码映射
        error_info = cls.ERROR_CODE_MAP.get(code, ("UNKNOWN_ERROR", msg, False))
        error_type, error_message, retryable = error_info
        
        logger.error(f"飞书API错误: {operation}",
                    error_code=code,
                    error_message=msg,
                    error_type=error_type,
                    operation=operation,
                    retryable=retryable)
        
        return {
            "success": False,
            "error": {
                "code": code,
                "message": error_message,
                "type": error_type,
                "original_message": msg,
                "retryable": retryable,
                "operation": operation,
                "timestamp": time.time()
            }
        }
    
    @classmethod
    def should_retry_feishu_error(cls, error_data: Dict[str, Any]) -> bool:
        """检查飞书API错误是否应该重试"""
        code = error_data.get("code", 0)
        
        if code == 0:
            return False
        
        # 查找错误码映射
        error_info = cls.ERROR_CODE_MAP.get(code, ("UNKNOWN_ERROR", "", False))
        _, _, retryable = error_info
        
        return retryable


# 便捷装饰器
def with_retry(config: RetryConfig = None):
    """便捷的重试装饰器"""
    return retry(config)

def with_circuit_breaker(circuit_name: str, config: CircuitBreakerConfig = None):
    """便捷的断路器装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            return await error_handler.execute_with_circuit_breaker(
                circuit_name, func, *args, **kwargs
            )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # 同步函数需要转换为异步执行
            async def async_func():
                return func(*args, **kwargs)
            
            # 在当前事件循环中运行，如果没有则创建新的事件循环
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(
                error_handler.execute_with_circuit_breaker(circuit_name, async_func)
            )
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator