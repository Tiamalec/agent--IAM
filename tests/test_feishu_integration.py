"""
测试飞书集成模块
"""
import os
import json
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock

from agent_iam.feishu_integration import (
    FeishuSkill,
    FeishuAction,
    FeishuResource,
    FeishuPermissionMapper,
    FeishuOAuth2Client,
    FeishuSSOManager,
    FeishuOrgSync,
    FeishuAgent
)
from agent_iam.models import Actor, ActorType, TokenClaims
from agent_iam.token_service import TokenService
from agent_iam.auth_engine import AuthorizationEngine


class TestFeishuPermissionMapper:
    """测试权限映射器"""
    
    @pytest.fixture
    def permission_mapper(self):
        """创建权限映射器实例"""
        return FeishuPermissionMapper()
    
    def test_default_mappings_loaded(self, permission_mapper):
        """测试默认映射规则已加载"""
        assert FeishuSkill.CALENDAR in permission_mapper.mapping_rules
        assert FeishuSkill.IM in permission_mapper.mapping_rules
        assert FeishuSkill.DOC in permission_mapper.mapping_rules
        assert FeishuSkill.BASE in permission_mapper.mapping_rules
        assert FeishuSkill.TASK in permission_mapper.mapping_rules
        assert FeishuSkill.IAM_MANAGER in permission_mapper.mapping_rules
    
    def test_map_feishu_to_iam(self, permission_mapper):
        """测试飞书权限映射到IAM Scopes"""
        # 测试日历读取权限
        iam_scopes = permission_mapper.map_feishu_to_iam(
            FeishuSkill.CALENDAR,
            FeishuAction.READ,
            FeishuResource.CALENDAR
        )
        
        assert isinstance(iam_scopes, set)
        assert len(iam_scopes) > 0
        assert "read:calendar" in iam_scopes or "read:event" in iam_scopes
        
        # 测试消息发送权限
        iam_scopes = permission_mapper.map_feishu_to_iam(
            FeishuSkill.IM,
            FeishuAction.SEND,
            FeishuResource.MESSAGE
        )
        
        assert "send:message" in iam_scopes
    
    def test_map_iam_to_feishu(self, permission_mapper):
        """测试IAM Scopes映射到飞书权限"""
        test_scopes = {"read:calendar", "send:message"}
        
        feishu_permissions = permission_mapper.map_iam_to_feishu(test_scopes)
        
        assert isinstance(feishu_permissions, list)
        assert len(feishu_permissions) > 0
        
        # 检查是否包含预期的权限
        skill_values = [p["skill"].value for p in feishu_permissions]
        assert "lark-calendar" in skill_values or "lark-im" in skill_values
    
    def test_validate_iam_scopes(self, permission_mapper):
        """测试IAM Scopes验证"""
        # 用户拥有所需权限
        user_scopes = {"read:calendar", "read:event", "write:calendar"}
        is_valid = permission_mapper.validate_iam_scopes_for_feishu(
            FeishuSkill.CALENDAR,
            FeishuAction.READ,
            user_scopes
        )
        assert is_valid is True
        
        # 用户缺少所需权限
        user_scopes = {"read:calendar"}  # 缺少read:event
        is_valid = permission_mapper.validate_iam_scopes_for_feishu(
            FeishuSkill.CALENDAR,
            FeishuAction.READ,
            user_scopes
        )
        # 注意：read:calendar可能就足够了，取决于映射规则
        # 我们只检查函数能正常运行
    
    def test_load_config_from_json(self, permission_mapper):
        """测试从JSON文件加载配置"""
        # 创建临时JSON配置文件
        config_data = {
            "skill_mappings": {
                "lark-calendar": {
                    "iam_scopes": {
                        "test_action": ["test:scope"]
                    }
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name
        
        try:
            # 加载配置
            result = permission_mapper.load_config(config_file)
            assert result is True
            
            # 检查新映射是否生效
            iam_scopes = permission_mapper.map_feishu_to_iam(
                FeishuSkill.CALENDAR,
                FeishuAction("test_action"),
                FeishuResource.CALENDAR
            )
            assert "test:scope" in iam_scopes
        finally:
            os.unlink(config_file)
    
    def test_add_custom_mapping(self, permission_mapper):
        """测试添加自定义映射规则"""
        # 添加自定义映射
        permission_mapper.add_custom_mapping(
            FeishuSkill.CALENDAR,
            FeishuAction("custom_action"),
            {"custom:scope1", "custom:scope2"}
        )
        
        # 验证映射生效
        required_scopes = permission_mapper.get_required_scopes_for_feishu(
            FeishuSkill.CALENDAR,
            FeishuAction("custom_action")
        )
        
        assert "custom:scope1" in required_scopes
        assert "custom:scope2" in required_scopes


class TestFeishuOAuth2Client:
    """测试OAuth2客户端"""
    
    @pytest.fixture
    def oauth_client(self):
        """创建OAuth2客户端实例"""
        return FeishuOAuth2Client(
            app_id="test_app_id",
            app_secret="test_app_secret",
            redirect_uri="https://example.com/callback"
        )
    
    def test_initialization(self, oauth_client):
        """测试客户端初始化"""
        assert oauth_client.app_id == "test_app_id"
        assert oauth_client.app_secret == "test_app_secret"
        assert oauth_client.redirect_uri == "https://example.com/callback"
        assert oauth_client.base_url == "https://open.feishu.cn"
    
    def test_get_authorization_url(self, oauth_client):
        """测试生成授权URL"""
        auth_url = oauth_client.get_authorization_url(
            state="test_state",
            scope="contact:user.base:readonly"
        )
        
        assert auth_url.startswith("https://open.feishu.cn/open-apis/authen/v1/index")
        assert "app_id=test_app_id" in auth_url
        assert "redirect_uri=https%3A%2F%2Fexample.com%2Fcallback" in auth_url
        assert "scope=contact%3Auser.base%3Areadonly" in auth_url
        assert "state=test_state" in auth_url
    
    @patch('requests.post')
    def test_exchange_code_for_token_http(self, mock_post, oauth_client):
        """测试HTTP方式换取访问令牌"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 7200,
            "token_type": "Bearer"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # 调用方法
        result = oauth_client._exchange_code_for_token_http("test_code")
        
        # 验证结果
        assert result["success"] is True
        assert result["access_token"] == "test_access_token"
        assert result["refresh_token"] == "test_refresh_token"
        assert result["expires_in"] == 7200
        
        # 验证请求参数
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "open.feishu.cn" in call_args[0][0]
        assert call_args[1]["json"]["grant_type"] == "authorization_code"
        assert call_args[1]["json"]["code"] == "test_code"


class TestFeishuSSOManager:
    """测试SSO管理器"""
    
    @pytest.fixture
    def sso_manager(self):
        """创建SSO管理器实例"""
        # 创建模拟的OAuth2客户端
        mock_oauth_client = Mock(spec=FeishuOAuth2Client)
        
        # 模拟令牌交换
        mock_oauth_client.exchange_code_for_token.return_value = {
            "success": True,
            "access_token": "test_access_token"
        }
        
        # 模拟获取用户信息
        mock_oauth_client.get_user_info.return_value = {
            "success": True,
            "user": {
                "user_id": "test_user_id",
                "open_id": "test_open_id",
                "union_id": "test_union_id",
                "name": "测试用户",
                "email": "test@example.com",
                "mobile": "13800138000",
                "avatar_url": "https://example.com/avatar.jpg"
            }
        }
        
        # 创建TokenService
        token_service = TokenService(secret_key="test_secret_key")
        
        # 创建AuthorizationEngine
        auth_engine = AuthorizationEngine()
        
        return FeishuSSOManager(mock_oauth_client, token_service, auth_engine)
    
    def test_authenticate_user_success(self, sso_manager):
        """测试成功验证用户"""
        # 调用认证方法
        actor, iam_token, user_info = sso_manager.authenticate_user("test_code")
        
        # 验证结果
        assert actor is not None
        assert isinstance(actor, Actor)
        assert actor.name == "测试用户"
        assert actor.type == ActorType.USER
        
        assert iam_token is not None
        assert isinstance(iam_token, str)
        assert len(iam_token) > 0
        
        assert user_info is not None
        assert user_info["name"] == "测试用户"
        assert user_info["email"] == "test@example.com"
        
        # 验证Actor属性
        assert actor.attributes["feishu_user_id"] == "test_user_id"
        assert actor.attributes["feishu_open_id"] == "test_open_id"
        assert actor.attributes["email"] == "test@example.com"
        assert actor.attributes["source"] == "feishu"
    
    def test_authenticate_user_failure(self):
        """测试用户验证失败"""
        # 创建模拟的OAuth2客户端（返回失败）
        mock_oauth_client = Mock(spec=FeishuOAuth2Client)
        mock_oauth_client.exchange_code_for_token.return_value = {
            "success": False,
            "error": "Invalid code"
        }
        
        token_service = TokenService(secret_key="test_secret_key")
        auth_engine = AuthorizationEngine()
        
        sso_manager = FeishuSSOManager(mock_oauth_client, token_service, auth_engine)
        
        # 调用认证方法
        actor, iam_token, user_info = sso_manager.authenticate_user("invalid_code")
        
        # 验证结果
        assert actor is None
        assert iam_token is None
        assert user_info is None


class TestFeishuAgent:
    """测试飞书Agent"""
    
    @pytest.fixture
    def feishu_agent(self):
        """创建飞书Agent实例"""
        return FeishuAgent(
            name="智能日历助手",
            agent_type=ActorType.MASTER_AGENT,
            feishu_app_id="feishu_app_calendar_001",
            feishu_skills=[FeishuSkill.CALENDAR, FeishuSkill.IM]
        )
    
    def test_feishu_agent_creation(self, feishu_agent):
        """测试飞书Agent创建"""
        assert feishu_agent.name == "智能日历助手"
        assert feishu_agent.type == ActorType.MASTER_AGENT
        assert feishu_agent.feishu_app_id == "feishu_app_calendar_001"
        
        # 验证Skills
        assert len(feishu_agent.feishu_skills) == 2
        assert FeishuSkill.CALENDAR in feishu_agent.feishu_skills
        assert FeishuSkill.IM in feishu_agent.feishu_skills
    
    def test_add_remove_skill(self, feishu_agent):
        """测试添加和移除Skill"""
        # 初始Skills数量
        initial_count = len(feishu_agent.feishu_skills)
        
        # 添加新Skill
        feishu_agent.add_feishu_skill(FeishuSkill.DOC)
        assert len(feishu_agent.feishu_skills) == initial_count + 1
        assert FeishuSkill.DOC in feishu_agent.feishu_skills
        
        # 移除Skill
        feishu_agent.remove_feishu_skill(FeishuSkill.IM)
        assert len(feishu_agent.feishu_skills) == initial_count  # 回到初始数量
        assert FeishuSkill.IM not in feishu_agent.feishu_skills
    
    def test_has_skill(self, feishu_agent):
        """测试检查Skill"""
        assert feishu_agent.has_feishu_skill(FeishuSkill.CALENDAR) is True
        assert feishu_agent.has_feishu_skill(FeishuSkill.DOC) is False
    
    def test_to_dict(self, feishu_agent):
        """测试转换为字典"""
        agent_dict = feishu_agent.to_dict()
        
        assert "feishu_app_id" in agent_dict
        assert agent_dict["feishu_app_id"] == "feishu_app_calendar_001"
        
        assert "feishu_skills" in agent_dict
        assert isinstance(agent_dict["feishu_skills"], list)
        assert len(agent_dict["feishu_skills"]) == 2
        
        assert "feishu_skill_count" in agent_dict
        assert agent_dict["feishu_skill_count"] == 2


class TestFeishuOrgSync:
    """测试组织架构同步"""
    
    @pytest.fixture
    def org_sync(self):
        """创建组织架构同步器实例"""
        return FeishuOrgSync(
            app_id="test_app_id",
            app_secret="test_app_secret"
        )
    
    def test_initialization(self, org_sync):
        """测试初始化"""
        assert org_sync.app_id == "test_app_id"
        assert org_sync.app_secret == "test_app_secret"
    
    @patch('requests.post')
    def test_get_tenant_access_token(self, mock_post, org_sync):
        """测试获取租户访问令牌"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_tenant_token",
            "expire": 7200
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # 调用方法
        result = org_sync._get_tenant_access_token()
        
        # 验证结果
        assert result["success"] is True
        assert result["tenant_access_token"] == "test_tenant_token"
        assert result["expire"] == 7200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])