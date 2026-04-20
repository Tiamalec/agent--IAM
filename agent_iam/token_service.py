"""
Token服务：HMAC签名Token的签发与校验
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Optional, Dict, Any, List

from .models import TokenClaims


class TokenService:
    """Token服务类"""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key.encode('utf-8')
        self.algorithm = algorithm
        
    def _sign(self, data: bytes) -> str:
        """生成HMAC签名"""
        if self.algorithm == "HS256":
            signature = hmac.new(self.secret_key, data, hashlib.sha256).digest()
        elif self.algorithm == "HS384":
            signature = hmac.new(self.secret_key, data, hashlib.sha384).digest()
        elif self.algorithm == "HS512":
            signature = hmac.new(self.secret_key, data, hashlib.sha512).digest()
        else:
            raise ValueError(f"Unsupported algorithm: {self.algorithm}")
        
        return base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')
    
    def _verify_signature(self, data: bytes, signature: str) -> bool:
        """验证签名"""
        expected_signature = self._sign(data)
        return hmac.compare_digest(expected_signature, signature)
    
    def encode(self, claims: TokenClaims) -> str:
        """将claims编码为Token字符串"""
        # 将claims转换为字典
        claims_dict = claims.to_dict()
        
        # 序列化头部
        header = {
            "alg": self.algorithm,
            "typ": "JWT"
        }
        
        # 编码头部和载荷
        header_encoded = base64.urlsafe_b64encode(
            json.dumps(header).encode('utf-8')
        ).decode('utf-8').rstrip('=')
        
        payload_encoded = base64.urlsafe_b64encode(
            json.dumps(claims_dict).encode('utf-8')
        ).decode('utf-8').rstrip('=')
        
        # 生成签名
        data_to_sign = f"{header_encoded}.{payload_encoded}".encode('utf-8')
        signature = self._sign(data_to_sign)
        
        # 组装Token
        return f"{header_encoded}.{payload_encoded}.{signature}"
    
    def decode(self, token: str) -> Optional[TokenClaims]:
        """解码Token字符串为TokenClaims对象"""
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return None
            
            header_encoded, payload_encoded, signature = parts
            
            # 验证签名
            data_to_verify = f"{header_encoded}.{payload_encoded}".encode('utf-8')
            if not self._verify_signature(data_to_verify, signature):
                return None
            
            # 解码payload
            payload_json = base64.urlsafe_b64decode(payload_encoded + '=' * (4 - len(payload_encoded) % 4))
            payload_dict = json.loads(payload_json)
            
            # 转换为TokenClaims对象
            claims = TokenClaims(
                sub=payload_dict['sub'],
                iss=payload_dict['iss'],
                iat=payload_dict['iat'],
                exp=payload_dict.get('exp'),
                nbf=payload_dict.get('nbf'),
                scopes=set(payload_dict.get('scopes', [])),
                parent_token=payload_dict.get('parent_token'),
                trust_chain=payload_dict.get('trust_chain', []),
                max_uses=payload_dict.get('max_uses'),
                used_count=payload_dict.get('used_count', 0),
                context=payload_dict.get('context', {})
            )
            
            return claims
            
        except Exception:
            return None
    
    def validate_token(self, token: str) -> bool:
        """验证Token的有效性（签名、过期、使用次数）"""
        claims = self.decode(token)
        if claims is None:
            return False
        
        # 检查Token声明有效性
        if not claims.is_valid():
            return False
        
        return True
    
    def increment_use_count(self, token: str) -> Optional[str]:
        """增加Token使用次数，返回更新后的Token（如果需要重新编码）"""
        claims = self.decode(token)
        if claims is None:
            return None
        
        if claims.max_uses is not None:
            claims.used_count += 1
            
            # 如果使用次数未超过限制，重新编码Token
            if claims.used_count <= claims.max_uses:
                return self.encode(claims)
        
        return token