"""
飞书API客户端（遵循官方Python Server SDK规范）
提供企业级IAM系统与飞书平台的集成
"""
import os
import time
import json
import logging
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import lark_oapi as lark
from lark_oapi.api.contact.v3 import *
from lark_oapi.api.authen.v1 import *
from lark_oapi.api.application.v6 import *
from lark_oapi.api.calendar.v4 import *
from lark_oapi.api.im.v1 import *


logger = logging.getLogger(__name__)


class FeishuAppType(Enum):
    """飞书应用类型"""
    SELF_BUILT = "self_built"  # 自建应用
    ISV = "isv"  # 商店应用


@dataclass
class FeishuConfig:
    """飞书配置"""
    app_id: str
    app_secret: str
    app_type: FeishuAppType = FeishuAppType.SELF_BUILT
    app_ticket: Optional[str] = None  # 仅商店应用需要
    domain: str = lark.FEISHU_DOMAIN
    timeout: int = 10
    enable_set_token: bool = False
    log_level: lark.LogLevel = lark.LogLevel.INFO
    
    @classmethod
    def from_env(cls) -> "FeishuConfig":
        """从环境变量创建配置"""
        app_id = os.environ.get("FEISHU_APP_ID")
        app_secret = os.environ.get("FEISHU_APP_SECRET")
        
        if not app_id or not app_secret:
            raise ValueError("飞书App ID和App Secret必须配置在环境变量中")
        
        app_type_str = os.environ.get("FEISHU_APP_TYPE", "self_built")
        app_type = FeishuAppType(app_type_str)
        
        app_ticket = os.environ.get("FEISHU_APP_TICKET")
        
        return cls(
            app_id=app_id,
            app_secret=app_secret,
            app_type=app_type,
            app_ticket=app_ticket
        )


