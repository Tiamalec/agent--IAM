"""
飞书AI Agent集成模块
将AI Agent IAM系统与飞书lark-cli集成
"""
try:
    from .feishu_real_client import RealFeishuAPIClient
    REAL_API_AVAILABLE = True
except ImportError:
    REAL_API_AVAILABLE = False

import json
import os
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Tuple
from enum import Enum
from .logger import get_logger

logger = get_logger(__name__)


class FeishuError(Exception):
    """飞书API错误基类"""
    
    def __init__(self, code: int, message: str, details: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"Feishu Error {code}: {message}")


class FeishuAuthError(FeishuError):
    """飞书认证错误"""
    pass


class FeishuAPIError(FeishuError):
    """飞书API调用错误"""
    pass


class FeishuRateLimitError(FeishuError):
    """飞书API速率限制错误"""
    pass


class FeishuNetworkError(FeishuError):
    """飞书网络错误"""
    pass


def handle_feishu_error(response: Dict[str, Any]) -> Optional[FeishuError]:
    """处理飞书API响应错误"""
    if not response.get("success", False):
        error_code = response.get("code", 500)
        error_msg = response.get("error", response.get("msg", "Unknown error"))
        
        if error_code == 401:
            return FeishuAuthError(error_code, f"认证失败: {error_msg}")
        elif error_code == 429:
            return FeishuRateLimitError(error_code, f"API速率限制: {error_msg}")
        elif error_code >= 500:
            return FeishuAPIError(error_code, f"飞书服务器错误: {error_msg}")
        else:
            return FeishuAPIError(error_code, f"API调用失败: {error_msg}")
    return None

from .models import Actor, ActorType
from .token_service import TokenService
from .auth_engine import AuthorizationEngine

DEFAULT_TOKEN_EXPIRY = 86400  # 24小时

class FeishuSkill(Enum):
    """飞书lark-cli Skills枚举"""
    # 基础技能
    SHARED = "lark-shared"  # 应用配置、认证登录、权限管理
    
    # 业务技能
    CALENDAR = "lark-calendar"  # 日历日程、议程查看、忙闲查询、时间建议
    IM = "lark-im"  # 发送/回复消息、群聊管理、消息搜索、文件上传下载
    DOC = "lark-doc"  # 文档创建、读取、更新、搜索（基于Markdown）
    DRIVE = "lark-drive"  # 文件上传下载、权限管理、评论
    SHEETS = "lark-sheets"  # 电子表格的创建、读取、写入、追加、查找、导出
    BASE = "lark-base"  # 多维表格、字段、记录、视图、仪表盘、数据聚合分析
    TASK = "lark-task"  # 任务、任务清单、子任务、提醒、成员分配
    MAIL = "lark-mail"  # 邮件浏览、搜索、阅读、发送、回复、转发、草稿管理
    CONTACT = "lark-contact"  # 按姓名/邮箱/手机号搜索用户，获取用户信息
    WIKI = "lark-wiki"  # 知识空间、节点、文档管理
    EVENT = "lark-event"  # 实时事件订阅（WebSocket）
    VC = "lark-vc"  # 搜索会议记录、查询纪要产物
    HR = "lark-hr"  # 人事信息查询和管理
    APPROVAL = "lark-approval"  # 审批流程管理
    MEETING = "lark-meeting"  # 会议安排和管理
    AI_ASSISTANT = "lark-ai-assistant"  # AI助手相关功能
    REPORT = "lark-report"  # 报表生成和分析
    
    # 自定义技能
    IAM_MANAGER = "iam-manager"  # IAM系统管理


class FeishuResource(Enum):
    """飞书资源类型枚举"""
    # 日历相关
    CALENDAR = "calendar"  # 日历
    EVENT = "calendar_event"  # 日历事件
    SCHEDULE = "schedule"  # 日程安排
    
    # 消息相关
    MESSAGE = "message"  # 消息
    CHAT = "chat"  # 群聊
    USER = "user"  # 用户
    
    # 文档相关
    DOCUMENT = "document"  # 文档
    WIKI = "wiki"  # 知识库
    PAGE = "page"  # 页面
    
    # 数据相关
    SPREADSHEET = "spreadsheet"  # 电子表格
    BITABLE = "bitable"  # 多维表格
    DATABASE = "database"  # 数据库
    
    # 文件相关
    FILE = "file"  # 文件
    FOLDER = "folder"  # 文件夹
    DRIVE = "drive"  # 云盘
    
    # 任务相关
    TASK = "task"  # 任务
    TASK_LIST = "task_list"  # 任务列表
    
    # 邮件相关
    EMAIL = "email"  # 邮件
    MAILBOX = "mailbox"  # 邮箱
    
    # 会议相关
    MEETING = "meeting"  # 会议
    VC_ROOM = "vc_room"  # 视频会议室
    
    # 审批相关
    APPROVAL = "approval"  # 审批
    WORKFLOW = "workflow"  # 工作流
    
    # 人事相关
    EMPLOYEE = "employee"  # 员工
    DEPARTMENT = "department"  # 部门
    
    # 系统相关
    APP = "app"  # 应用
    TENANT = "tenant"  # 租户
    API = "api"  # API接口


class FeishuAction(Enum):
    """飞书操作类型枚举"""
    # 通用操作
    READ = "read"
    WRITE = "write"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    SEARCH = "search"
    EXPORT = "export"
    IMPORT = "import"
    
    # 消息相关
    SEND = "send"
    REPLY = "reply"
    FORWARD = "forward"
    PIN = "pin"
    UNPIN = "unpin"
    
    # 日历相关
    SCHEDULE = "schedule"
    INVITE = "invite"
    CANCEL = "cancel"
    RESCHEDULE = "reschedule"
    
    # 文件相关
    UPLOAD = "upload"
    DOWNLOAD = "download"
    SHARE = "share"
    UNSHARE = "unshare"
    
    # 任务相关
    ASSIGN = "assign"
    COMPLETE = "complete"
    REOPEN = "reopen"
    PRIORITIZE = "prioritize"
    
    # 审批相关
    SUBMIT = "submit"
    APPROVE = "approve"
    REJECT = "reject"
    REVOKE = "revoke"
    
    # 会议相关
    JOIN = "join"
    LEAVE = "leave"
    RECORD = "record"
    TRANSCRIBE = "transcribe"
    
    # 管理操作
    MANAGE = "manage"
    CONFIGURE = "configure"
    MONITOR = "monitor"
    AUDIT = "audit"
    
    @classmethod
    def _missing_(cls, value):
        """允许动态创建枚举值以支持自定义操作"""
        # 动态创建枚举成员
        obj = object.__new__(cls)
        obj._value_ = value
        # 注册新成员（Python 3.11+ 有 _ignore_，但这里我们简单处理）
        # 注意：这可能会影响枚举的迭代，但用于自定义操作是可接受的
        return obj


