"""
测试Token服务
"""
import time
import pytest

from agent_iam.models import TokenClaims
from agent_iam.token_service import TokenService


class TestTokenService:
    """测试TokenService"""
    
    @pytest.fixture
    def token_service(self):
        """创建TokenService实例"""
        return TokenService(secret_key="test_secret_key")
    
    @pytest.fixture
    def sample_claims(self):
        """创建示例claims"""
        return TokenClaims(
            sub="user123",
            iss="iam_controller",
            iat=time.time(),
            exp=time.time() + 3600,
            scopes={"read:data", "write:data"},
            max_uses=10
        )
    
    def test_encode_decode(self, token_service, sample_claims):
        """测试Token编码和解码"""
        # 编码Token
        token = token_service.encode(sample_claims)
        assert token is not None
        assert len(token.split('.')) == 3  # JWT格式：header.payload.signature
        
        # 解码Token
        decoded_claims = token_service.decode(token)
        assert decoded_claims is not None
        assert decoded_claims.sub == sample_claims.sub
        assert decoded_claims.iss == sample_claims.iss
        assert "read:data" in decoded_claims.scopes
    
    def test_invalid_token(self, token_service):
        """测试无效Token"""
        # 无效Token格式
        invalid_token = "invalid.token.format"
        decoded = token_service.decode(invalid_token)
        assert decoded is None
        
        # 空Token
        decoded = token_service.decode("")
        assert decoded is None
    
    def test_token_validation(self, token_service, sample_claims):
        """测试Token验证"""
        # 有效的Token
        token = token_service.encode(sample_claims)
        assert token_service.validate_token(token) is True
        
        # 修改Token使其无效
        parts = token.split('.')
        tampered_token = f"{parts[0]}.{parts[1]}.tampered_signature"
        assert token_service.validate_token(tampered_token) is False
    
    def test_expired_token(self, token_service):
        """测试过期Token"""
        expired_claims = TokenClaims(
            sub="user123",
            iss="iam_controller",
            iat=time.time() - 7200,
            exp=time.time() - 3600  # 1小时前过期
        )
        
        token = token_service.encode(expired_claims)
        assert token_service.validate_token(token) is False
    
    def test_increment_use_count(self, token_service):
        """测试增加使用次数"""
        claims = TokenClaims(
            sub="user123",
            iss="iam_controller",
            max_uses=3,
            used_count=0
        )
        
        token = token_service.encode(claims)
        
        # 第一次使用
        updated_token = token_service.increment_use_count(token)
        assert updated_token is not None
        
        # 解码检查使用次数
        updated_claims = token_service.decode(updated_token)
        assert updated_claims.used_count == 1
        
        # 第二次使用
        updated_token2 = token_service.increment_use_count(updated_token)
        updated_claims2 = token_service.decode(updated_token2)
        assert updated_claims2.used_count == 2
        
        # 第三次使用（达到上限）
        updated_token3 = token_service.increment_use_count(updated_token2)
        updated_claims3 = token_service.decode(updated_token3)
        assert updated_claims3.used_count == 3
        
        # 第四次使用应该失败（Token无效）
        updated_token4 = token_service.increment_use_count(updated_token3)
        # 由于达到max_uses，increment_use_count可能返回None或原token
        # 但validate_token应该返回False
        if updated_token4:
            assert token_service.validate_token(updated_token4) is False
    
    def test_token_without_max_uses(self, token_service):
        """测试没有使用次数限制的Token"""
        claims = TokenClaims(
            sub="user123",
            iss="iam_controller",
            max_uses=None  # 无限制
        )
        
        token = token_service.encode(claims)
        
        # 多次使用应该都成功
        for i in range(5):
            updated_token = token_service.increment_use_count(token)
            if updated_token:
                token = updated_token
        
        # Token应该仍然有效
        assert token_service.validate_token(token) is True