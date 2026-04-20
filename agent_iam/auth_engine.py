"""
授权引擎：RBAC + ABAC 混合授权校验
"""
import time
from typing import Dict, Any, List, Optional, Set

from .models import Policy, ActionType, ResourceType, TokenClaims


class AuthorizationEngine:
    """授权引擎"""
    
    def __init__(self):
        self.policies: Dict[str, Policy] = {}
        
    def add_policy(self, policy: Policy) -> None:
        """添加策略"""
        self.policies[policy.id] = policy
    
    def remove_policy(self, policy_id: str) -> None:
        """移除策略"""
        if policy_id in self.policies:
            del self.policies[policy_id]
    
    def evaluate_rbac(self, actor_role: str, action: ActionType, resource: ResourceType) -> bool:
        """RBAC评估：检查角色是否有权限执行操作"""
        for policy in self.policies.values():
            if policy.role == actor_role:
                if action in policy.actions and resource in policy.resources:
                    # 检查ABAC条件（如果没有条件则通过）
                    if not policy.conditions:
                        return True
                    # 如果有条件，评估条件（提供actor角色属性）
                    if self._evaluate_abac(policy.conditions, {"actor": {"role": actor_role}}):
                        return True
        return False
    
    def evaluate_abac(self, actor_attributes: Dict[str, Any], 
                     resource_attributes: Dict[str, Any],
                     action: ActionType, 
                     resource: ResourceType,
                     environment_attributes: Dict[str, Any]) -> bool:
        """ABAC评估：基于属性进行授权决策"""
        for policy in self.policies.values():
            if action in policy.actions and resource in policy.resources:
                # 检查是否有条件限制
                if not policy.conditions:
                    # 如果没有条件，则通过
                    return True
                
                # 构建完整的属性集合
                all_attributes = {
                    "actor": actor_attributes,
                    "resource": resource_attributes,
                    "environment": environment_attributes
                }
                if self._evaluate_abac(policy.conditions, all_attributes):
                    return True
        return False
    
    def _evaluate_abac(self, conditions: Dict[str, Any], attributes: Dict[str, Any]) -> bool:
        """评估ABAC条件"""
        if not conditions:
            return True
        
        for key, expected_value in conditions.items():
            # 简单的属性路径解析，如 "actor.department"
            parts = key.split('.')
            current = attributes
            
            try:
                for part in parts:
                    if isinstance(current, dict):
                        current = current.get(part)
                    else:
                        return False
                
                # 比较值
                if current != expected_value:
                    return False
            except Exception:
                return False
        
        return True
    
    def evaluate_token_authorization(self, token_claims: TokenClaims, 
                                    action: ActionType, 
                                    resource: ResourceType,
                                    context: Dict[str, Any] = None) -> bool:
        """基于Token进行授权评估"""
        if context is None:
            context = {}
        
        # 检查Token是否有效
        if not token_claims.is_valid():
            return False
        
        # 检查scope是否包含所需权限
        required_scope = f"{action.value}:{resource.value}"
        if required_scope not in token_claims.scopes:
            # 也支持通配符scope，如 "read:*"
            wildcard_scope = f"{action.value}:*"
            if wildcard_scope not in token_claims.scopes:
                return False
        
        # 检查上下文条件（ABAC）
        if token_claims.context:
            # 合并Token上下文和请求上下文
            evaluation_context = {**token_claims.context, **context}
            
            # 简单的上下文条件检查
            for key, expected_value in token_claims.context.items():
                if key.startswith("require_"):
                    actual_key = key[8:]  # 移除 "require_" 前缀
                    if actual_key in evaluation_context:
                        if evaluation_context[actual_key] != expected_value:
                            return False
        
        return True
    
    def create_policy_from_template(self, role: str, 
                                   actions: List[ActionType],
                                   resources: List[ResourceType],
                                   conditions: Dict[str, Any] = None) -> Policy:
        """从模板创建策略"""
        if conditions is None:
            conditions = {}
        
        return Policy(
            name=f"{role}_policy",
            role=role,
            actions=set(actions),
            resources=set(resources),
            conditions=conditions
        )