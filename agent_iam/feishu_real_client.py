"""
真实飞书API客户端实现
"""
import os
import time
import json
from typing import Dict, Any, Optional
import requests
import jwt
from datetime import datetime, timedelta

from .error_handling import (
    error_handler, 
    with_retry, 
    with_circuit_breaker,
    RetryConfig,
    CircuitBreakerConfig,
    FeishuErrorHandler
)

try:
    import lark_oapi as lark
    # 导入必要的API模块
    try:
        from lark_oapi.api.calendar.v4 import *
        from lark_oapi.api.im.v1 import *
        from lark_oapi.api.contact.v3 import *
        from lark_oapi.api.drive.v1 import *
    except ImportError:
        # 如果子模块导入失败，SDK可能不完整，但继续
        pass
    LARK_SDK_AVAILABLE = True
except ImportError:
    LARK_SDK_AVAILABLE = False

TOKEN_EXPIRY_BUFFER = 300  # 5分钟

class RealFeishuAPIClient:
    """真实飞书API客户端"""
    
    def __init__(self, app_id: str = None, app_secret: str = None):
        # 读取环境变量或传入参数
        self.app_id = app_id or os.environ.get("FEISHU_APP_ID")
        self.app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")
        self.tenant_access_token = None
        self.token_expiry = 0
        
        # 错误处理配置
        self.retry_config = RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=10.0,
            strategy="exponential_backoff"
        )
        
        self.circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_requests=3,
            name="feishu_api"
        )
        
        # 初始化SDK客户端
        self.lark_client = None
        self._init_clients()
    
    def _init_clients(self):
        """初始化客户端"""
        if not self.app_id or not self.app_secret:
            raise ValueError("飞书App ID和App Secret必须配置")
        
        if LARK_SDK_AVAILABLE:
            # 使用官方SDK
            self.lark_client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .log_level(lark.LogLevel.INFO) \
                .build()
        else:
            # 使用HTTP API
            print("使用HTTP API模式，需要手动实现各API接口")
    
    @with_retry()
    @with_circuit_breaker("feishu_token_api")
    def _fetch_tenant_access_token_internal(self) -> Dict:
        """内部方法：获取租户访问令牌（带有错误处理）"""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        # 处理飞书API错误
        error_result = FeishuErrorHandler.handle_feishu_error(result, "get_tenant_access_token")
        if not error_result["success"]:
            raise Exception(f"获取token失败: {error_result['error']['message']}")
        
        return result
    
    def _get_tenant_access_token(self) -> str:
        """获取租户访问令牌"""
        if self.tenant_access_token and time.time() < self.token_expiry:
            return self.tenant_access_token
        
        try:
            # 使用带有错误处理的方法获取令牌
            result = self._fetch_tenant_access_token_internal()
            
            if result.get("code") == 0:
                self.tenant_access_token = result["tenant_access_token"]
                self.token_expiry = time.time() + result["expire"] - TOKEN_EXPIRY_BUFFER  # 提前5分钟过期
                return self.tenant_access_token
            else:
                raise Exception(f"获取token失败: {result.get('msg')}")
                
        except Exception as e:
            raise Exception(f"获取租户访问令牌失败: {e}")
    
    def _make_request(self, method: str, endpoint: str, 
                     data: Dict = None, params: Dict = None) -> Dict:
        """通用API请求方法"""
        token = self._get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=10)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=10)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, params=params, timeout=10)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API请求失败: {e}")
    
    # 日历相关API
    def get_calendar_events(self, calendar_id: str = "primary", 
                           start_time: str = None, end_time: str = None) -> Dict:
        """获取日历事件"""
        if not start_time:
            # 使用UTC时间格式，飞书API期望的时间格式
            start_time = datetime.utcnow().isoformat() + 'Z'
        if not end_time:
            end_time = (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z'
        
        # 如果提供了时间但缺少时区信息，添加Z后缀
        if start_time and 'Z' not in start_time and '+' not in start_time:
            start_time += 'Z'
        if end_time and 'Z' not in end_time and '+' not in end_time:
            end_time += 'Z'
        
        if self.lark_client and LARK_SDK_AVAILABLE:
            # 使用SDK
            req = ListCalendarEventRequest.builder() \
                .calendar_id(calendar_id) \
                .start_time(start_time) \
                .end_time(end_time) \
                .build()
            
            resp = self.lark_client.calendar.v4.calendar_event.list(req)
            return resp.__dict__
        else:
            # 使用HTTP API
            endpoint = f"calendar/v4/calendars/{calendar_id}/events"
            params = {
                "start_time": start_time,
                "end_time": end_time
            }
            return self._make_request("GET", endpoint, params=params)
    
    # 消息相关API
    def send_message(self, receive_id: str, msg_type: str, 
                    content: Dict, receive_id_type: str = "open_id") -> Dict:
        """发送消息"""
        if self.lark_client and LARK_SDK_AVAILABLE:
            req = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(CreateMessageRequestBody.builder()
                             .receive_id(receive_id)
                             .msg_type(msg_type)
                             .content(json.dumps(content))
                             .build()) \
                .build()
            
            resp = self.lark_client.im.v1.message.create(req)
            return resp.__dict__
        else:
            endpoint = "im/v1/messages"
            data = {
                "receive_id": receive_id,
                "msg_type": msg_type,
                "content": json.dumps(content),
                "receive_id_type": receive_id_type
            }
            return self._make_request("POST", endpoint, data=data)
    
    # 用户相关API
    def get_user_info(self, user_id: str, user_id_type: str = "open_id") -> Dict:
        """获取用户信息"""
        if self.lark_client and LARK_SDK_AVAILABLE:
            # 使用SDK
            req = GetUserRequest.builder() \
                .user_id(user_id) \
                .user_id_type(user_id_type) \
                .build()
            
            resp = self.lark_client.contact.v3.user.get(req)
            return resp.__dict__
        else:
            # 使用HTTP API
            endpoint = f"contact/v3/users/{user_id}"
            params = {"user_id_type": user_id_type}
            return self._make_request("GET", endpoint, params=params)
    
    # 文档相关API
    def create_document(self, folder_token: str, title: str) -> Dict:
        """创建文档"""
        endpoint = "drive/v1/files"
        data = {
            "folder_token": folder_token,
            "title": title,
            "type": "doc"
        }
        return self._make_request("POST", endpoint, data=data)
    
    def execute_feishu_command(self, command_type: str, subcommand: str,
                              params: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行飞书命令的统一接口"""
        params = params or {}
        
        try:
            if command_type == "calendar" and subcommand == "agenda":
                # 获取今日日程（使用UTC时间）
                today = datetime.utcnow().strftime("%Y-%m-%d")
                events = self.get_calendar_events(
                    start_time=f"{today}T00:00:00Z",  # UTC时间
                    end_time=f"{today}T23:59:59Z"     # UTC时间
                )
                return {
                    "success": True,
                    "data": events,
                    "source": "real_api"
                }
            
            elif command_type == "im" and subcommand == "send":
                # 发送消息
                result = self.send_message(
                    receive_id=params.get("to"),
                    msg_type="text",
                    content={"text": params.get("content", "")}
                )
                return {
                    "success": True,
                    "data": result,
                    "source": "real_api"
                }
            
            elif command_type == "contact" and subcommand == "search":
                # 搜索用户
                user_id = params.get("user_id")
                if user_id:
                    result = self.get_user_info(user_id)
                    return {
                        "success": True,
                        "data": result,
                        "source": "real_api"
                    }
            
            else:
                return {
                    "success": False,
                    "error": f"不支持的飞书命令: {command_type} {subcommand}",
                    "source": "real_api"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "source": "real_api"
            }