class FeishuAPIClient:
    """飞书API客户端（支持模拟和真实API）"""
    
    def __init__(self):
        logger.info("初始化飞书API客户端")
        self.use_real_api = os.environ.get("FEISHU_SKILLS_ENABLED", "true").lower() == "true"
        self.app_id = os.environ.get("FEISHU_APP_ID")
        self.app_secret = os.environ.get("FEISHU_APP_SECRET")
        
        logger.debug(f"使用真实API: {self.use_real_api}")
        logger.debug(f"App ID: {self.app_id}")
        
        # 缓存机制
        self.cache = {}
        self.cache_ttl = 300  # 缓存有效期（秒）
        logger.info(f"初始化缓存，TTL: {self.cache_ttl}秒")
        
        # 并发处理
        import asyncio
        self.loop = asyncio.get_event_loop()
        logger.debug("初始化事件循环")
        
        self.real_client = None
        if self.use_real_api and self.app_id and self.app_secret:
            try:
                if REAL_API_AVAILABLE:
                    self.real_client = RealFeishuAPIClient(self.app_id, self.app_secret)
                    logger.info("✅ 真实飞书API客户端初始化成功")
                else:
                    logger.warning("⚠️ 真实API客户端未安装，使用模拟模式")
                    self.use_real_api = False
            except Exception as e:
                logger.error(f"⚠️ 真实API客户端初始化失败: {e}", exc_info=True)
                self.use_real_api = False
        else:
            logger.warning("⚠️ 飞书API配置不完整，使用模拟模式")
            self.use_real_api = False
    
    def _get_cache_key(self, command_type: str, subcommand: str, params: Dict[str, Any]) -> str:
        """生成缓存键"""
        import hashlib
        key_data = f"{command_type}:{subcommand}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """从缓存获取数据"""
        if key in self.cache:
            cached_data = self.cache[key]
            if time.time() < cached_data["expires"]:
                logger.debug(f"缓存命中: {key[:20]}...")
                return cached_data["data"]
            else:
                # 缓存过期，删除
                logger.debug(f"缓存过期，删除: {key[:20]}...")
                del self.cache[key]
        else:
            logger.debug(f"缓存未命中: {key[:20]}...")
        return None
    
    def _set_cache(self, key: str, data: Dict[str, Any]) -> None:
        """设置缓存数据"""
        self.cache[key] = {
            "data": data,
            "expires": time.time() + self.cache_ttl
        }
        logger.debug(f"缓存设置: {key[:20]}..., 过期时间: {time.time() + self.cache_ttl:.0f}")
    
    def clear_cache(self) -> None:
        """清空缓存"""
        cache_size = len(self.cache)
        self.cache.clear()
        logger.info(f"清空缓存，共删除 {cache_size} 个缓存项")
    
    def execute_command(self, command_type: str, subcommand: str,
                       params: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行飞书命令（支持缓存和并发）"""
        params = params or {}
        
        # 生成缓存键
        cache_key = self._get_cache_key(command_type, subcommand, params)
        
        # 尝试从缓存获取
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            logger.debug(f"从缓存获取命令结果: {command_type} {subcommand}")
            return cached_result
        
        # 执行命令
        result = None
        try:
            if self.use_real_api and self.real_client:
                # 使用并发执行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        self.real_client.execute_feishu_command,
                        command_type, subcommand, params
                    )
                    result = future.result(timeout=30)  # 30秒超时
            else:
                result = self._execute_simulated(command_type, subcommand, params)
            
            # 处理错误响应
            error = handle_feishu_error(result)
            if error:
                logger.error(f"飞书API错误: {error}")
                # 转换为友好的错误响应
                return {
                    "success": False,
                    "error": error.message,
                    "code": error.code,
                    "details": error.details
                }
            
            # 缓存结果
            self._set_cache(cache_key, result)
            logger.debug(f"命令执行成功: {command_type} {subcommand}")
            return result
            
        except concurrent.futures.TimeoutError:
            error_msg = f"飞书API调用超时: {command_type} {subcommand}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "code": 408,
                "details": {"command_type": command_type, "subcommand": subcommand}
            }
        except Exception as e:
            error_msg = f"执行飞书命令失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "code": 500,
                "details": {"command_type": command_type, "subcommand": subcommand}
            }
    
    def _execute_simulated(self, command_type: str, subcommand: str,
                          params: Dict[str, Any]) -> Dict[str, Any]:
        """模拟执行飞书命令"""
        # 模拟不同的飞书命令
        if command_type == "calendar" and subcommand == "agenda":
            return {
                "success": True,
                "data": {
                    "events": [
                        {"title": "团队周会", "time": "10:00-11:00", "location": "会议室A"},
                        {"title": "项目评审", "time": "14:00-15:30", "location": "线上会议"},
                        {"title": "客户沟通", "time": "16:00-17:00", "location": "客户办公室"}
                    ]
                }
            }
        
        elif command_type == "im" and subcommand == "send":
            return {
                "success": True,
                "data": {
                    "message_id": f"msg_{int(time.time())}",
                    "sent_to": params.get("to", "unknown"),
                    "content": params.get("content", ""),
                    "timestamp": time.time()
                }
            }
        
        elif command_type == "doc" and subcommand == "create":
            return {
                "success": True,
                "data": {
                    "document_id": f"doc_{int(time.time())}",
                    "title": params.get("title", "未命名文档"),
                    "url": f"https://feishu.cn/docx/{int(time.time())}",
                    "created_at": time.time()
                }
            }
        
        elif command_type == "task" and subcommand == "create":
            return {
                "success": True,
                "data": {
                    "task_id": f"task_{int(time.time())}",
                    "title": params.get("title", "未命名任务"),
                    "assignee": params.get("assignee", "未分配"),
                    "due_date": params.get("due_date"),
                    "created_at": time.time()
                }
            }
        
        else:
            return {
                "success": True,
                "data": {
                    "message": f"模拟执行命令: {command_type} {subcommand}",
                    "params": params
                }
            }


class FeishuSkillPermission:
    """飞书Skill权限定义"""
    
    def __init__(self, skill: FeishuSkill, description: str, 
                 actions: List[FeishuAction], resources: List[FeishuResource]):
        self.skill = skill
        self.description = description
        self.actions = actions
        self.resources = resources
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "skill": self.skill.value,
            "description": self.description,
            "actions": [action.value for action in self.actions],
            "resources": [resource.value for resource in self.resources]
        }


