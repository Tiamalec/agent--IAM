"""
飞书权限映射服务
将飞书权限映射到IAM系统权限
"""
import json
import logging
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum

from .models import ActionType, ResourceType, Policy
from .feishu_client import FeishuClient

logger = logging.getLogger(__name__)


# 重用现有的飞书权限枚举（从feishu_integration.py中复制）
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


@dataclass
class PermissionMapping:
    """权限映射规则"""
    feishu_skill: FeishuSkill
    iam_actions: Set[ActionType]
    iam_resources: Set[ResourceType]
    conditions: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    priority: int = 0  # 优先级，数值越大优先级越高
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "feishu_skill": self.feishu_skill.value,
            "iam_actions": [action.value for action in self.iam_actions],
            "iam_resources": [resource.value for resource in self.iam_resources],
            "conditions": self.conditions,
            "description": self.description,
            "priority": self.priority
        }


@dataclass
class RoleMapping:
    """角色映射规则"""
    feishu_role: str  # 飞书角色标识
    iam_role: str  # IAM角色
    permission_mappings: List[str] = field(default_factory=list)  # 引用的权限映射ID
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "feishu_role": self.feishu_role,
            "iam_role": self.iam_role,
            "permission_mappings": self.permission_mappings,
            "description": self.description
        }


