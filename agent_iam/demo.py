"""
演示脚本：展示AI Agent IAM系统的核心功能
"""
import time
from typing import Dict, Any

from .models import Actor, ActorType, ActionType, ResourceType, TokenClaims
from .token_service import TokenService
from .auth_engine import AuthorizationEngine
from .delegation import DelegationService
from .audit_logger import AuditLogger


class IAMDemo:
    """IAM系统演示"""
    
    def __init__(self):
        # 初始化服务
        self.token_service = TokenService(secret_key="demo_secret_key_12345")
        self.auth_engine = AuthorizationEngine()
        self.delegation_service = DelegationService(self.token_service)
        self.audit_logger = AuditLogger("demo_audit_log.jsonl")
        
        # 创建参与者
        self.user = Actor(name="张三", type=ActorType.USER)
        self.master_agent = Actor(name="财务助手", type=ActorType.MASTER_AGENT)
        self.worker_agent = Actor(name="数据读取器", type=ActorType.WORKER_AGENT)
        
        # 创建策略
        self._setup_policies()
        
        # Token存储
        self.tokens: Dict[str, str] = {}
    
    def _setup_policies(self) -> None:
        """设置示例策略"""
        # 用户策略：可以委托和读取财务数据
        user_policy = self.auth_engine.create_policy_from_template(
            role="user",
            actions=[ActionType.READ, ActionType.DELEGATE],
            resources=[ResourceType.FINANCIAL_DATA]
        )
        self.auth_engine.add_policy(user_policy)
        
        # Master Agent策略：可以读取和委托财务数据
        master_policy = self.auth_engine.create_policy_from_template(
            role="master_agent",
            actions=[ActionType.READ, ActionType.DELEGATE],
            resources=[ResourceType.FINANCIAL_DATA]
        )
        self.auth_engine.add_policy(master_policy)
        
        # Worker Agent策略：只能读取财务数据
        worker_policy = self.auth_engine.create_policy_from_template(
            role="worker_agent",
            actions=[ActionType.READ],
            resources=[ResourceType.FINANCIAL_DATA]
        )
        self.auth_engine.add_policy(worker_policy)
    
    def demo_user_authorizes_master(self) -> bool:
        """演示：用户授权给Master Agent"""
        print("\n=== 步骤1: 用户授权给Master Agent ===")
        
        # 用户创建根Token授权给Master Agent
        root_claims = TokenClaims(
            sub=self.master_agent.id,
            iss=self.user.id,
            iat=time.time(),
            exp=time.time() + 3600,  # 1小时后过期
            scopes={"read:financial_data", "delegate:financial_data"},
            max_uses=100
        )
        
        root_token = self.token_service.encode(root_claims)
        self.tokens['root'] = root_token
        
        # 记录审计事件
        self.audit_logger.log_event(
            actor_id=self.user.id,
            action="issue_token",
            resource="master_agent",
            result="allow",
            details={"token_id": root_claims.sub, "scopes": list(root_claims.scopes)}
        )
        
        print(f"用户 {self.user.name} 创建了根Token授权给 {self.master_agent.name}")
        print(f"Token范围: {root_claims.scopes}")
        print(f"Token有效期: 1小时")
        
        return True
    
    def demo_master_delegates_to_worker(self) -> bool:
        """演示：Master Agent委托给Worker Agent"""
        print("\n=== 步骤2: Master Agent委托给Worker Agent ===")
        
        root_token = self.tokens.get('root')
        if not root_token:
            print("错误: 没有找到根Token")
            return False
        
        # Master Agent创建委托Token给Worker Agent（只读权限）
        delegated_token = self.delegation_service.create_delegated_token(
            parent_token=root_token,
            child_sub=self.worker_agent.id,
            scopes={"read:financial_data"},
            expires_in=1800,  # 30分钟后过期
            max_uses=10,  # 最多使用10次
            context={"project": "financial_report", "department": "finance"}
        )
        
        if not delegated_token:
            print("错误: 委托失败")
            return False
        
        self.tokens['delegated'] = delegated_token
        
        # 记录审计事件
        self.audit_logger.log_event(
            actor_id=self.master_agent.id,
            action="delegate_token",
            resource="worker_agent",
            result="allow",
            details={"parent_token": root_token[:20] + "...", "child_scopes": ["read:financial_data"]}
        )
        
        print(f"Master Agent {self.master_agent.name} 创建了委托Token给 {self.worker_agent.name}")
        print(f"委托Token范围: {{'read:financial_data'}}")
        print(f"委托Token有效期: 30分钟，最多使用10次")
        
        return True
    
    def demo_worker_access_financial_data(self) -> bool:
        """演示：Worker Agent访问财务数据"""
        print("\n=== 步骤3: Worker Agent访问财务数据 ===")
        
        delegated_token = self.tokens.get('delegated')
        if not delegated_token:
            print("错误: 没有找到委托Token")
            return False
        
        # 解码Token
        claims = self.token_service.decode(delegated_token)
        if not claims:
            print("错误: Token解码失败")
            return False
        
        # 验证Token
        if not self.token_service.validate_token(delegated_token):
            print("错误: Token无效")
            return False
        
        # 检查授权
        context = {"project": "financial_report", "department": "finance"}
        is_authorized = self.auth_engine.evaluate_token_authorization(
            claims, ActionType.READ, ResourceType.FINANCIAL_DATA, context
        )
        
        if is_authorized:
            # 增加使用次数
            updated_token = self.token_service.increment_use_count(delegated_token)
            if updated_token:
                self.tokens['delegated'] = updated_token
            
            # 记录成功的访问
            self.audit_logger.log_event(
                actor_id=self.worker_agent.id,
                action="read_financial_data",
                resource="financial_report_2024_q1",
                result="allow",
                details={"token_uses": claims.used_count + 1}
            )
            
            print(f"Worker Agent {self.worker_agent.name} 成功读取财务数据")
            print(f"Token已使用次数: {claims.used_count + 1}")
            return True
        else:
            # 记录失败的访问
            self.audit_logger.log_event(
                actor_id=self.worker_agent.id,
                action="read_financial_data",
                resource="financial_report_2024_q1",
                result="deny",
                details={"reason": "unauthorized"}
            )
            
            print(f"Worker Agent {self.worker_agent.name} 无权访问财务数据")
            return False
    
    def demo_worker_tries_unauthorized_write(self) -> bool:
        """演示：Worker Agent尝试未授权的写入操作"""
        print("\n=== 步骤4: Worker Agent尝试未授权的写入操作 ===")
        
        delegated_token = self.tokens.get('delegated')
        if not delegated_token:
            print("错误: 没有找到委托Token")
            return False
        
        # 解码Token
        claims = self.token_service.decode(delegated_token)
        if not claims:
            print("错误: Token解码失败")
            return False
        
        # 检查写入授权（应该被拒绝）
        context = {"project": "financial_report", "department": "finance"}
        is_authorized = self.auth_engine.evaluate_token_authorization(
            claims, ActionType.WRITE, ResourceType.FINANCIAL_DATA, context
        )
        
        if not is_authorized:
            # 记录拒绝的访问
            self.audit_logger.log_event(
                actor_id=self.worker_agent.id,
                action="write_financial_data",
                resource="financial_report_2024_q1",
                result="deny",
                details={"reason": "insufficient_permissions"}
            )
            
            print(f"Worker Agent {self.worker_agent.name} 尝试写入财务数据被拒绝")
            print("原因: Token没有写入权限")
            return True  # 拒绝是预期的行为
        else:
            print("错误: Worker Agent不应该有写入权限")
            return False
    
    def demo_token_expiration(self) -> bool:
        """演示：过期Token被拒绝"""
        print("\n=== 步骤5: 过期Token被拒绝 ===")
        
        # 创建一个立即过期的Token
        expired_claims = TokenClaims(
            sub=self.worker_agent.id,
            iss=self.master_agent.id,
            iat=time.time() - 3600,  # 1小时前签发
            exp=time.time() - 1800,  # 30分钟前过期
            scopes={"read:financial_data"}
        )
        
        expired_token = self.token_service.encode(expired_claims)
        
        # 验证Token（应该失败）
        is_valid = self.token_service.validate_token(expired_token)
        
        if not is_valid:
            # 记录Token过期事件
            self.audit_logger.log_event(
                actor_id=self.worker_agent.id,
                action="access_with_expired_token",
                resource="financial_data",
                result="deny",
                details={"reason": "token_expired"}
            )
            
            print("过期Token被成功拒绝")
            return True
        else:
            print("错误: 过期Token不应该有效")
            return False
    
    def demo_audit_log_integrity(self) -> bool:
        """演示：审计日志完整性验证"""
        print("\n=== 步骤6: 审计日志完整性验证 ===")
        
        # 验证hash-chain完整性
        integrity_ok = self.audit_logger.verify_integrity()
        
        if integrity_ok:
            print("审计日志完整性验证通过")
            
            # 显示所有审计事件
            events = self.audit_logger.load_events()
            print(f"\n共记录 {len(events)} 个审计事件:")
            for event in events:
                print(f"  [{time.ctime(event.timestamp)}] {event.actor_id} {event.action} {event.resource} -> {event.result}")
            
            return True
        else:
            print("错误: 审计日志完整性验证失败")
            return False
    
    def run_full_demo(self) -> bool:
        """运行完整演示"""
        print("=" * 60)
        print("AI Agent IAM 系统演示")
        print("=" * 60)
        
        steps = [
            ("用户授权给Master Agent", self.demo_user_authorizes_master),
            ("Master Agent委托给Worker Agent", self.demo_master_delegates_to_worker),
            ("Worker Agent访问财务数据", self.demo_worker_access_financial_data),
            ("Worker Agent尝试未授权的写入", self.demo_worker_tries_unauthorized_write),
            ("过期Token被拒绝", self.demo_token_expiration),
            ("审计日志完整性验证", self.demo_audit_log_integrity),
        ]
        
        all_passed = True
        for step_name, step_func in steps:
            print(f"\n>>> 执行: {step_name}")
            try:
                success = step_func()
                if success:
                    print(f"✓ {step_name} 成功")
                else:
                    print(f"✗ {step_name} 失败")
                    all_passed = False
                    break
            except Exception as e:
                print(f"✗ {step_name} 出错: {e}")
                all_passed = False
                break
        
        if all_passed:
            print("\n" + "=" * 60)
            print("所有演示步骤完成！")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("演示过程中出现错误")
            print("=" * 60)
        
        return all_passed


if __name__ == "__main__":
    demo = IAMDemo()
    demo.run_full_demo()