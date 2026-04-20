"""
测试核心域模型
"""
import time
import pytest

from agent_iam.models import (
    Actor, ActorType, ActionType, ResourceType, Policy, 
    TokenClaims, AuditEvent
)


class TestActor:
    """测试Actor模型"""
    
    def test_actor_creation(self):
        """测试Actor创建"""
        actor = Actor(name="测试用户", type=ActorType.USER)
        
        assert actor.name == "测试用户"
        assert actor.type == ActorType.USER
        assert actor.id is not None
        assert actor.created_at > 0
    
    def test_actor_to_dict(self):
        """测试Actor转换为字典"""
        actor = Actor(name="测试用户", type=ActorType.USER)
        actor_dict = actor.to_dict()
        
        assert isinstance(actor_dict, dict)
        assert actor_dict['name'] == "测试用户"
        assert actor_dict['type'] == ActorType.USER.value


class TestPolicy:
    """测试Policy模型"""
    
    def test_policy_creation(self):
        """测试Policy创建"""
        policy = Policy(
            name="测试策略",
            role="admin",
            actions={ActionType.READ, ActionType.WRITE},
            resources={ResourceType.FINANCIAL_DATA}
        )
        
        assert policy.name == "测试策略"
        assert policy.role == "admin"
        assert ActionType.READ in policy.actions
        assert ResourceType.FINANCIAL_DATA in policy.resources
    
    def test_policy_to_dict(self):
        """测试Policy转换为字典"""
        policy = Policy(
            name="测试策略",
            role="admin",
            actions={ActionType.READ},
            resources={ResourceType.FINANCIAL_DATA}
        )
        
        policy_dict = policy.to_dict()
        
        assert isinstance(policy_dict, dict)
        assert policy_dict['name'] == "测试策略"
        assert policy_dict['role'] == "admin"
        assert 'read' in policy_dict['actions']


class TestTokenClaims:
    """测试TokenClaims模型"""
    
    def test_token_claims_creation(self):
        """测试TokenClaims创建"""
        claims = TokenClaims(
            sub="user123",
            iss="iam_controller",
            scopes={"read:data", "write:data"}
        )
        
        assert claims.sub == "user123"
        assert claims.iss == "iam_controller"
        assert "read:data" in claims.scopes
        assert claims.used_count == 0
    
    def test_token_claims_expiry(self):
        """测试TokenClaims过期检查"""
        # 未过期的Token
        claims = TokenClaims(
            sub="user123",
            iss="iam_controller",
            exp=time.time() + 3600  # 1小时后过期
        )
        assert not claims.is_expired()
        
        # 已过期的Token
        claims_expired = TokenClaims(
            sub="user123",
            iss="iam_controller",
            exp=time.time() - 3600  # 1小时前过期
        )
        assert claims_expired.is_expired()
    
    def test_token_claims_validity(self):
        """测试TokenClaims有效性检查"""
        # 有效的Token
        claims = TokenClaims(
            sub="user123",
            iss="iam_controller",
            exp=time.time() + 3600,
            max_uses=10
        )
        assert claims.is_valid()
        
        # 超过最大使用次数的Token
        claims_overused = TokenClaims(
            sub="user123",
            iss="iam_controller",
            max_uses=5,
            used_count=5
        )
        assert not claims_overused.is_valid()
        
        # 未生效的Token
        claims_not_yet_valid = TokenClaims(
            sub="user123",
            iss="iam_controller",
            nbf=time.time() + 3600  # 1小时后生效
        )
        assert not claims_not_yet_valid.is_valid()


class TestAuditEvent:
    """测试AuditEvent模型"""
    
    def test_audit_event_creation(self):
        """测试AuditEvent创建"""
        event = AuditEvent(
            actor_id="user123",
            action="read",
            resource="data",
            result="allow"
        )
        
        assert event.actor_id == "user123"
        assert event.action == "read"
        assert event.resource == "data"
        assert event.result == "allow"
        assert event.id is not None
    
    def test_audit_event_to_dict(self):
        """测试AuditEvent转换为字典"""
        event = AuditEvent(
            actor_id="user123",
            action="read",
            resource="data",
            result="allow"
        )
        
        event_dict = event.to_dict()
        
        assert isinstance(event_dict, dict)
        assert event_dict['actor_id'] == "user123"
        assert event_dict['result'] == "allow"