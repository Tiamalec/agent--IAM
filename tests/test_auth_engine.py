"""
测试授权引擎
"""
import pytest

from agent_iam.models import Policy, ActionType, ResourceType, TokenClaims
from agent_iam.auth_engine import AuthorizationEngine


class TestAuthorizationEngine:
    """测试AuthorizationEngine"""
    
    @pytest.fixture
    def auth_engine(self):
        """创建AuthorizationEngine实例"""
        engine = AuthorizationEngine()
        
        # 添加测试策略
        policy1 = Policy(
            name="admin_policy",
            role="admin",
            actions={ActionType.READ, ActionType.WRITE, ActionType.DELETE},
            resources={ResourceType.FINANCIAL_DATA, ResourceType.USER_DATA},
            conditions={"actor.role": "admin"}  # 只有admin角色可以使用此策略
        )
        
        policy2 = Policy(
            name="reader_policy",
            role="reader",
            actions={ActionType.READ},
            resources={ResourceType.FINANCIAL_DATA},
            conditions={"actor.department": "finance"}  # ABAC条件
        )
        
        engine.add_policy(policy1)
        engine.add_policy(policy2)
        
        return engine
    
    def test_rbac_evaluation(self, auth_engine):
        """测试RBAC评估"""
        # admin角色应该有读写权限（满足条件）
        assert auth_engine.evaluate_rbac("admin", ActionType.READ, ResourceType.FINANCIAL_DATA) is True
        assert auth_engine.evaluate_rbac("admin", ActionType.WRITE, ResourceType.FINANCIAL_DATA) is True
        
        # reader角色只有读权限，但需要department=fiance条件
        # 由于RBAC评估不提供department属性，应该返回False
        assert auth_engine.evaluate_rbac("reader", ActionType.READ, ResourceType.FINANCIAL_DATA) is False
        assert auth_engine.evaluate_rbac("reader", ActionType.WRITE, ResourceType.FINANCIAL_DATA) is False
        
        # 不存在的角色
        assert auth_engine.evaluate_rbac("nonexistent", ActionType.READ, ResourceType.FINANCIAL_DATA) is False
    
    def test_abac_evaluation(self, auth_engine):
        """测试ABAC评估"""
        # 符合条件的情况
        actor_attrs = {"department": "finance"}
        resource_attrs = {"sensitivity": "high"}
        env_attrs = {"time": "working_hours"}
        
        assert auth_engine.evaluate_abac(
            actor_attributes=actor_attrs,
            resource_attributes=resource_attrs,
            action=ActionType.READ,
            resource=ResourceType.FINANCIAL_DATA,
            environment_attributes=env_attrs
        ) is True
        
        # 不符合条件的情况
        actor_attrs_wrong = {"department": "marketing"}
        
        assert auth_engine.evaluate_abac(
            actor_attributes=actor_attrs_wrong,
            resource_attributes=resource_attrs,
            action=ActionType.READ,
            resource=ResourceType.FINANCIAL_DATA,
            environment_attributes=env_attrs
        ) is False
    
    def test_token_authorization(self, auth_engine):
        """测试基于Token的授权"""
        # 创建有正确scope的Token
        claims = TokenClaims(
            sub="user123",
            iss="iam_controller",
            scopes={"read:financial_data"}
        )
        
        # 有权限的情况
        assert auth_engine.evaluate_token_authorization(
            claims, ActionType.READ, ResourceType.FINANCIAL_DATA
        ) is True
        
        # 无权限的情况（scope不匹配）
        assert auth_engine.evaluate_token_authorization(
            claims, ActionType.WRITE, ResourceType.FINANCIAL_DATA
        ) is False
        
        # 使用通配符scope
        claims_wildcard = TokenClaims(
            sub="user123",
            iss="iam_controller",
            scopes={"read:*"}  # 可以读取所有资源
        )
        
        assert auth_engine.evaluate_token_authorization(
            claims_wildcard, ActionType.READ, ResourceType.FINANCIAL_DATA
        ) is True
        
        assert auth_engine.evaluate_token_authorization(
            claims_wildcard, ActionType.READ, ResourceType.USER_DATA
        ) is True
        
        # 通配符不匹配的情况
        assert auth_engine.evaluate_token_authorization(
            claims_wildcard, ActionType.WRITE, ResourceType.FINANCIAL_DATA
        ) is False
    
    def test_token_with_context(self, auth_engine):
        """测试带上下文的Token授权"""
        claims = TokenClaims(
            sub="user123",
            iss="iam_controller",
            scopes={"read:financial_data"},
            context={"require_department": "finance", "require_project": "report"}
        )
        
        # 上下文匹配的情况
        context_matching = {"department": "finance", "project": "report"}
        
        assert auth_engine.evaluate_token_authorization(
            claims, ActionType.READ, ResourceType.FINANCIAL_DATA, context_matching
        ) is True
        
        # 上下文不匹配的情况
        context_not_matching = {"department": "marketing", "project": "report"}
        
        assert auth_engine.evaluate_token_authorization(
            claims, ActionType.READ, ResourceType.FINANCIAL_DATA, context_not_matching
        ) is False
    
    def test_create_policy_from_template(self, auth_engine):
        """测试从模板创建策略"""
        policy = auth_engine.create_policy_from_template(
            role="auditor",
            actions=[ActionType.READ],
            resources=[ResourceType.FINANCIAL_DATA, ResourceType.USER_DATA],
            conditions={"actor.role": "auditor"}
        )
        
        assert policy.role == "auditor"
        assert ActionType.READ in policy.actions
        assert ResourceType.FINANCIAL_DATA in policy.resources
        assert policy.conditions == {"actor.role": "auditor"}
        
        # 添加策略并验证
        auth_engine.add_policy(policy)
        assert auth_engine.evaluate_rbac("auditor", ActionType.READ, ResourceType.FINANCIAL_DATA) is True