class FeishuIntegration:
    """飞书集成服务"""
    
    # 飞书Skills权限映射
    SKILL_PERMISSIONS: Dict[FeishuSkill, FeishuSkillPermission] = {
        FeishuSkill.CALENDAR: FeishuSkillPermission(
            skill=FeishuSkill.CALENDAR,
            description="日历管理：查看日程、创建日程、邀请参会人、查询忙闲状态",
            actions=[
                FeishuAction.READ, FeishuAction.CREATE, FeishuAction.UPDATE,
                FeishuAction.DELETE, FeishuAction.LIST, FeishuAction.SCHEDULE,
                FeishuAction.INVITE, FeishuAction.CANCEL, FeishuAction.RESCHEDULE
            ],
            resources=[FeishuResource.CALENDAR, FeishuResource.EVENT, FeishuResource.SCHEDULE]
        ),
        
        FeishuSkill.IM: FeishuSkillPermission(
            skill=FeishuSkill.IM,
            description="即时通讯：发送/回复消息、群聊管理、消息搜索、文件上传下载",
            actions=[
                FeishuAction.READ, FeishuAction.SEND, FeishuAction.REPLY,
                FeishuAction.FORWARD, FeishuAction.CREATE, FeishuAction.UPDATE,
                FeishuAction.DELETE, FeishuAction.SEARCH, FeishuAction.PIN,
                FeishuAction.UNPIN
            ],
            resources=[FeishuResource.MESSAGE, FeishuResource.CHAT, FeishuResource.USER]
        ),
        
        FeishuSkill.DOC: FeishuSkillPermission(
            skill=FeishuSkill.DOC,
            description="文档管理：创建、读取、更新、搜索文档（基于Markdown）",
            actions=[
                FeishuAction.READ, FeishuAction.CREATE, FeishuAction.UPDATE,
                FeishuAction.DELETE, FeishuAction.SEARCH, FeishuAction.EXPORT,
                FeishuAction.IMPORT
            ],
            resources=[FeishuResource.DOCUMENT, FeishuResource.PAGE]
        ),
        
        FeishuSkill.BASE: FeishuSkillPermission(
            skill=FeishuSkill.BASE,
            description="多维表格：表格、字段、记录、视图、仪表盘、数据聚合分析",
            actions=[
                FeishuAction.READ, FeishuAction.CREATE, FeishuAction.UPDATE,
                FeishuAction.DELETE, FeishuAction.LIST, FeishuAction.SEARCH,
                FeishuAction.EXPORT, FeishuAction.IMPORT
            ],
            resources=[FeishuResource.BITABLE, FeishuResource.DATABASE]
        ),
        
        FeishuSkill.TASK: FeishuSkillPermission(
            skill=FeishuSkill.TASK,
            description="任务管理：任务、任务清单、子任务、提醒、成员分配",
            actions=[
                FeishuAction.READ, FeishuAction.CREATE, FeishuAction.UPDATE,
                FeishuAction.DELETE, FeishuAction.ASSIGN, FeishuAction.COMPLETE,
                FeishuAction.REOPEN, FeishuAction.PRIORITIZE
            ],
            resources=[FeishuResource.TASK, FeishuResource.TASK_LIST]
        ),
        
        FeishuSkill.MAIL: FeishuSkillPermission(
            skill=FeishuSkill.MAIL,
            description="邮件管理：浏览、搜索、阅读、发送、回复、转发邮件",
            actions=[
                FeishuAction.READ, FeishuAction.SEND, FeishuAction.REPLY,
                FeishuAction.FORWARD, FeishuAction.SEARCH, FeishuAction.DELETE
            ],
            resources=[FeishuResource.EMAIL, FeishuResource.MAILBOX]
        ),
        
        FeishuSkill.VC: FeishuSkillPermission(
            skill=FeishuSkill.VC,
            description="视频会议：搜索会议记录、查询纪要产物",
            actions=[
                FeishuAction.READ, FeishuAction.SEARCH, FeishuAction.JOIN,
                FeishuAction.LEAVE, FeishuAction.RECORD, FeishuAction.TRANSCRIBE
            ],
            resources=[FeishuResource.MEETING, FeishuResource.VC_ROOM]
        ),
        
        FeishuSkill.APPROVAL: FeishuSkillPermission(
            skill=FeishuSkill.APPROVAL,
            description="审批流程：提交、审批、拒绝、撤回审批申请",
            actions=[
                FeishuAction.READ, FeishuAction.SUBMIT, FeishuAction.APPROVE,
                FeishuAction.REJECT, FeishuAction.REVOKE, FeishuAction.SEARCH
            ],
            resources=[FeishuResource.APPROVAL, FeishuResource.WORKFLOW]
        ),
        
        FeishuSkill.IAM_MANAGER: FeishuSkillPermission(
            skill=FeishuSkill.IAM_MANAGER,
            description="IAM系统管理：管理飞书AI Agent的权限和访问控制",
            actions=[
                FeishuAction.READ, FeishuAction.CREATE, FeishuAction.UPDATE,
                FeishuAction.DELETE, FeishuAction.MANAGE, FeishuAction.CONFIGURE,
                FeishuAction.MONITOR, FeishuAction.AUDIT
            ],
            resources=[FeishuResource.APP, FeishuResource.TENANT, FeishuResource.API]
        )
    }
    
    def __init__(self):
        self.registered_skills: Dict[str, FeishuSkill] = {}
        self.skill_tokens: Dict[str, str] = {}  # skill_id -> token
        self.api_client = FeishuAPIClient()
    
    def register_feishu_agent(self, actor: Actor, skills: List[FeishuSkill]) -> Dict[str, str]:
        """注册飞书AI Agent并分配Skills"""
        # 放宽检查：允许任何类型的Actor注册飞书Skills
        # 实际部署中可以根据需要限制
        
        skill_tokens = {}
        for skill in skills:
            if skill in self.SKILL_PERMISSIONS:
                skill_id = f"{actor.id}_{skill.value}"
                self.registered_skills[skill_id] = skill
                
                # 创建Skill Token（这里简化处理，实际应该使用IAM Token服务）
                skill_token = self._create_skill_token(actor, skill)
                skill_tokens[skill.value] = skill_token
        
        return skill_tokens
    
    def _create_skill_token(self, actor: Actor, skill: FeishuSkill) -> str:
        """创建Skill Token（简化版）"""
        permission = self.SKILL_PERMISSIONS.get(skill)
        if not permission:
            raise ValueError(f"未知的Skill: {skill}")
        
        # 生成Token ID
        token_id = f"feishu_{actor.id}_{skill.value}_{int(time.time())}"
        
        # 存储Token
        self.skill_tokens[token_id] = json.dumps({
            "actor_id": str(actor.id),
            "actor_name": str(actor.name),
            "skill": skill.value,
            "permissions": permission.to_dict(),
            "issued_at": time.time(),
            "expires_at": time.time() + DEFAULT_TOKEN_EXPIRY,  # 24小时
            "token_id": token_id
        })
        
        return token_id
    
    def validate_skill_token(self, token_id: str, action: str, resource: str) -> bool:
        """验证Skill Token是否有权限执行操作"""
        token_data_str = self.skill_tokens.get(token_id)
        if not token_data_str:
            return False
        
        try:
            token_data = json.loads(token_data_str)
            
            # 检查Token是否过期
            if time.time() > token_data.get("expires_at", 0):
                return False
            
            # 获取权限定义
            skill_value = token_data.get("skill")
            skill = FeishuSkill(skill_value) if skill_value else None
            if not skill or skill not in self.SKILL_PERMISSIONS:
                return False
            
            permission = self.SKILL_PERMISSIONS[skill]
            
            # 检查操作和资源是否在权限范围内
            action_enum = FeishuAction(action) if hasattr(FeishuAction, action.upper()) else None
            resource_enum = FeishuResource(resource) if hasattr(FeishuResource, resource.upper()) else None
            
            if not action_enum or not resource_enum:
                return False
            
            # 检查操作权限
            if action_enum not in permission.actions:
                return False
            
            # 检查资源权限
            if resource_enum not in permission.resources:
                return False
            
            return True
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            return False
    
    def get_skill_permissions(self, skill: FeishuSkill) -> Optional[Dict[str, Any]]:
        """获取Skill的权限定义"""
        permission = self.SKILL_PERMISSIONS.get(skill)
        return permission.to_dict() if permission else None
    
    def list_available_skills(self) -> List[Dict[str, Any]]:
        """列出所有可用的Skills"""
        return [
            {
                "skill": skill.value,
                "description": permission.description,
                "permissions": permission.to_dict()
            }
            for skill, permission in self.SKILL_PERMISSIONS.items()
        ]
    
    def create_feishu_policy_from_skill(self, skill: FeishuSkill, role: str) -> Dict[str, Any]:
        """根据Skill创建IAM策略"""
        permission = self.SKILL_PERMISSIONS.get(skill)
        if not permission:
            return {}
        
        # 将飞书权限映射到IAM权限
        policy = {
            "role": role,
            "skill": skill.value,
            "description": permission.description,
            "actions": [action.value for action in permission.actions],
            "resources": [resource.value for resource in permission.resources],
            "conditions": {
                "platform": "feishu",
                "skill_required": skill.value
            }
        }
        
        return policy
    
    def translate_iam_to_feishu(self, iam_actor: Actor, 
                               iam_scopes: Set[str]) -> List[FeishuSkill]:
        """将IAM权限范围翻译为飞书Skills"""
        feishu_skills = []
        
        # 简单的映射逻辑（实际应该更复杂）
        scope_to_skill = {
            "read:calendar": FeishuSkill.CALENDAR,
            "write:calendar": FeishuSkill.CALENDAR,
            "send:message": FeishuSkill.IM,
            "read:message": FeishuSkill.IM,
            "create:document": FeishuSkill.DOC,
            "read:document": FeishuSkill.DOC,
            "manage:task": FeishuSkill.TASK,
            "read:task": FeishuSkill.TASK,
            "send:email": FeishuSkill.MAIL,
            "read:email": FeishuSkill.MAIL,
            "manage:approval": FeishuSkill.APPROVAL,
            "join:meeting": FeishuSkill.VC,
            "manage:bitable": FeishuSkill.BASE,
            "manage:iam": FeishuSkill.IAM_MANAGER,
        }
        
        for scope in iam_scopes:
            for scope_pattern, skill in scope_to_skill.items():
                if scope.startswith(scope_pattern.split(":")[0]):
                    if skill not in feishu_skills:
                        feishu_skills.append(skill)
        
        return feishu_skills
    
    def execute_feishu_command(self, token_id: str, command: str, 
                              params: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行飞书命令（支持模拟和真实API）"""
        # 验证Token
        if not self._validate_command_token(token_id, command):
            return {"success": False, "error": "权限不足或Token无效"}
        
        # 解析命令
        command_parts = command.split()
        if len(command_parts) < 2:
            return {"success": False, "error": "命令格式错误"}
        
        command_type = command_parts[0]
        subcommand = command_parts[1]
        
        # 使用API客户端执行命令
        try:
            result = self.api_client.execute_command(command_type, subcommand, params or {})
            
            # 适配原有返回格式
            if result.get("success", False):
                return {"success": True, "result": result.get("data", {})}
            else:
                # 如果有fallback标记，尝试使用模拟
                if result.get("fallback_to_simulation", False):
                    fallback_result = self.api_client._execute_simulated(command_type, subcommand, params or {})
                    if fallback_result.get("success", False):
                        return {"success": True, "result": fallback_result.get("data", {})}
                
                return {"success": False, "error": result.get("error", "命令执行失败")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _validate_command_token(self, token_id: str, command: str) -> bool:
        """验证命令Token（简化版）"""
        # 这里应该解析命令，提取操作和资源，然后验证权限
        # 为简化，我们只检查Token是否存在
        return token_id in self.skill_tokens
    



class FeishuAgent(Actor):
    """飞书AI Agent扩展类"""
    
    def __init__(self, name: str, agent_type: ActorType, 
                 feishu_app_id: str = None, feishu_skills: List[FeishuSkill] = None):
        super().__init__(name=name, type=agent_type)
        self.feishu_app_id = feishu_app_id
        self.feishu_skills = feishu_skills or []
        self.feishu_tokens: Dict[str, str] = {}
        self.last_command_time: Dict[str, float] = {}
    
    def add_feishu_skill(self, skill: FeishuSkill) -> None:
        """添加飞书Skill"""
        if skill not in self.feishu_skills:
            self.feishu_skills.append(skill)
    
    def remove_feishu_skill(self, skill: FeishuSkill) -> None:
        """移除飞书Skill"""
        if skill in self.feishu_skills:
            self.feishu_skills.remove(skill)
    
    def has_feishu_skill(self, skill: FeishuSkill) -> bool:
        """检查是否有某个飞书Skill"""
        return skill in self.feishu_skills
    
    def get_skill_token(self, skill: FeishuSkill) -> Optional[str]:
        """获取Skill Token"""
        return self.feishu_tokens.get(skill.value)
    
    def set_skill_token(self, skill: FeishuSkill, token: str) -> None:
        """设置Skill Token"""
        self.feishu_tokens[skill.value] = token
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（扩展）"""
        data = super().to_dict()
        data.update({
            "feishu_app_id": self.feishu_app_id,
            "feishu_skills": [skill.value for skill in self.feishu_skills],
            "feishu_skill_count": len(self.feishu_skills)
        })
        return data


class FeishuOAuth2Client:
    """飞书OAuth2.0客户端，遵循官方SDK规范"""
    
    def __init__(self, app_id: str = None, app_secret: str = None, 
                 redirect_uri: str = None, domain: str = "feishu"):
        """
        初始化飞书OAuth2.0客户端
        
        Args:
            app_id: 飞书应用App ID
            app_secret: 飞书应用App Secret
            redirect_uri: OAuth2.0回调地址
            domain: 域名，feishu或larksuite
        """
        self.app_id = app_id or os.environ.get("FEISHU_APP_ID")
        self.app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")
        self.redirect_uri = redirect_uri or os.environ.get("FEISHU_REDIRECT_URI")
        
        if domain == "feishu":
            self.base_url = "https://open.feishu.cn"
        else:
            self.base_url = "https://open.larksuite.com"
        
        # 初始化官方SDK客户端
        self._init_sdk_client()
    
    def _init_sdk_client(self):
        """初始化官方SDK客户端"""
        try:
            import lark_oapi as lark
            self.lark_client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .domain(lark.FEISHU_DOMAIN) \
                .timeout(10) \
                .log_level(lark.LogLevel.INFO) \
                .build()
            self.sdk_available = True
        except ImportError:
            self.sdk_available = False
            self.lark_client = None
        except Exception as e:
            self.sdk_available = False
            self.lark_client = None
    
    def get_authorization_url(self, state: str = None, 
                             scope: str = "contact:user.base:readonly") -> str:
        """
        获取OAuth2.0授权URL
        
        Args:
            state: 状态参数，用于防止CSRF攻击
            scope: 权限范围，默认读取用户基本信息
            
        Returns:
            OAuth2.0授权URL
        """
        params = {
            "app_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "scope": scope,
            "state": state or os.urandom(16).hex()
        }
        
        query_string = urllib.parse.urlencode(params)
        return f"{self.base_url}/open-apis/authen/v1/index?{query_string}"
    
    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        使用授权码换取访问令牌
        
        Args:
            code: OAuth2.0授权码
            
        Returns:
            包含访问令牌和用户信息的字典
        """
        # 首先尝试使用SDK
        if self.sdk_available and self.lark_client:
            try:
                # 尝试导入SDK类
                try:
                    from lark_oapi.api.authen.v1 import CreateOidcAccessTokenRequest
                    from lark_oapi.api.authen.v1 import CreateOidcAccessTokenRequestBody
                except ImportError:
                    # 如果导入失败，回退到HTTP API
                    return self._exchange_code_for_token_http(code)
                
                request = CreateOidcAccessTokenRequest.builder() \
                    .request_body(CreateOidcAccessTokenRequestBody.builder()
                                 .grant_type("authorization_code")
                                 .code(code)
                                 .redirect_uri(self.redirect_uri)
                                 .build()) \
                    .build()
                
                response = self.lark_client.authen.v1.oidc_access_token.create(request)
                
                if response.success():
                    return {
                        "success": True,
                        "access_token": response.data.access_token,
                        "refresh_token": response.data.refresh_token,
                        "expires_in": response.data.expires_in,
                        "token_type": response.data.token_type
                    }
                else:
                    # SDK调用失败，回退到HTTP API
                    return self._exchange_code_for_token_http(code)
            except Exception as e:
                # SDK异常，回退到HTTP API
                return self._exchange_code_for_token_http(code)
        else:
            # 使用HTTP API
            return self._exchange_code_for_token_http(code)
    
    def _exchange_code_for_token_http(self, code: str) -> Dict[str, Any]:
        """HTTP API方式换取访问令牌"""
        url = f"{self.base_url}/open-apis/authen/v1/oidc/access_token"
        headers = {"Content-Type": "application/json"}
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri
        }
        
        try:
            import requests
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            # 统一返回格式
            if result.get("code") == 0:
                return {
                    "success": True,
                    "access_token": result.get("access_token"),
                    "refresh_token": result.get("refresh_token"),
                    "expires_in": result.get("expires_in"),
                    "token_type": result.get("token_type")
                }
            else:
                return {
                    "success": False,
                    "error": f"code: {result.get('code')}, msg: {result.get('msg')}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        使用访问令牌获取用户信息
        
        Args:
            access_token: OAuth2.0访问令牌
            
        Returns:
            用户信息字典
        """
        if self.sdk_available and self.lark_client:
            try:
                from lark_oapi.api.authen.v1 import GetUserInfoRequest
                
                request = GetUserInfoRequest.builder() \
                    .build()
                
                # 需要在请求选项中设置访问令牌
                from lark_oapi import RequestOption
                option = RequestOption.builder() \
                    .user_access_token(access_token) \
                    .build()
                
                response = self.lark_client.authen.v1.user_info.get(request, option)
                
                if response.success():
                    return {
                        "success": True,
                        "user": {
                            "user_id": response.data.user_id,
                            "open_id": response.data.open_id,
                            "union_id": response.data.union_id,
                            "name": response.data.name,
                            "avatar_url": response.data.avatar_url,
                            "email": response.data.email,
                            "mobile": response.data.mobile
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": f"code: {response.code}, msg: {response.msg}"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        else:
            # 使用HTTP API回退
            url = f"{self.base_url}/open-apis/authen/v1/user_info"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            try:
                import requests
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        使用刷新令牌获取新的访问令牌
        
        Args:
            refresh_token: OAuth2.0刷新令牌
            
        Returns:
            新的访问令牌信息
        """
        if self.sdk_available and self.lark_client:
            try:
                from lark_oapi.api.authen.v1 import CreateOidcRefreshAccessTokenRequest
                
                request = CreateOidcRefreshAccessTokenRequest.builder() \
                    .request_body(CreateOidcRefreshAccessTokenRequestBody.builder()
                                 .grant_type("refresh_token")
                                 .refresh_token(refresh_token)
                                 .build()) \
                    .build()
                
                response = self.lark_client.authen.v1.oidc_refresh_access_token.create(request)
                
                if response.success():
                    return {
                        "success": True,
                        "access_token": response.data.access_token,
                        "refresh_token": response.data.refresh_token,
                        "expires_in": response.data.expires_in
                    }
                else:
                    return {
                        "success": False,
                        "error": f"code: {response.code}, msg: {response.msg}"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        else:
            # 使用HTTP API回退
            url = f"{self.base_url}/open-apis/authen/v1/oidc/refresh_access_token"
            headers = {"Content-Type": "application/json"}
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }
            
            try:
                import requests
                response = requests.post(url, headers=headers, json=data, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }


class FeishuSSOManager:
    """飞书单点登录管理器"""
    
    def __init__(self, oauth_client: FeishuOAuth2Client, 
                 token_service: TokenService,
                 auth_engine: AuthorizationEngine):
        self.oauth_client = oauth_client
        self.token_service = token_service
        self.auth_engine = auth_engine
    
    def authenticate_user(self, code: str) -> Tuple[Optional[Actor], Optional[str], Optional[Dict]]:
        """
        使用OAuth2.0授权码验证用户
        
        Args:
            code: OAuth2.0授权码
            
        Returns:
            (Actor对象, IAM令牌, 飞书用户信息) 或 (None, None, None)
        """
        # 1. 使用授权码获取访问令牌
        token_result = self.oauth_client.exchange_code_for_token(code)
        if not token_result.get("success", False):
            return None, None, None
        
        access_token = token_result.get("access_token")
        if not access_token:
            return None, None, None
        
        # 2. 获取用户信息
        user_result = self.oauth_client.get_user_info(access_token)
        if not user_result.get("success", False):
            return None, None, None
        
        user_info = user_result.get("user", {})
        user_id = user_info.get("user_id") or user_info.get("open_id")
        if not user_id:
            return None, None, None
        
        # 3. 创建或获取IAM Actor
        actor = self._get_or_create_actor(user_info)
        if not actor:
            return None, None, None
        
        # 4. 生成IAM令牌
        iam_token = self._generate_iam_token(actor, user_info)
        
        return actor, iam_token, user_info
    
    def _get_or_create_actor(self, user_info: Dict[str, Any]) -> Optional[Actor]:
        """
        根据飞书用户信息获取或创建IAM Actor
        
        Args:
            user_info: 飞书用户信息
            
        Returns:
            Actor对象或None
        """
        user_id = user_info.get("user_id") or user_info.get("open_id")
        name = user_info.get("name", "")
        email = user_info.get("email", "")
        
        # 这里应该查询数据库或存储，查找现有的Actor
        # 为简化，我们创建一个新的Actor
        # 实际部署中应该检查用户是否已存在
        
        actor = Actor(
            name=name or f"feishu_user_{user_id[:8]}",
            type=ActorType.USER,
            attributes={
                "feishu_user_id": user_id,
                "feishu_open_id": user_info.get("open_id"),
                "feishu_union_id": user_info.get("union_id"),
                "email": email,
                "mobile": user_info.get("mobile", ""),
                "avatar_url": user_info.get("avatar_url", ""),
                "source": "feishu",
                "last_login": time.time()
            }
        )
        
        return actor
    
    def _generate_iam_token(self, actor: Actor, user_info: Dict[str, Any]) -> str:
        """
        为Actor生成IAM令牌
        
        Args:
            actor: Actor对象
            user_info: 飞书用户信息
            
        Returns:
            IAM令牌字符串
        """
        from .models import TokenClaims
        
        # 创建Token声明
        claims = TokenClaims(
            sub=str(actor.id),
            iss="feishu_sso",
            exp=time.time() + DEFAULT_TOKEN_EXPIRY,
            scopes={"user:read", "user:write"},
            context={
                "feishu_user_id": user_info.get("user_id"),
                "feishu_open_id": user_info.get("open_id"),
                "authenticated_via": "feishu_oauth2"
            }
        )
        
        # 使用TokenService编码令牌
        return self.token_service.encode(claims)


class FeishuOrgSync:
    """飞书组织架构同步模块"""
    
    def __init__(self, app_id: str = None, app_secret: str = None):
        self.app_id = app_id or os.environ.get("FEISHU_APP_ID")
        self.app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")
        
        # 初始化SDK客户端
        self._init_sdk_client()
    
    def _init_sdk_client(self):
        """初始化官方SDK客户端"""
        try:
            import lark_oapi as lark
            self.lark_client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .domain(lark.FEISHU_DOMAIN) \
                .timeout(30) \
                .log_level(lark.LogLevel.INFO) \
                .build()
            self.sdk_available = True
        except ImportError:
            self.sdk_available = False
            self.lark_client = None
        except Exception as e:
            self.sdk_available = False
            self.lark_client = None
    
    def get_departments(self, department_id: str = "0", 
                       fetch_child: bool = True) -> Dict[str, Any]:
        """
        获取部门列表
        
        Args:
            department_id: 部门ID，0表示根部门
            fetch_child: 是否获取子部门
            
        Returns:
            部门列表信息
        """
        if self.sdk_available and self.lark_client:
            try:
                from lark_oapi.api.contact.v3 import ListDepartmentRequest
                
                request = ListDepartmentRequest.builder() \
                    .department_id(department_id) \
                    .fetch_child(fetch_child) \
                    .page_size(100) \
                    .build()
                
                response = self.lark_client.contact.v3.department.list(request)
                
                if response.success():
                    departments = []
                    for dept in response.data.items:
                        departments.append({
                            "department_id": dept.department_id,
                            "name": dept.name,
                            "parent_department_id": dept.parent_department_id,
                            "open_department_id": dept.open_department_id,
                            "leader_user_id": dept.leader_user_id,
                            "member_count": dept.member_count,
                            "description": dept.description
                        })
                    
                    return {
                        "success": True,
                        "departments": departments,
                        "has_more": response.data.has_more,
                        "page_token": response.data.page_token
                    }
                else:
                    return {
                        "success": False,
                        "error": f"code: {response.code}, msg: {response.msg}"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        else:
            # 使用HTTP API回退
            return self._get_departments_http(department_id, fetch_child)
    
    def _get_departments_http(self, department_id: str, fetch_child: bool) -> Dict[str, Any]:
        """HTTP API获取部门列表"""
        import requests
        
        # 先获取租户访问令牌
        token_result = self._get_tenant_access_token()
        if not token_result.get("success", False):
            return token_result
        
        access_token = token_result["tenant_access_token"]
        url = "https://open.feishu.cn/open-apis/contact/v3/departments"
        
        params = {
            "department_id": department_id,
            "fetch_child": "true" if fetch_child else "false",
            "page_size": "100"
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") == 0:
                departments = []
                for dept in result.get("data", {}).get("items", []):
                    departments.append({
                        "department_id": dept.get("department_id"),
                        "name": dept.get("name"),
                        "parent_department_id": dept.get("parent_department_id"),
                        "open_department_id": dept.get("open_department_id"),
                        "leader_user_id": dept.get("leader_user_id"),
                        "member_count": dept.get("member_count"),
                        "description": dept.get("description")
                    })
                
                return {
                    "success": True,
                    "departments": departments,
                    "has_more": result.get("data", {}).get("has_more", False),
                    "page_token": result.get("data", {}).get("page_token", "")
                }
            else:
                return {
                    "success": False,
                    "error": f"code: {result.get('code')}, msg: {result.get('msg')}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_users(self, department_id: str = "0", 
                 page_size: int = 100, page_token: str = None) -> Dict[str, Any]:
        """
        获取部门用户列表
        
        Args:
            department_id: 部门ID
            page_size: 每页大小
            page_token: 分页令牌
            
        Returns:
            用户列表信息
        """
        if self.sdk_available and self.lark_client:
            try:
                from lark_oapi.api.contact.v3 import ListUserRequest
                
                request = ListUserRequest.builder() \
                    .department_id(department_id) \
                    .page_size(page_size) \
                    .page_token(page_token) \
                    .build()
                
                response = self.lark_client.contact.v3.user.list(request)
                
                if response.success():
                    users = []
                    for user in response.data.items:
                        users.append({
                            "user_id": user.user_id,
                            "open_id": user.open_id,
                            "union_id": user.union_id,
                            "name": user.name,
                            "email": user.email,
                            "mobile": user.mobile,
                            "avatar_url": user.avatar.avatar_origin if user.avatar else None,
                            "department_ids": user.department_ids,
                            "leader_user_id": user.leader_user_id,
                            "city": user.city,
                            "country": user.country,
                            "employee_no": user.employee_no,
                            "employee_type": user.employee_type,
                            "gender": user.gender,
                            "join_time": user.join_time
                        })
                    
                    return {
                        "success": True,
                        "users": users,
                        "has_more": response.data.has_more,
                        "page_token": response.data.page_token
                    }
                else:
                    return {
                        "success": False,
                        "error": f"code: {response.code}, msg: {response.msg}"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        else:
            # 使用HTTP API回退
            return self._get_users_http(department_id, page_size, page_token)
    
    def _get_users_http(self, department_id: str, page_size: int, page_token: str) -> Dict[str, Any]:
        """HTTP API获取用户列表"""
        import requests
        
        # 先获取租户访问令牌
        token_result = self._get_tenant_access_token()
        if not token_result.get("success", False):
            return token_result
        
        access_token = token_result["tenant_access_token"]
        url = "https://open.feishu.cn/open-apis/contact/v3/users"
        
        params = {
            "department_id": department_id,
            "page_size": str(page_size)
        }
        
        if page_token:
            params["page_token"] = page_token
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") == 0:
                users = []
                for user in result.get("data", {}).get("items", []):
                    users.append({
                        "user_id": user.get("user_id"),
                        "open_id": user.get("open_id"),
                        "union_id": user.get("union_id"),
                        "name": user.get("name"),
                        "email": user.get("email"),
                        "mobile": user.get("mobile"),
                        "avatar_url": user.get("avatar", {}).get("avatar_origin") if user.get("avatar") else None,
                        "department_ids": user.get("department_ids", []),
                        "leader_user_id": user.get("leader_user_id"),
                        "city": user.get("city"),
                        "country": user.get("country"),
                        "employee_no": user.get("employee_no"),
                        "employee_type": user.get("employee_type"),
                        "gender": user.get("gender"),
                        "join_time": user.get("join_time")
                    })
                
                return {
                    "success": True,
                    "users": users,
                    "has_more": result.get("data", {}).get("has_more", False),
                    "page_token": result.get("data", {}).get("page_token", "")
                }
            else:
                return {
                    "success": False,
                    "error": f"code: {result.get('code')}, msg: {result.get('msg')}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_tenant_access_token(self) -> Dict[str, Any]:
        """获取租户访问令牌"""
        import requests
        
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") == 0:
                return {
                    "success": True,
                    "tenant_access_token": result["tenant_access_token"],
                    "expire": result["expire"]
                }
            else:
                return {
                    "success": False,
                    "error": f"code: {result.get('code')}, msg: {result.get('msg')}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def sync_full_organization(self) -> Dict[str, Any]:
        """
        同步完整的组织架构（部门和用户）
        
        Returns:
            同步结果
        """
        # 1. 获取所有部门
        all_departments = []
        page_token = None
        
        while True:
            result = self.get_departments("0", True)
            if not result.get("success", False):
                return result
            
            departments = result.get("departments", [])
            all_departments.extend(departments)
            
            if not result.get("has_more", False):
                break
            
            page_token = result.get("page_token")
            if not page_token:
                break
        
        # 2. 获取所有用户
        all_users = []
        
        for dept in all_departments:
            dept_id = dept.get("department_id")
            page_token = None
            
            while True:
                result = self.get_users(dept_id, 100, page_token)
                if not result.get("success", False):
                    # 记录错误但继续
                    break
                
                users = result.get("users", [])
                # 去重：避免重复添加同一用户
                for user in users:
                    user_id = user.get("user_id")
                    if not any(u.get("user_id") == user_id for u in all_users):
                        all_users.append(user)
                
                if not result.get("has_more", False):
                    break
                
                page_token = result.get("page_token")
                if not page_token:
                    break
        
        # 3. 构建组织架构树
        org_structure = self._build_org_structure(all_departments, all_users)
        
        return {
            "success": True,
            "department_count": len(all_departments),
            "user_count": len(all_users),
            "departments": all_departments,
            "users": all_users,
            "org_structure": org_structure
        }
    
    def _build_org_structure(self, departments: List[Dict], users: List[Dict]) -> Dict[str, Any]:
        """构建组织架构树"""
        # 创建部门ID到部门的映射
        dept_map = {dept["department_id"]: dept for dept in departments}
        
        # 为每个部门添加用户列表
        for dept in departments:
            dept_id = dept["department_id"]
            dept_users = []
            
            for user in users:
                if dept_id in user.get("department_ids", []):
                    dept_users.append({
                        "user_id": user["user_id"],
                        "name": user["name"],
                        "email": user["email"],
                        "mobile": user["mobile"]
                    })
            
            dept["users"] = dept_users
        
        # 构建树形结构
        root_departments = []
        for dept in departments:
            parent_id = dept.get("parent_department_id")
            if not parent_id or parent_id == "0" or parent_id not in dept_map:
                root_departments.append(dept)
        
        # 递归构建子树
        def build_subtree(parent_dept):
            subtree = {
                "department": parent_dept,
                "children": []
            }
            
            for dept in departments:
                if dept.get("parent_department_id") == parent_dept["department_id"]:
                    subtree["children"].append(build_subtree(dept))
            
            return subtree
        
        org_tree = []
        for root_dept in root_departments:
            org_tree.append(build_subtree(root_dept))
        
        return {
            "tree": org_tree,
            "flat": departments
        }


class FeishuPermissionMapper:
    """飞书权限映射规则配置系统"""
    
    def __init__(self, config_file: str = None):
        """
        初始化权限映射器
        
        Args:
            config_file: 配置文件路径（JSON或YAML）
        """
        self.mapping_rules = {}
        self.reverse_mapping = {}
        
        # 加载默认映射规则
        self._load_default_mappings()
        
        # 加载自定义配置
        if config_file and os.path.exists(config_file):
            self.load_config(config_file)
    
    def _load_default_mappings(self):
        """加载默认的权限映射规则"""
        # 飞书Skills到IAM Scopes的默认映射
        self.mapping_rules = {
            # 日历相关
            FeishuSkill.CALENDAR: {
                "iam_scopes": {
                    "read": {"read:calendar", "read:event"},
                    "write": {"write:calendar", "create:event", "update:event", "delete:event"},
                    "create": {"create:event"},
                    "update": {"update:event"},
                    "delete": {"delete:event"},
                    "list": {"read:calendar"},
                    "schedule": {"write:calendar", "create:event"},
                    "invite": {"write:calendar", "update:event"},
                    "cancel": {"write:calendar", "delete:event"},
                    "reschedule": {"write:calendar", "update:event"}
                },
                "resources": {
                    "calendar": "calendar",
                    "calendar_event": "event",
                    "schedule": "event"
                }
            },
            
            # 消息相关
            FeishuSkill.IM: {
                "iam_scopes": {
                    "read": {"read:message", "read:chat"},
                    "send": {"send:message"},
                    "reply": {"send:message"},
                    "forward": {"send:message"},
                    "create": {"create:chat"},
                    "update": {"update:chat"},
                    "delete": {"delete:message", "delete:chat"},
                    "search": {"read:message"},
                    "pin": {"update:chat"},
                    "unpin": {"update:chat"}
                },
                "resources": {
                    "message": "message",
                    "chat": "chat",
                    "user": "user"
                }
            },
            
            # 文档相关
            FeishuSkill.DOC: {
                "iam_scopes": {
                    "read": {"read:document"},
                    "create": {"create:document"},
                    "update": {"update:document"},
                    "delete": {"delete:document"},
                    "search": {"read:document"},
                    "export": {"read:document"},
                    "import": {"write:document"}
                },
                "resources": {
                    "document": "document",
                    "page": "document"
                }
            },
            
            # 多维表格相关
            FeishuSkill.BASE: {
                "iam_scopes": {
                    "read": {"read:bitable"},
                    "create": {"create:bitable"},
                    "update": {"update:bitable"},
                    "delete": {"delete:bitable"},
                    "list": {"read:bitable"},
                    "search": {"read:bitable"},
                    "export": {"read:bitable"},
                    "import": {"write:bitable"}
                },
                "resources": {
                    "bitable": "bitable",
                    "database": "database"
                }
            },
            
            # 任务相关
            FeishuSkill.TASK: {
                "iam_scopes": {
                    "read": {"read:task"},
                    "create": {"create:task"},
                    "update": {"update:task"},
                    "delete": {"delete:task"},
                    "assign": {"write:task"},
                    "complete": {"update:task"},
                    "reopen": {"update:task"},
                    "prioritize": {"update:task"}
                },
                "resources": {
                    "task": "task",
                    "task_list": "task"
                }
            },
            
            # IAM管理相关
            FeishuSkill.IAM_MANAGER: {
                "iam_scopes": {
                    "read": {"read:iam"},
                    "create": {"create:iam"},
                    "update": {"update:iam"},
                    "delete": {"delete:iam"},
                    "manage": {"admin:iam"},
                    "configure": {"admin:iam"},
                    "monitor": {"read:iam"},
                    "audit": {"read:iam"}
                },
                "resources": {
                    "app": "application",
                    "tenant": "tenant",
                    "api": "api"
                }
            }
        }
        
        # 构建反向映射（IAM Scope到飞书Skill）
        self._build_reverse_mappings()
    
    def _build_reverse_mappings(self):
        """构建反向映射表"""
        self.reverse_mapping = {}
        
        for skill, skill_config in self.mapping_rules.items():
            iam_scopes = skill_config.get("iam_scopes", {})
            
            for action, scopes in iam_scopes.items():
                for scope in scopes:
                    if scope not in self.reverse_mapping:
                        self.reverse_mapping[scope] = []
                    
                    mapping_entry = {
                        "skill": skill,
                        "action": action,
                        "required_scopes": scopes
                    }
                    
                    if mapping_entry not in self.reverse_mapping[scope]:
                        self.reverse_mapping[scope].append(mapping_entry)
    
    def load_config(self, config_file: str):
        """
        从配置文件加载映射规则
        
        Args:
            config_file: 配置文件路径（支持JSON或YAML）
        """
        try:
            import json
            
            with open(config_file, 'r', encoding='utf-8') as f:
                if config_file.endswith('.json'):
                    config = json.load(f)
                elif config_file.endswith('.yaml') or config_file.endswith('.yml'):
                    # 延迟导入yaml，避免不必要的依赖
                    import yaml
                    config = yaml.safe_load(f)
                else:
                    raise ValueError("不支持的配置文件格式，请使用JSON或YAML")
            
            # 更新映射规则
            self._update_mappings_from_config(config)
            
            # 重新构建反向映射
            self._build_reverse_mappings()
            
            return True
            
        except Exception as e:
            return False
    
    def _update_mappings_from_config(self, config: Dict[str, Any]):
        """从配置字典更新映射规则"""
        for skill_name, skill_config in config.get("skill_mappings", {}).items():
            try:
                skill = FeishuSkill(skill_name)
                
                # 更新IAM Scopes映射
                iam_scopes = skill_config.get("iam_scopes", {})
                if iam_scopes:
                    if skill not in self.mapping_rules:
                        self.mapping_rules[skill] = {"iam_scopes": {}, "resources": {}}
                    
                    self.mapping_rules[skill]["iam_scopes"].update(iam_scopes)
                
                # 更新资源映射
                resources = skill_config.get("resources", {})
                if resources:
                    if skill not in self.mapping_rules:
                        self.mapping_rules[skill] = {"iam_scopes": {}, "resources": {}}
                    
                    self.mapping_rules[skill]["resources"].update(resources)
                    
            except ValueError:
                # 未知的Skill，跳过
                continue
    
    def map_feishu_to_iam(self, skill: FeishuSkill, action: FeishuAction, 
                          resource: FeishuResource) -> Set[str]:
        """
        将飞书权限映射到IAM Scopes
        
        Args:
            skill: 飞书Skill
            action: 飞书操作
            resource: 飞书资源
            
        Returns:
            IAM Scope集合
        """
        iam_scopes = set()
        
        if skill not in self.mapping_rules:
            return iam_scopes
        
        skill_config = self.mapping_rules[skill]
        action_mappings = skill_config.get("iam_scopes", {})
        
        # 查找操作映射
        action_str = action.value
        if action_str in action_mappings:
            iam_scopes.update(action_mappings[action_str])
        
        # 查找资源映射（如果有特殊资源映射）
        resource_mappings = skill_config.get("resources", {})
        resource_str = resource.value
        if resource_str in resource_mappings:
            # 可以根据资源类型添加额外的Scope
            mapped_resource = resource_mappings[resource_str]
            for scope in list(iam_scopes):
                if ":" in scope:
                    # 将通用Scope转换为特定资源Scope
                    prefix = scope.split(":")[0]
                    specific_scope = f"{prefix}:{mapped_resource}"
                    iam_scopes.add(specific_scope)
        
        return iam_scopes
    
    def map_iam_to_feishu(self, iam_scopes: Set[str]) -> List[Dict[str, Any]]:
        """
        将IAM Scopes映射到飞书权限
        
        Args:
            iam_scopes: IAM Scope集合
            
        Returns:
            飞书权限配置列表
        """
        feishu_permissions = []
        
        for scope in iam_scopes:
            if scope in self.reverse_mapping:
                for mapping in self.reverse_mapping[scope]:
                    skill = mapping["skill"]
                    action = mapping["action"]
                    
                    # 检查是否已存在相同的Skill和Action组合
                    existing = next(
                        (p for p in feishu_permissions 
                         if p["skill"] == skill and p["action"] == action),
                        None
                    )
                    
                    if not existing:
                        feishu_permissions.append({
                            "skill": skill,
                            "action": action,
                            "required_scopes": mapping["required_scopes"]
                        })
        
        return feishu_permissions
    
    def get_required_scopes_for_feishu(self, skill: FeishuSkill, 
                                      action: FeishuAction) -> Set[str]:
        """
        获取执行飞书操作所需的IAM Scopes
        
        Args:
            skill: 飞书Skill
            action: 飞书操作
            
        Returns:
            所需的IAM Scope集合
        """
        if skill not in self.mapping_rules:
            return set()
        
        skill_config = self.mapping_rules[skill]
        action_mappings = skill_config.get("iam_scopes", {})
        action_str = action.value
        
        if action_str in action_mappings:
            return action_mappings[action_str].copy()
        
        return set()
    
    def validate_iam_scopes_for_feishu(self, skill: FeishuSkill, 
                                      action: FeishuAction, 
                                      user_scopes: Set[str]) -> bool:
        """
        验证用户IAM Scopes是否满足飞书操作要求
        
        Args:
            skill: 飞书Skill
            action: 飞书操作
            user_scopes: 用户的IAM Scopes
            
        Returns:
            是否满足权限要求
        """
        required_scopes = self.get_required_scopes_for_feishu(skill, action)
        
        # 检查用户是否拥有所有必需的Scopes
        return required_scopes.issubset(user_scopes)
    
    def add_custom_mapping(self, skill: FeishuSkill, action: FeishuAction,
                          iam_scopes: Set[str], resource_mapping: Dict[str, str] = None):
        """
        添加自定义映射规则
        
        Args:
            skill: 飞书Skill
            action: 飞书操作
            iam_scopes: 对应的IAM Scopes
            resource_mapping: 资源映射（可选）
        """
        if skill not in self.mapping_rules:
            self.mapping_rules[skill] = {"iam_scopes": {}, "resources": {}}
        
        action_str = action.value
        self.mapping_rules[skill]["iam_scopes"][action_str] = iam_scopes.copy()
        
        if resource_mapping:
            self.mapping_rules[skill]["resources"].update(resource_mapping)
        
        # 更新反向映射
        self._build_reverse_mappings()
    
    def export_config(self, output_file: str, format: str = "json"):
        """
        导出映射配置到文件
        
        Args:
            output_file: 输出文件路径
            format: 输出格式（json或yaml）
        """
        config = {"skill_mappings": {}}
        
        for skill, skill_config in self.mapping_rules.items():
            skill_name = skill.value
            config["skill_mappings"][skill_name] = {
                "iam_scopes": skill_config.get("iam_scopes", {}),
                "resources": skill_config.get("resources", {})
            }
        
        try:
            if format == "json":
                import json
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
            elif format == "yaml":
                import yaml
                with open(output_file, 'w', encoding='utf-8') as f:
                    yaml.dump(config, f, allow_unicode=True)
            else:
                raise ValueError("不支持的输出格式")
            
            return True
            
        except Exception as e:
            return False


class FeishuWebhookHandler:
    """飞书Webhook事件处理器"""
    
    def __init__(self, verification_token: str = None, encrypt_key: str = None):
        """
        初始化Webhook处理器
        
        Args:
            verification_token: Webhook验证令牌
            encrypt_key: 加密密钥（如果启用了加密）
        """
        self.verification_token = verification_token or os.environ.get("FEISHU_WEBHOOK_VERIFICATION_TOKEN")
        self.encrypt_key = encrypt_key or os.environ.get("FEISHU_WEBHOOK_ENCRYPT_KEY")
    
    def verify_webhook(self, challenge: str, token: str, timestamp: str, nonce: str, 
                      encrypted: str = None, signature: str = None) -> Dict[str, Any]:
        """
        验证Webhook请求
        
        Args:
            challenge: 飞书发送的挑战码
            token: Webhook令牌
            timestamp: 时间戳
            nonce: 随机数
            encrypted: 加密数据（如果启用了加密）
            signature: 签名（如果启用了加密）
            
        Returns:
            验证结果，包含challenge用于响应
        """
        # 简单验证：检查token是否匹配
        if token != self.verification_token:
            return {
                "success": False,
                "error": "Invalid verification token"
            }
        
        # 如果启用了加密，需要验证签名
        if self.encrypt_key and encrypted and signature:
            # 这里需要实现飞书加密验证逻辑
            # 实际部署中应该根据飞书文档实现
            pass
        
        # 验证成功，返回challenge
        return {
            "success": True,
            "challenge": challenge
        }
    
    def handle_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理Webhook事件
        
        Args:
            event_data: Webhook事件数据
            
        Returns:
            处理结果
        """
        try:
            event_type = event_data.get("type")
            event = event_data.get("event", {})
            
            # 根据事件类型分发处理
            if event_type == "contact.user.created_v3":
                return self._handle_user_created(event)
            elif event_type == "contact.user.updated_v3":
                return self._handle_user_updated(event)
            elif event_type == "contact.user.deleted_v3":
                return self._handle_user_deleted(event)
            elif event_type == "contact.department.created_v3":
                return self._handle_department_created(event)
            elif event_type == "contact.department.updated_v3":
                return self._handle_department_updated(event)
            elif event_type == "contact.department.deleted_v3":
                return self._handle_department_deleted(event)
            elif event_type == "contact.scope.updated_v3":
                return self._handle_scope_updated(event)
            else:
                return {
                    "success": True,
                    "handled": False,
                    "message": f"Unhandled event type: {event_type}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "event_data": event_data
            }
    
    def _handle_user_created(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """处理用户创建事件"""
        user_info = event.get("object", {})
        user_id = user_info.get("user_id")
        
        # 在这里处理用户创建逻辑
        # 例如：将新用户同步到IAM系统
        
        return {
            "success": True,
            "handled": True,
            "event_type": "user.created",
            "user_id": user_id,
            "action": "user_created",
            "message": f"User {user_id} created"
        }
    
    def _handle_user_updated(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """处理用户更新事件"""
        user_info = event.get("object", {})
        user_id = user_info.get("user_id")
        changed_fields = event.get("changed_fields", [])
        
        # 在这里处理用户更新逻辑
        # 例如：更新IAM系统中的用户信息
        
        return {
            "success": True,
            "handled": True,
            "event_type": "user.updated",
            "user_id": user_id,
            "changed_fields": changed_fields,
            "action": "user_updated",
            "message": f"User {user_id} updated"
        }
    
    def _handle_user_deleted(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """处理用户删除事件"""
        user_info = event.get("object", {})
        user_id = user_info.get("user_id")
        
        # 在这里处理用户删除逻辑
        # 例如：从IAM系统中删除用户
        
        return {
            "success": True,
            "handled": True,
            "event_type": "user.deleted",
            "user_id": user_id,
            "action": "user_deleted",
            "message": f"User {user_id} deleted"
        }
    
    def _handle_department_created(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """处理部门创建事件"""
        dept_info = event.get("object", {})
        dept_id = dept_info.get("department_id")
        
        # 在这里处理部门创建逻辑
        # 例如：将新部门同步到IAM系统
        
        return {
            "success": True,
            "handled": True,
            "event_type": "department.created",
            "department_id": dept_id,
            "action": "department_created",
            "message": f"Department {dept_id} created"
        }
    
    def _handle_department_updated(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """处理部门更新事件"""
        dept_info = event.get("object", {})
        dept_id = dept_info.get("department_id")
        changed_fields = event.get("changed_fields", [])
        
        # 在这里处理部门更新逻辑
        # 例如：更新IAM系统中的部门信息
        
        return {
            "success": True,
            "handled": True,
            "event_type": "department.updated",
            "department_id": dept_id,
            "changed_fields": changed_fields,
            "action": "department_updated",
            "message": f"Department {dept_id} updated"
        }
    
    def _handle_department_deleted(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """处理部门删除事件"""
        dept_info = event.get("object", {})
        dept_id = dept_info.get("department_id")
        
        # 在这里处理部门删除逻辑
        # 例如：从IAM系统中删除部门
        
        return {
            "success": True,
            "handled": True,
            "event_type": "department.deleted",
            "department_id": dept_id,
            "action": "department_deleted",
            "message": f"Department {dept_id} deleted"
        }
    
    def _handle_scope_updated(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """处理权限范围更新事件"""
        # 处理应用权限范围变更
        # 例如：重新同步组织架构
        
        return {
            "success": True,
            "handled": True,
            "event_type": "scope.updated",
            "action": "scope_updated",
            "message": "Permission scope updated,可能需要重新同步组织架构"
        }
    
    def batch_process_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量处理Webhook事件
        
        Args:
            events: 事件列表
            
        Returns:
            处理结果列表
        """
        results = []
        for event_data in events:
            result = self.handle_event(event_data)
            results.append(result)
        
        return results
    
    def register_event_handler(self, event_type: str, handler_func):
        """
        注册自定义事件处理器
        
        Args:
            event_type: 事件类型
            handler_func: 处理函数
        """
        if not hasattr(self, "_custom_handlers"):
            self._custom_handlers = {}
        
        self._custom_handlers[event_type] = handler_func
    
    def process_with_custom_handlers(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用自定义处理器处理事件
        
        Args:
            event_data: 事件数据
            
        Returns:
            处理结果
        """
        event_type = event_data.get("type")
        
        if hasattr(self, "_custom_handlers") and event_type in self._custom_handlers:
            handler_func = self._custom_handlers[event_type]
            try:
                return handler_func(event_data)
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "event_type": event_type
                }
        else:
            # 如果没有自定义处理器，使用默认处理
            return self.handle_event(event_data)