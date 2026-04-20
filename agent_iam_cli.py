#!/usr/bin/env python3
"""
AI Agent IAM 命令行工具
"""
import argparse
import json
import sys
import time
from typing import Optional

from agent_iam.models import Actor, ActorType, ActionType, ResourceType, TokenClaims
from agent_iam.token_service import TokenService
from agent_iam.auth_engine import AuthorizationEngine
from agent_iam.delegation import DelegationService
from agent_iam.audit_logger import AuditLogger


class IAMCLI:
    """IAM命令行工具"""
    
    def __init__(self):
        self.token_service = TokenService(secret_key="cli_secret_key")
        self.auth_engine = AuthorizationEngine()
        self.delegation_service = DelegationService(self.token_service)
        self.audit_logger = AuditLogger("cli_audit_log.jsonl")
        
        self.actors = {}
        self.tokens = {}
    
    def create_actor(self, name: str, actor_type: str, attributes: Optional[dict] = None) -> dict:
        """创建参与者"""
        actor_type_enum = ActorType[actor_type.upper()]
        actor = Actor(name=name, type=actor_type_enum, attributes=attributes or {})
        self.actors[actor.id] = actor
        
        # 记录审计
        self.audit_logger.log_event(
            actor_id="cli",
            action="create_actor",
            resource=f"actor_{actor.id}",
            result="allow",
            details={"name": name, "type": actor_type}
        )
        
        return actor.to_dict()
    
    def issue_token(self, issuer_id: str, subject_id: str, scopes: list, 
                   expires_in: int = 3600, max_uses: Optional[int] = None) -> Optional[str]:
        """签发Token"""
        if issuer_id not in self.actors or subject_id not in self.actors:
            print(f"错误: 参与者不存在")
            return None
        
        claims = TokenClaims(
            sub=subject_id,
            iss=issuer_id,
            iat=time.time(),
            exp=time.time() + expires_in,
            scopes=set(scopes),
            max_uses=max_uses
        )
        
        token = self.token_service.encode(claims)
        self.tokens[subject_id] = token
        
        # 记录审计
        self.audit_logger.log_event(
            actor_id=issuer_id,
            action="issue_token",
            resource=f"token_for_{subject_id}",
            result="allow",
            details={"scopes": scopes, "expires_in": expires_in}
        )
        
        return token
    
    def verify_token(self, token: str) -> dict:
        """验证Token"""
        try:
            claims = self.token_service.decode(token)
            is_valid = self.token_service.validate_token(token)
            
            return {
                "valid": is_valid,
                "claims": claims.to_dict() if claims else None,
                "message": "Token有效" if is_valid else "Token无效"
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def delegate_token(self, parent_token: str, child_sub: str, scopes: list, 
                      expires_in: int = 1800) -> Optional[str]:
        """委托Token"""
        delegated_token = self.delegation_service.create_delegated_token(
            parent_token=parent_token,
            child_sub=child_sub,
            scopes=set(scopes),
            expires_in=expires_in
        )
        
        if delegated_token:
            self.tokens[child_sub] = delegated_token
            
            # 记录审计
            claims = self.token_service.decode(parent_token)
            if claims:
                self.audit_logger.log_event(
                    actor_id=claims.sub,
                    action="delegate_token",
                    resource=f"token_for_{child_sub}",
                    result="allow",
                    details={"child": child_sub, "scopes": scopes}
                )
        
        return delegated_token
    
    def check_permission(self, token: str, action: str, resource: str, context: Optional[dict] = None) -> dict:
        """检查权限"""
        try:
            claims = self.token_service.decode(token)
            if not claims:
                return {"authorized": False, "reason": "无效Token"}
            
            action_enum = ActionType[action.upper()]
            resource_enum = ResourceType[resource.upper()]
            
            is_authorized = self.auth_engine.evaluate_token_authorization(
                claims, action_enum, resource_enum, context or {}
            )
            
            # 记录审计
            self.audit_logger.log_event(
                actor_id=claims.sub,
                action=f"check_permission_{action}",
                resource=resource,
                result="allow" if is_authorized else "deny",
                details={"context": context, "authorized": is_authorized}
            )
            
            return {
                "authorized": is_authorized,
                "subject": claims.sub,
                "action": action,
                "resource": resource,
                "context": context
            }
        except Exception as e:
            return {"authorized": False, "error": str(e)}
    
    def show_audit_logs(self, limit: int = 10) -> list:
        """显示审计日志"""
        events = self.audit_logger.load_events()
        return [e.to_dict() for e in events[-limit:]]
    
    def show_system_info(self) -> dict:
        """显示系统信息"""
        return {
            "actors": len(self.actors),
            "tokens": len(self.tokens),
            "audit_events": len(self.audit_logger.load_events()),
            "integrity_check": self.audit_logger.verify_integrity()
        }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="AI Agent IAM 命令行工具")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 创建参与者
    parser_create = subparsers.add_parser("create-actor", help="创建参与者")
    parser_create.add_argument("--name", required=True, help="参与者名称")
    parser_create.add_argument("--type", required=True, choices=["user", "master_agent", "worker_agent"], help="参与者类型")
    parser_create.add_argument("--attributes", type=json.loads, default="{}", help="属性JSON")
    
    # 签发Token
    parser_issue = subparsers.add_parser("issue-token", help="签发Token")
    parser_issue.add_argument("--issuer", required=True, help="签发者ID")
    parser_issue.add_argument("--subject", required=True, help="接收者ID")
    parser_issue.add_argument("--scopes", required=True, nargs="+", help="权限范围")
    parser_issue.add_argument("--expires-in", type=int, default=3600, help="过期时间(秒)")
    parser_issue.add_argument("--max-uses", type=int, help="最大使用次数")
    
    # 验证Token
    parser_verify = subparsers.add_parser("verify-token", help="验证Token")
    parser_verify.add_argument("--token", required=True, help="要验证的Token")
    
    # 委托Token
    parser_delegate = subparsers.add_parser("delegate-token", help="委托Token")
    parser_delegate.add_argument("--parent-token", required=True, help="父Token")
    parser_delegate.add_argument("--child", required=True, help="子参与者ID")
    parser_delegate.add_argument("--scopes", required=True, nargs="+", help="委托的权限范围")
    parser_delegate.add_argument("--expires-in", type=int, default=1800, help="过期时间(秒)")
    
    # 检查权限
    parser_check = subparsers.add_parser("check-permission", help="检查权限")
    parser_check.add_argument("--token", required=True, help="Token")
    parser_check.add_argument("--action", required=True, help="操作")
    parser_check.add_argument("--resource", required=True, help="资源")
    parser_check.add_argument("--context", type=json.loads, default="{}", help="上下文JSON")
    
    # 显示审计日志
    parser_audit = subparsers.add_parser("show-audit", help="显示审计日志")
    parser_audit.add_argument("--limit", type=int, default=10, help="显示数量")
    
    # 系统信息
    parser_info = subparsers.add_parser("system-info", help="系统信息")
    
    # 运行演示
    parser_demo = subparsers.add_parser("demo", help="运行演示")
    parser_demo.add_argument("--type", default="basic", choices=["basic", "advanced"], help="演示类型")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    cli = IAMCLI()
    
    try:
        if args.command == "create-actor":
            result = cli.create_actor(args.name, args.type, args.attributes)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif args.command == "issue-token":
            token = cli.issue_token(args.issuer, args.subject, args.scopes, args.expires_in, args.max_uses)
            if token:
                print(f"Token: {token}")
                claims = cli.token_service.decode(token)
                if claims:
                    print(f"Claims: {json.dumps(claims.to_dict(), indent=2, ensure_ascii=False)}")
            else:
                print("错误: 签发Token失败")
        
        elif args.command == "verify-token":
            result = cli.verify_token(args.token)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif args.command == "delegate-token":
            token = cli.delegate_token(args.parent_token, args.child, args.scopes, args.expires_in)
            if token:
                print(f"委托Token: {token}")
            else:
                print("错误: 委托Token失败")
        
        elif args.command == "check-permission":
            result = cli.check_permission(args.token, args.action, args.resource, args.context)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif args.command == "show-audit":
            logs = cli.show_audit_logs(args.limit)
            print(json.dumps(logs, indent=2, ensure_ascii=False))
        
        elif args.command == "system-info":
            info = cli.show_system_info()
            print(json.dumps(info, indent=2, ensure_ascii=False))
        
        elif args.command == "demo":
            if args.type == "basic":
                print("运行基础演示...")
                # 创建示例参与者
                user = cli.create_actor("演示用户", "user")
                master = cli.create_actor("Master Agent", "master_agent")
                worker = cli.create_actor("Worker Agent", "worker_agent")
                
                print(f"创建参与者: {user['name']}, {master['name']}, {worker['name']}")
                
                # 签发Token
                token = cli.issue_token(user['id'], master['id'], ["read:financial_data", "delegate:financial_data"])
                if token:
                    print(f"签发Token成功")
                    
                    # 委托Token
                    delegated = cli.delegate_token(token, worker['id'], ["read:financial_data"])
                    if delegated:
                        print(f"委托Token成功")
                        
                        # 检查权限
                        result = cli.check_permission(delegated, "read", "financial_data")
                        print(f"权限检查: {result['authorized']}")
                    else:
                        print("委托Token失败")
                else:
                    print("签发Token失败")
            
            elif args.type == "advanced":
                print("运行高级演示...")
                from agent_iam.advanced_demo import FinancialReportDemo
                demo = FinancialReportDemo()
                demo.run_full_demo()
        
        else:
            print(f"未知命令: {args.command}")
            sys.exit(1)
    
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()