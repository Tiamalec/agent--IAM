"""
测试委托逻辑
"""
import time
import pytest

from agent_iam.models import TokenClaims
from agent_iam.token_service import TokenService
from agent_iam.delegation import DelegationService


class TestDelegationService:
    """测试DelegationService"""
    
    @pytest.fixture
    def token_service(self):
        """创建TokenService实例"""
        return TokenService(secret_key="test_secret_key")
    
    @pytest.fixture
    def delegation_service(self, token_service):
        """创建DelegationService实例"""
        return DelegationService(token_service)
    
    @pytest.fixture
    def root_token(self, token_service):
        """创建根Token"""
        claims = TokenClaims(
            sub="master_agent",
            iss="user",
            scopes={"read:data", "write:data", "delegate:data"},
            exp=time.time() + 3600
        )
        return token_service.encode(claims)
    
    @pytest.fixture
    def read_only_token(self, token_service):
        """创建只读Token"""
        claims = TokenClaims(
            sub="worker_agent",
            iss="master_agent",
            scopes={"read:data"},
            exp=time.time() + 3600
        )
        return token_service.encode(claims)
    
    def test_can_delegate(self, delegation_service, root_token):
        """测试委托权限检查"""
        # 有委托权限的情况
        requested_scopes = {"read:data"}
        parent_claims = delegation_service.can_delegate(root_token, requested_scopes)
        assert parent_claims is not None
        assert parent_claims.sub == "master_agent"
        
        # 请求超出父Token权限的范围
        requested_scopes_too_much = {"read:data", "delete:data"}
        parent_claims = delegation_service.can_delegate(root_token, requested_scopes_too_much)
        assert parent_claims is None
        
        # 无效的Token
        invalid_token = "invalid.token"
        parent_claims = delegation_service.can_delegate(invalid_token, requested_scopes)
        assert parent_claims is None
    
    def test_create_delegated_token(self, delegation_service, root_token):
        """测试创建委托Token"""
        # 创建委托Token
        delegated_token = delegation_service.create_delegated_token(
            parent_token=root_token,
            child_sub="worker_agent",
            scopes={"read:data"},
            expires_in=1800,
            max_uses=5
        )
        
        assert delegated_token is not None
        
        # 解码验证
        token_service = delegation_service.token_service
        claims = token_service.decode(delegated_token)
        
        assert claims.sub == "worker_agent"
        assert claims.iss == "master_agent"
        assert "read:data" in claims.scopes
        assert claims.parent_token == root_token
        assert claims.max_uses == 5
        assert claims.trust_chain == ["master_agent"]
        
        # 验证委托链
        assert delegation_service.validate_delegation_chain(delegated_token) is True
    
    def test_delegation_with_wildcard(self, delegation_service, token_service):
        """测试通配符委托"""
        # 父Token有通配符权限
        parent_claims = TokenClaims(
            sub="master_agent",
            iss="user",
            scopes={"read:*", "delegate:*"}  # 可以读取和委托所有资源
        )
        parent_token = token_service.encode(parent_claims)
        
        # 创建委托Token（特定资源）
        delegated_token = delegation_service.create_delegated_token(
            parent_token=parent_token,
            child_sub="worker_agent",
            scopes={"read:financial_data"}  # 子集
        )
        
        assert delegated_token is not None
        
        # 解码验证
        claims = token_service.decode(delegated_token)
        assert "read:financial_data" in claims.scopes
    
    def test_validate_delegation_chain(self, delegation_service, token_service):
        """测试委托链验证"""
        # 创建三级委托链
        # 第一级：用户 -> Master Agent
        level1_claims = TokenClaims(
            sub="master_agent",
            iss="user",
            scopes={"read:data", "write:data", "delegate:data"}
        )
        level1_token = token_service.encode(level1_claims)
        
        # 第二级：Master Agent -> Worker Agent 1
        level2_token = delegation_service.create_delegated_token(
            parent_token=level1_token,
            child_sub="worker_agent_1",
            scopes={"read:data"}
        )
        
        # 第三级：Worker Agent 1 -> Worker Agent 2（应该失败，因为level2没有委托权限）
        level3_token = delegation_service.create_delegated_token(
            parent_token=level2_token,
            child_sub="worker_agent_2",
            scopes={"read:data"}
        )
        
        # level2应该有有效的委托链
        assert delegation_service.validate_delegation_chain(level2_token) is True
        
        # level3应该没有有效的委托链（因为level2没有委托权限）
        if level3_token:
            assert delegation_service.validate_delegation_chain(level3_token) is False
    
    def test_get_trust_chain(self, delegation_service, root_token, token_service):
        """测试获取信任链"""
        # 创建委托Token
        delegated_token = delegation_service.create_delegated_token(
            parent_token=root_token,
            child_sub="worker_agent",
            scopes={"read:data"}
        )
        
        # 获取信任链
        trust_chain = delegation_service.get_trust_chain(delegated_token)
        
        assert trust_chain is not None
        assert len(trust_chain) == 2  # master_agent, worker_agent
        assert trust_chain[0] == "master_agent"
        assert trust_chain[1] == "worker_agent"
        
        # 根Token的信任链
        root_trust_chain = delegation_service.get_trust_chain(root_token)
        assert root_trust_chain is not None
        assert len(root_trust_chain) == 1  # 只有master_agent
        assert root_trust_chain[0] == "master_agent"