class FeishuPermissionMapper:
    """飞书权限映射器"""
    
    def __init__(self, feishu_client: Optional[FeishuClient] = None):
        self.feishu_client = feishu_client or FeishuClient()
        self.permission_mappings: Dict[str, PermissionMapping] = {}
        self.role_mappings: Dict[str, RoleMapping] = {}
        
        # 初始化默认映射
        self._init_default_mappings()
    
    def _init_default_mappings(self) -> None:
        """初始化默认权限映射"""
        # 日历技能映射
        self.add_permission_mapping(
            mapping_id="calendar_basic",
            mapping=PermissionMapping(
                feishu_skill=FeishuSkill.CALENDAR,
                iam_actions={ActionType.READ, ActionType.WRITE, ActionType.EXECUTE},
                iam_resources={ResourceType.USER_DATA},
                description="日历基本权限：查看和创建日程",
                priority=10
            )
        )
        
        # 消息技能映射
        self.add_permission_mapping(
            mapping_id="im_basic",
            mapping=PermissionMapping(
                feishu_skill=FeishuSkill.IM,
                iam_actions={ActionType.READ, ActionType.WRITE, ActionType.EXECUTE},
                iam_resources={ResourceType.USER_DATA},
                description="消息基本权限：发送和接收消息",
                priority=10
            )
        )
        
        # 文档技能映射
        self.add_permission_mapping(
            mapping_id="doc_basic",
            mapping=PermissionMapping(
                feishu_skill=FeishuSkill.DOC,
                iam_actions={ActionType.READ, ActionType.WRITE, ActionType.EXECUTE},
                iam_resources={ResourceType.USER_DATA},
                description="文档基本权限：创建和编辑文档",
                priority=10
            )
        )
        
        # IAM管理技能映射
        self.add_permission_mapping(
            mapping_id="iam_manager",
            mapping=PermissionMapping(
                feishu_skill=FeishuSkill.IAM_MANAGER,
                iam_actions={ActionType.READ, ActionType.WRITE, ActionType.DELETE, ActionType.DELEGATE},
                iam_resources={ResourceType.SYSTEM_CONFIG, ResourceType.AGENT_REGISTRY},
                description="IAM管理权限：管理系统配置和Agent注册",
                priority=100
            )
        )
        
        # 初始化默认角色映射
        self.add_role_mapping(
            role_id="admin_role",
            mapping=RoleMapping(
                feishu_role="admin",
                iam_role="administrator",
                permission_mappings=["calendar_basic", "im_basic", "doc_basic", "iam_manager"],
                description="管理员角色映射"
            )
        )
        
        self.add_role_mapping(
            role_id="user_role",
            mapping=RoleMapping(
                feishu_role="user",
                iam_role="regular_user",
                permission_mappings=["calendar_basic", "im_basic", "doc_basic"],
                description="普通用户角色映射"
            )
        )
    
    def add_permission_mapping(self, mapping_id: str, mapping: PermissionMapping) -> None:
        """添加权限映射"""
        self.permission_mappings[mapping_id] = mapping
        logger.info(f"添加权限映射: {mapping_id} - {mapping.feishu_skill.value}")
    
    def remove_permission_mapping(self, mapping_id: str) -> bool:
        """移除权限映射"""
        if mapping_id in self.permission_mappings:
            del self.permission_mappings[mapping_id]
            logger.info(f"移除权限映射: {mapping_id}")
            return True
        return False
    
    def add_role_mapping(self, role_id: str, mapping: RoleMapping) -> None:
        """添加角色映射"""
        self.role_mappings[role_id] = mapping
        logger.info(f"添加角色映射: {role_id} - {mapping.feishu_role} -> {mapping.iam_role}")
    
    def remove_role_mapping(self, role_id: str) -> bool:
        """移除角色映射"""
        if role_id in self.role_mappings:
            del self.role_mappings[role_id]
            logger.info(f"移除角色映射: {role_id}")
            return True
        return False
    
    def map_feishu_skills_to_policy(self, feishu_skills: List[FeishuSkill], 
                                   role_mapping_id: Optional[str] = None) -> Policy:
        """将飞书Skills映射为IAM策略"""
        # 收集所有权限映射
        all_actions: Set[ActionType] = set()
        all_resources: Set[ResourceType] = set()
        conditions: Dict[str, Any] = {}
        
        # 根据角色映射获取权限映射ID
        permission_mapping_ids = []
        
        if role_mapping_id and role_mapping_id in self.role_mappings:
            role_mapping = self.role_mappings[role_mapping_id]
            permission_mapping_ids.extend(role_mapping.permission_mappings)
        else:
            # 如果没有指定角色映射，使用默认映射
            for skill in feishu_skills:
                for mapping_id, mapping in self.permission_mappings.items():
                    if mapping.feishu_skill == skill:
                        permission_mapping_ids.append(mapping_id)
        
        # 按优先级排序
        sorted_mappings = sorted(
            [(mid, self.permission_mappings[mid]) for mid in permission_mapping_ids 
             if mid in self.permission_mappings],
            key=lambda x: x[1].priority,
            reverse=True
        )
        
        # 合并权限
        for mapping_id, mapping in sorted_mappings:
            all_actions.update(mapping.iam_actions)
            all_resources.update(mapping.iam_resources)
            
            # 合并条件（简单合并，实际项目中可能需要更复杂的逻辑）
            if mapping.conditions:
                conditions.update(mapping.conditions)
        
        # 创建策略
        policy = Policy(
            name=f"feishu_skills_policy_{'_'.join([s.value for s in feishu_skills])}",
            description=f"由飞书Skills映射生成的策略: {', '.join([s.value for s in feishu_skills])}",
            role=role_mapping_id or "feishu_user",
            actions=all_actions,
            resources=all_resources,
            conditions=conditions
        )
        
        return policy
    
    def get_feishu_skills_from_iam_scopes(self, iam_scopes: Set[str]) -> List[FeishuSkill]:
        """从IAM权限范围推断飞书Skills"""
        feishu_skills = []
        
        # 简单的反向映射逻辑
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
    
    def load_mappings_from_config(self, config_file: str) -> bool:
        """从配置文件加载映射规则"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 加载权限映射
            if "permission_mappings" in config:
                for mapping_id, mapping_data in config["permission_mappings"].items():
                    mapping = PermissionMapping(
                        feishu_skill=FeishuSkill(mapping_data["feishu_skill"]),
                        iam_actions={ActionType(action) for action in mapping_data["iam_actions"]},
                        iam_resources={ResourceType(resource) for resource in mapping_data["iam_resources"]},
                        conditions=mapping_data.get("conditions", {}),
                        description=mapping_data.get("description", ""),
                        priority=mapping_data.get("priority", 0)
                    )
                    self.add_permission_mapping(mapping_id, mapping)
            
            # 加载角色映射
            if "role_mappings" in config:
                for role_id, role_data in config["role_mappings"].items():
                    mapping = RoleMapping(
                        feishu_role=role_data["feishu_role"],
                        iam_role=role_data["iam_role"],
                        permission_mappings=role_data.get("permission_mappings", []),
                        description=role_data.get("description", "")
                    )
                    self.add_role_mapping(role_id, mapping)
            
            logger.info(f"从配置文件加载映射规则成功: {config_file}")
            return True
            
        except Exception as e:
            logger.error(f"加载配置文件失败 {config_file}: {e}")
            return False
    
    def save_mappings_to_config(self, config_file: str) -> bool:
        """保存映射规则到配置文件"""
        try:
            config = {
                "permission_mappings": {
                    mid: mapping.to_dict() 
                    for mid, mapping in self.permission_mappings.items()
                },
                "role_mappings": {
                    rid: mapping.to_dict()
                    for rid, mapping in self.role_mappings.items()
                }
            }
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"保存映射规则到配置文件成功: {config_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置文件失败 {config_file}: {e}")
            return False
    
    def list_available_skills(self) -> List[Dict[str, Any]]:
        """列出所有可用的飞书Skills"""
        skills = []
        for skill in FeishuSkill:
            skill_info = {
                "skill": skill.value,
                "description": self._get_skill_description(skill),
                "permission_mappings": []
            }
            
            # 查找相关的权限映射
            for mapping_id, mapping in self.permission_mappings.items():
                if mapping.feishu_skill == skill:
                    skill_info["permission_mappings"].append({
                        "mapping_id": mapping_id,
                        "description": mapping.description,
                        "priority": mapping.priority
                    })
            
            skills.append(skill_info)
        
        return skills
    
    def _get_skill_description(self, skill: FeishuSkill) -> str:
        """获取Skill描述"""
        descriptions = {
            FeishuSkill.CALENDAR: "日历管理：查看日程、创建日程、邀请参会人、查询忙闲状态",
            FeishuSkill.IM: "即时通讯：发送/回复消息、群聊管理、消息搜索、文件上传下载",
            FeishuSkill.DOC: "文档管理：创建、读取、更新、搜索文档（基于Markdown）",
            FeishuSkill.BASE: "多维表格：表格、字段、记录、视图、仪表盘、数据聚合分析",
            FeishuSkill.TASK: "任务管理：任务、任务清单、子任务、提醒、成员分配",
            FeishuSkill.MAIL: "邮件管理：浏览、搜索、阅读、发送、回复、转发邮件",
            FeishuSkill.VC: "视频会议：搜索会议记录、查询纪要产物",
            FeishuSkill.APPROVAL: "审批流程：提交、审批、拒绝、撤回审批申请",
            FeishuSkill.IAM_MANAGER: "IAM系统管理：管理飞书AI Agent的权限和访问控制",
        }
        
        return descriptions.get(skill, skill.value)