class FeishuClient:
    """飞书API客户端（遵循官方SDK规范）"""
    
    def __init__(self, config: Optional[FeishuConfig] = None):
        self.config = config or FeishuConfig.from_env()
        self.client = self._init_client()
        self._token_cache: Dict[str, Dict[str, Any]] = {}
    
    def _init_client(self) -> lark.Client:
        """初始化SDK客户端"""
        builder = lark.Client.builder() \
            .app_id(self.config.app_id) \
            .app_secret(self.config.app_secret) \
            .domain(self.config.domain) \
            .timeout(self.config.timeout) \
            .log_level(self.config.log_level)
        
        if self.config.app_type == FeishuAppType.ISV:
            builder = builder.app_type(lark.AppType.ISV)
            if self.config.app_ticket:
                builder = builder.app_ticket(self.config.app_ticket)
        
        if self.config.enable_set_token:
            builder = builder.enable_set_token(True)
        
        return builder.build()
    
    # ==================== 认证相关API ====================
    
    def get_tenant_access_token(self) -> str:
        """获取租户访问令牌（tenant_access_token）"""
        cache_key = "tenant_access_token"
        if cache_key in self._token_cache:
            token_data = self._token_cache[cache_key]
            if time.time() < token_data.get("expire_time", 0):
                return token_data["token"]
        
        # SDK会自动管理token，这里我们直接使用client调用API
        # 对于需要tenant_access_token的API，SDK会自动获取
        try:
            # 使用一个不需要权限的API来触发token获取
            request = GetApplicationRequest.builder().build()
            response = self.client.application.v6.application.get(request)
            
            if response.success():
                # SDK内部已经获取了token，我们可以通过client内部状态获取
                # 注意：SDK内部管理token，我们不直接暴露
                pass
        except Exception as e:
            logger.warning(f"获取租户访问令牌时发生错误: {e}")
        
        # 返回一个标记值，实际token由SDK内部管理
        return "SDK_MANAGED_TENANT_TOKEN"
    
    def get_user_access_token(self, code: str, grant_type: str = "authorization_code") -> Dict[str, Any]:
        """通过授权码获取用户访问令牌（OAuth2）"""
        request = CreateOidcAccessTokenRequest.builder() \
            .request_body(CreateOidcAccessTokenRequestBody.builder()
                         .grant_type(grant_type)
                         .code(code)
                         .build()) \
            .build()
        
        response = self.client.authen.v1.oidc_access_token.create(request)
        
        if not response.success():
            logger.error(f"获取用户访问令牌失败: {response.msg}")
            raise Exception(f"获取用户访问令牌失败: {response.msg}")
        
        return {
            "access_token": response.data.access_token,
            "token_type": response.data.token_type,
            "expires_in": response.data.expires_in,
            "refresh_token": response.data.refresh_token,
            "refresh_expires_in": response.data.refresh_expires_in
        }
    
    def refresh_user_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """刷新用户访问令牌"""
        request = CreateOidcRefreshAccessTokenRequest.builder() \
            .request_body(CreateOidcRefreshAccessTokenRequestBody.builder()
                         .grant_type("refresh_token")
                         .refresh_token(refresh_token)
                         .build()) \
            .build()
        
        response = self.client.authen.v1.oidc_refresh_access_token.create(request)
        
        if not response.success():
            logger.error(f"刷新用户访问令牌失败: {response.msg}")
            raise Exception(f"刷新用户访问令牌失败: {response.msg}")
        
        return {
            "access_token": response.data.access_token,
            "token_type": response.data.token_type,
            "expires_in": response.data.expires_in,
            "refresh_token": response.data.refresh_token,
            "refresh_expires_in": response.data.refresh_expires_in
        }
    
    def get_user_info(self, user_access_token: str) -> Dict[str, Any]:
        """获取用户信息"""
        request = GetUserInfoRequest.builder().build()
        
        # 设置用户访问令牌
        req_option = lark.RequestOption.builder() \
            .user_access_token(user_access_token) \
            .build()
        
        response = self.client.authen.v1.user_info.get(request, req_option)
        
        if not response.success():
            logger.error(f"获取用户信息失败: {response.msg}")
            raise Exception(f"获取用户信息失败: {response.msg}")
        
        return {
            "user_id": response.data.sub,
            "name": response.data.name,
            "avatar_url": response.data.picture,
            "email": response.data.email,
            "employee_id": response.data.employee_id,
            "mobile": response.data.mobile
        }
    
    # ==================== 组织架构相关API ====================
    
    def list_departments(self, parent_department_id: str = "0", 
                         fetch_child: bool = True) -> List[Dict[str, Any]]:
        """获取部门列表"""
        request = ListDepartmentRequest.builder() \
            .department_id_type("department_id") \
            .parent_department_id(parent_department_id) \
            .fetch_child(fetch_child) \
            .build()
        
        response = self.client.contact.v3.department.list(request)
        
        if not response.success():
            logger.error(f"获取部门列表失败: {response.msg}")
            raise Exception(f"获取部门列表失败: {response.msg}")
        
        departments = []
        for dept in response.data.items:
            departments.append({
                "department_id": dept.department_id,
                "name": dept.name,
                "parent_department_id": dept.parent_department_id,
                "leader_user_id": dept.leader_user_id,
                "member_count": dept.member_count,
                "status": dept.status.department_status if dept.status else None
            })
        
        return departments
    
    def list_users(self, department_id: str = None, page_size: int = 100, 
                  page_token: str = None) -> Dict[str, Any]:
        """获取用户列表"""
        request = ListUserRequest.builder() \
            .department_id(department_id) \
            .page_size(page_size) \
            .page_token(page_token) \
            .user_id_type("user_id") \
            .department_id_type("department_id") \
            .build()
        
        response = self.client.contact.v3.user.list(request)
        
        if not response.success():
            logger.error(f"获取用户列表失败: {response.msg}")
            raise Exception(f"获取用户列表失败: {response.msg}")
        
        users = []
        for user in response.data.items:
            users.append({
                "user_id": user.user_id,
                "name": user.name,
                "email": user.email,
                "mobile": user.mobile,
                "employee_id": user.employee_id,
                "department_ids": user.department_ids,
                "leader_user_id": user.leader_user_id,
                "city": user.city,
                "country": user.country,
                "work_station": user.work_station,
                "join_time": user.join_time,
                "employee_type": user.employee_type,
                "orders": [{"department_id": o.department_id, "user_order": o.user_order} 
                          for o in user.orders] if user.orders else []
            })
        
        return {
            "users": users,
            "page_token": response.data.page_token,
            "has_more": response.data.has_more
        }
    
    def get_user_detail(self, user_id: str, user_id_type: str = "user_id") -> Dict[str, Any]:
        """获取用户详情"""
        request = GetUserRequest.builder() \
            .user_id(user_id) \
            .user_id_type(user_id_type) \
            .department_id_type("department_id") \
            .build()
        
        response = self.client.contact.v3.user.get(request)
        
        if not response.success():
            logger.error(f"获取用户详情失败: {response.msg}")
            raise Exception(f"获取用户详情失败: {response.msg}")
        
        user = response.data.user
        return {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "mobile": user.mobile,
            "employee_id": user.employee_id,
            "department_ids": user.department_ids,
            "leader_user_id": user.leader_user_id,
            "city": user.city,
            "country": user.country,
            "work_station": user.work_station,
            "join_time": user.join_time,
            "employee_type": user.employee_type,
            "orders": [{"department_id": o.department_id, "user_order": o.user_order} 
                      for o in user.orders] if user.orders else [],
            "custom_attrs": {attr.type: attr.value for attr in user.custom_attrs} if user.custom_attrs else {}
        }
    
    # ==================== 消息相关API ====================
    
    def send_message(self, receive_id: str, msg_type: str, content: Dict[str, Any],
                    receive_id_type: str = "open_id") -> Dict[str, Any]:
        """发送消息"""
        request = CreateMessageRequest.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(CreateMessageRequestBody.builder()
                         .receive_id(receive_id)
                         .msg_type(msg_type)
                         .content(json.dumps(content))
                         .build()) \
            .build()
        
        response = self.client.im.v1.message.create(request)
        
        if not response.success():
            logger.error(f"发送消息失败: {response.msg}")
            raise Exception(f"发送消息失败: {response.msg}")
        
        return {
            "message_id": response.data.message_id,
            "root_id": response.data.root_id,
            "parent_id": response.data.parent_id,
            "msg_type": response.data.msg_type,
            "create_time": response.data.create_time,
            "update_time": response.data.update_time,
            "deleted": response.data.deleted,
            "updated": response.data.updated
        }
    
    # ==================== 日历相关API ====================
    
    def list_calendar_events(self, calendar_id: str = "primary",
                            start_time: str = None, end_time: str = None) -> List[Dict[str, Any]]:
        """获取日历事件列表"""
        if not start_time:
            start_time = datetime.utcnow().isoformat() + 'Z'
        if not end_time:
            end_time = (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z'
        
        request = ListCalendarEventRequest.builder() \
            .calendar_id(calendar_id) \
            .start_time(start_time) \
            .end_time(end_time) \
            .build()
        
        response = self.client.calendar.v4.calendar_event.list(request)
        
        if not response.success():
            logger.error(f"获取日历事件失败: {response.msg}")
            raise Exception(f"获取日历事件失败: {response.msg}")
        
        events = []
        for event in response.data.items:
            events.append({
                "event_id": event.event_id,
                "summary": event.summary,
                "description": event.description,
                "start_time": event.start_time.to_dict() if event.start_time else None,
                "end_time": event.end_time.to_dict() if event.end_time else None,
                "visibility": event.visibility,
                "attendee_ability": event.attendee_ability,
                "free_busy_status": event.free_busy_status,
                "location": event.location.to_dict() if event.location else None,
                "color": event.color,
                "reminders": [r.to_dict() for r in event.reminders] if event.reminders else [],
                "recurrence": event.recurrence,
                "status": event.status,
                "is_exception": event.is_exception,
                "app_link": event.app_link,
                "organizer_calendar_id": event.organizer_calendar_id
            })
        
        return events
    
    # ==================== 通用工具方法 ====================
    
    def check_health(self) -> bool:
        """检查飞书API连接状态"""
        try:
            request = GetApplicationRequest.builder().build()
            response = self.client.application.v6.application.get(request)
            return response.success()
        except Exception as e:
            logger.error(f"飞书API健康检查失败: {e}")
            return False
    
    def get_app_permissions(self) -> Dict[str, Any]:
        """获取应用权限列表"""
        request = ListApplicationAppVersionRequest.builder().build()
        response = self.client.application.v6.application_app_version.list(request)
        
        if not response.success():
            logger.error(f"获取应用权限失败: {response.msg}")
            raise Exception(f"获取应用权限失败: {response.msg}")
        
        permissions = {}
        if response.data.items:
            latest_version = response.data.items[0]
            if latest_version.ability:
                permissions = {
                    "gadget": latest_version.ability.gadget.to_dict() if latest_version.ability.gadget else {},
                    "web_app": latest_version.ability.web_app.to_dict() if latest_version.ability.web_app else {},
                    "bot": latest_version.ability.bot.to_dict() if latest_version.ability.bot else {},
                    "workplace_widgets": latest_version.ability.workplace_widgets.to_dict() if latest_version.ability.workplace_widgets else {}
                }
        
        return permissions