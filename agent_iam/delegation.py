"""
委托逻辑：父Token派生子Token
"""
import time
from typing import Set, List, Optional

from .models import TokenClaims
from .token_service import TokenService


class DelegationService:
    """委托服务"""
    
    def __init__(self, token_service: TokenService):
        self.token_service = token_service
    
    def can_delegate(self, parent_token: str, requested_scopes: Set[str]) -> Optional[TokenClaims]:
        """检查父Token是否可以委托请求的权限范围"""
        parent_claims = self.token_service.decode(parent_token)
        if parent_claims is None:
            return None
        
        # 检查父Token是否有效
        if not parent_claims.is_valid():
            return None
        
        # 检查父Token是否有委托权限
        if "delegate" not in parent_claims.scopes and "*" not in parent_claims.scopes:
            # 检查是否有特定资源的委托权限
            delegate_scopes = {s for s in parent_claims.scopes if s.startswith("delegate:")}
            if not delegate_scopes:
                return None
        
        # 检查请求的scope是否是父Token scope的子集
        if not requested_scopes.issubset(parent_claims.scopes):
            # 允许通配符匹配
            for requested_scope in requested_scopes:
                if requested_scope not in parent_claims.scopes:
                    # 检查通配符
                    action_resource = requested_scope.split(':', 1)
                    if len(action_resource) == 2:
                        action, resource = action_resource
                        wildcard_scope = f"{action}:*"
                        if wildcard_scope not in parent_claims.scopes:
                            return None
                    else:
                        return None
        
        return parent_claims
    
    def create_delegated_token(self, parent_token: str, 
                              child_sub: str,
                              scopes: Set[str],
                              expires_in: Optional[int] = 3600,
                              max_uses: Optional[int] = None,
                              context: Optional[dict] = None) -> Optional[str]:
        """创建委托Token（子Token）"""
        parent_claims = self.can_delegate(parent_token, scopes)
        if parent_claims is None:
            return None
        
        # 构建信任链
        trust_chain = parent_claims.trust_chain.copy()
        trust_chain.append(parent_claims.sub)
        
        # 创建子Token声明
        child_claims = TokenClaims(
            sub=child_sub,
            iss=parent_claims.sub,  # 签发者是父Token的主体
            iat=time.time(),
            exp=time.time() + expires_in if expires_in else None,
            scopes=scopes,
            parent_token=parent_token,
            trust_chain=trust_chain,
            max_uses=max_uses,
            context=context or {}
        )
        
        # 编码Token
        return self.token_service.encode(child_claims)
    
    def validate_delegation_chain(self, token: str) -> bool:
        """验证委托链的完整性"""
        claims = self.token_service.decode(token)
        if claims is None:
            return False
        
        # 如果没有父Token，则是根Token
        if claims.parent_token is None:
            return True
        
        # 递归验证父Token
        parent_valid = self.validate_delegation_chain(claims.parent_token)
        if not parent_valid:
            return False
        
        # 验证当前Token的scope是父Token scope的子集
        parent_claims = self.token_service.decode(claims.parent_token)
        if parent_claims is None:
            return False
        
        for scope in claims.scopes:
            if scope not in parent_claims.scopes:
                # 检查通配符
                action_resource = scope.split(':', 1)
                if len(action_resource) == 2:
                    action, resource = action_resource
                    wildcard_scope = f"{action}:*"
                    if wildcard_scope not in parent_claims.scopes:
                        return False
                else:
                    return False
        
        return True
    
    def get_trust_chain(self, token: str) -> Optional[List[str]]:
        """获取完整的信任链"""
        claims = self.token_service.decode(token)
        if claims is None:
            return None
        
        chain = claims.trust_chain.copy()
        chain.append(claims.sub)
        return chain