"""
核心域模型定义
"""
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Union
from uuid import uuid4


class ActorType(Enum):
    """参与者类型"""
    USER = "user"
    MASTER_AGENT = "master_agent"
    WORKER_AGENT = "worker_agent"
    IAM_CONTROLLER = "iam_controller"


class ActionType(Enum):
    """操作类型"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    DELEGATE = "delegate"


class ResourceType(Enum):
    """资源类型"""
    FINANCIAL_DATA = "financial_data"
    USER_DATA = "user_data"
    SYSTEM_CONFIG = "system_config"
    AGENT_REGISTRY = "agent_registry"


@dataclass
class Actor:
    """参与者（用户或Agent）"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    type: ActorType = ActorType.USER
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['type'] = self.type.value
        return data


@dataclass
class Policy:
    """授权策略"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    role: str = ""  # RBAC角色
    actions: Set[ActionType] = field(default_factory=set)
    resources: Set[ResourceType] = field(default_factory=set)
    conditions: Dict[str, Any] = field(default_factory=dict)  # ABAC条件
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['actions'] = [a.value for a in self.actions]
        data['resources'] = [r.value for r in self.resources]
        return data


@dataclass
class TokenClaims:
    """Token声明（类似JWT claims）"""
    # 标准声明
    sub: str  # 主体（actor id）
    iss: str  # 签发者（actor id）
    iat: float = field(default_factory=time.time)  # 签发时间
    exp: Optional[float] = None  # 过期时间
    nbf: Optional[float] = None  # 生效时间
    
    # 自定义声明
    scopes: Set[str] = field(default_factory=set)  # 权限范围
    parent_token: Optional[str] = None  # 父token ID
    trust_chain: List[str] = field(default_factory=list)  # 信任链（从根token到当前token）
    max_uses: Optional[int] = None  # 最大使用次数
    used_count: int = 0  # 已使用次数
    context: Dict[str, Any] = field(default_factory=dict)  # 上下文属性（ABAC）
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['scopes'] = list(self.scopes)
        return data
    
    def is_expired(self) -> bool:
        if self.exp is None:
            return False
        return time.time() > self.exp
    
    def is_valid(self) -> bool:
        if self.exp is not None and time.time() > self.exp:
            return False
        if self.nbf is not None and time.time() < self.nbf:
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        return True


@dataclass
class AuditEvent:
    """审计事件"""
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time.time)
    actor_id: str = ""
    action: str = ""
    resource: str = ""
    result: str = ""  # allow, deny, delegate, issue, etc.
    details: Dict[str, Any] = field(default_factory=dict)
    previous_hash: Optional[str] = None  # 前一个事件的哈希（用于hash-chain）
    current_hash: Optional[str] = None  # 当前事件的哈希
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)