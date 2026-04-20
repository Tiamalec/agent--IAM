"""
API测试
"""
import pytest
from fastapi.testclient import TestClient
import time

from agent_iam.api.app import app
from agent_iam.models import ActorType, ActionType, ResourceType
from agent_iam.token_service import TokenService


class TestAPI:
    """测试API端点"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def token_service(self):
        """创建Token服务"""
        # 使用与API相同的密钥
        return TokenService(secret_key="api_secret_key_change_in_production")
    
    @pytest.fixture
    def system_token(self, token_service):
        """创建系统Token（用于测试）"""
        from agent_iam.models import TokenClaims
        
        claims = TokenClaims(
            sub="system",
            iss="system",
            scopes={"*"},  # 所有权限
            exp=time.time() + 3600
        )
        return token_service.encode(claims)
    
    def test_root_endpoint(self, client):
        """测试根端点"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert data["service"] == "AI Agent IAM API"
        assert "endpoints" in data
    
    def test_create_actor(self, client, system_token):
        """测试创建参与者"""
        # 设置Authorization头
        headers = {"Authorization": f"Bearer {system_token}"}
        
        # 创建用户
        user_data = {
            "name": "测试用户",
            "type": "user",
            "attributes": {"department": "finance"}
        }
        
        response = client.post("/actors", json=user_data, headers=headers)
        assert response.status_code == 201
        
        data = response.json()
        assert "id" in data
        assert data["name"] == "测试用户"
        assert data["type"] == "user"
        assert data["attributes"]["department"] == "finance"
        
        user_id = data["id"]
        
        # 获取用户信息
        response = client.get(f"/actors/{user_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["name"] == "测试用户"
    
    def test_issue_token(self, client, system_token, token_service):
        """测试签发Token"""
        headers = {"Authorization": f"Bearer {system_token}"}
        
        # 先创建参与者
        user_data = {
            "name": "Token测试用户",
            "type": "user",
            "attributes": {}
        }
        
        response = client.post("/actors", json=user_data, headers=headers)
        assert response.status_code == 201
        user_id = response.json()["id"]
        
        # 签发Token
        token_data = {
            "subject": user_id,
            "scopes": ["read:financial_data", "write:user_data"],
            "expires_in": 3600,
            "max_uses": 10,
            "context": {"project": "test"}
        }
        
        response = client.post("/tokens", json=token_data, headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "token" in data
        assert "claims" in data
        
        token = data["token"]
        claims = data["claims"]
        
        assert claims["sub"] == user_id
        assert "read:financial_data" in claims["scopes"]
        assert claims["max_uses"] == 10
        
        # 验证Token
        verify_data = {"token": token}
        response = client.post("/tokens/verify", json=verify_data)
        assert response.status_code == 200
        
        verify_result = response.json()
        assert verify_result["valid"] is True
        assert verify_result["claims"]["sub"] == user_id
    
    def test_delegate_token(self, client, system_token, token_service):
        """测试委托Token"""
        headers = {"Authorization": f"Bearer {system_token}"}
        
        # 创建父参与者
        parent_data = {
            "name": "父Agent",
            "type": "master_agent",
            "attributes": {}
        }
        
        response = client.post("/actors", json=parent_data, headers=headers)
        assert response.status_code == 201
        parent_id = response.json()["id"]
        
        # 为父参与者签发有委托权限的Token
        parent_token_data = {
            "subject": parent_id,
            "scopes": ["read:financial_data", "delegate:financial_data"],
            "expires_in": 3600
        }
        
        response = client.post("/tokens", json=parent_token_data, headers=headers)
        assert response.status_code == 200
        parent_token = response.json()["token"]
        
        # 创建子参与者
        child_data = {
            "name": "子Agent",
            "type": "worker_agent",
            "attributes": {}
        }
        
        response = client.post("/actors", json=child_data, headers=headers)
        assert response.status_code == 201
        child_id = response.json()["id"]
        
        # 委托Token
        delegate_headers = {"Authorization": f"Bearer {parent_token}"}
        delegate_data = {
            "parent_token": parent_token,
            "child_subject": child_id,
            "scopes": ["read:financial_data"],
            "expires_in": 1800
        }
        
        response = client.post("/tokens/delegate", json=delegate_data, headers=delegate_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "token" in data
        assert "claims" in data
        
        delegated_token = data["token"]
        claims = data["claims"]
        
        assert claims["sub"] == child_id
        assert claims["iss"] == parent_id
        assert "read:financial_data" in claims["scopes"]
    
    def test_authorize(self, client, system_token, token_service):
        """测试授权检查"""
        headers = {"Authorization": f"Bearer {system_token}"}
        
        # 创建参与者和Token
        user_data = {
            "name": "授权测试用户",
            "type": "user",
            "attributes": {}
        }
        
        response = client.post("/actors", json=user_data, headers=headers)
        assert response.status_code == 201
        user_id = response.json()["id"]
        
        # 签发只有读权限的Token
        token_data = {
            "subject": user_id,
            "scopes": ["read:financial_data"],
            "expires_in": 3600
        }
        
        response = client.post("/tokens", json=token_data, headers=headers)
        assert response.status_code == 200
        token = response.json()["token"]
        
        # 测试读授权（应该通过）
        auth_data = {
            "token": token,
            "action": "read",
            "resource": "financial_data",
            "context": {}
        }
        
        response = client.post("/authorize", json=auth_data)
        assert response.status_code == 200
        
        auth_result = response.json()
        assert auth_result["authorized"] is True
        
        # 测试写授权（应该拒绝）
        auth_data_write = {
            "token": token,
            "action": "write",
            "resource": "financial_data",
            "context": {}
        }
        
        response = client.post("/authorize", json=auth_data_write)
        assert response.status_code == 200
        
        auth_result = response.json()
        assert auth_result["authorized"] is False
        assert "error" in auth_result
    
    def test_audit_logs(self, client, system_token):
        """测试审计日志查询"""
        headers = {"Authorization": f"Bearer {system_token}"}
        
        # 创建一些活动来生成审计日志
        user_data = {
            "name": "审计测试用户",
            "type": "user",
            "attributes": {}
        }
        
        response = client.post("/actors", json=user_data, headers=headers)
        assert response.status_code == 201
        
        # 查询审计日志
        response = client.get("/audit", headers=headers)
        assert response.status_code == 200
        
        logs = response.json()
        assert isinstance(logs, list)
        
        # 应该至少有一个日志条目（创建参与者的记录）
        if logs:
            log = logs[0]
            assert "id" in log
            assert "actor_id" in log
            assert "action" in log
            assert "resource" in log
            assert "result" in log
    
    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    def test_invalid_token_verification(self, client):
        """测试无效Token验证"""
        verify_data = {"token": "invalid.token.here"}
        response = client.post("/tokens/verify", json=verify_data)
        assert response.status_code == 200
        
        result = response.json()
        assert result["valid"] is False
        assert "error" in result
    
    def test_unauthorized_access(self, client):
        """测试未授权访问"""
        # 没有Token的情况下访问需要认证的端点
        response = client.post("/tokens", json={})
        assert response.status_code == 401  # 没有提供Authorization头
        
        # 无效Token
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/audit", headers=headers)
        assert response.status_code == 401  # 无效Token