"""
高级演示脚本：展示复杂的多Agent协作场景
财务报告生成流水线
"""
import time
import json
from typing import Dict, Any, List, Optional
from enum import Enum

from .models import Actor, ActorType, ActionType, ResourceType, TokenClaims
from .token_service import TokenService
from .auth_engine import AuthorizationEngine
from .delegation import DelegationService
from .audit_logger import AuditLogger


class ReportStage(Enum):
    """报告生成阶段"""
    INITIATED = "initiated"
    DATA_COLLECTED = "data_collected"
    ANALYZED = "analyzed"
    REPORT_GENERATED = "report_generated"
    APPROVED = "approved"


class FinancialReportDemo:
    """财务报告生成演示"""
    
    def __init__(self):
        # 初始化服务
        self.token_service = TokenService(secret_key="advanced_demo_secret_12345")
        self.auth_engine = AuthorizationEngine()
        self.delegation_service = DelegationService(self.token_service)
        self.audit_logger = AuditLogger("advanced_demo_audit_log.jsonl")
        
        # 创建参与者
        self.finance_director = Actor(name="财务总监", type=ActorType.USER, 
                                      attributes={"department": "finance", "role": "director"})
        self.project_manager = Actor(name="项目管理Agent", type=ActorType.MASTER_AGENT,
                                     attributes={"capability": "coordination"})
        self.data_collector = Actor(name="数据收集Agent", type=ActorType.WORKER_AGENT,
                                    attributes={"capability": "data_extraction"})
        self.data_analyst = Actor(name="数据分析Agent", type=ActorType.WORKER_AGENT,
                                  attributes={"capability": "data_analysis"})
        self.report_generator = Actor(name="报告生成Agent", type=ActorType.WORKER_AGENT,
                                      attributes={"capability": "report_generation"})
        self.approver = Actor(name="审批Agent", type=ActorType.WORKER_AGENT,
                              attributes={"capability": "approval"})
        
        # 报告状态
        self.report_state = {
            "stage": ReportStage.INITIATED,
            "data_collected": False,
            "analysis_completed": False,
            "report_generated": False,
            "approved": False,
            "data_sources": [],
            "insights": [],
            "report_content": None
        }
        
        # Token存储
        self.tokens: Dict[str, str] = {}
        self.token_claims: Dict[str, TokenClaims] = {}
        
        # 设置策略
        self._setup_policies()
    
    def _setup_policies(self) -> None:
        """设置复杂的权限策略"""
        # 财务总监策略：全权管理财务数据
        director_policy = self.auth_engine.create_policy_from_template(
            role="finance_director",
            actions=[ActionType.READ, ActionType.WRITE, ActionType.DELETE, ActionType.DELEGATE, ActionType.EXECUTE],
            resources=[ResourceType.FINANCIAL_DATA, ResourceType.USER_DATA],
            conditions={"actor.department": "finance", "actor.role": "director"}
        )
        self.auth_engine.add_policy(director_policy)
        
        # 项目管理Agent策略：可以协调和委托
        manager_policy = self.auth_engine.create_policy_from_template(
            role="project_manager",
            actions=[ActionType.READ, ActionType.DELEGATE, ActionType.EXECUTE],
            resources=[ResourceType.FINANCIAL_DATA],
            conditions={"actor.capability": "coordination"}
        )
        self.auth_engine.add_policy(manager_policy)
        
        # 数据收集Agent策略：只能读取和收集数据
        collector_policy = self.auth_engine.create_policy_from_template(
            role="data_collector",
            actions=[ActionType.READ],
            resources=[ResourceType.FINANCIAL_DATA],
            conditions={"actor.capability": "data_extraction"}
        )
        self.auth_engine.add_policy(collector_policy)
        
        # 数据分析Agent策略：读取和分析数据
        analyst_policy = self.auth_engine.create_policy_from_template(
            role="data_analyst",
            actions=[ActionType.READ, ActionType.EXECUTE],
            resources=[ResourceType.FINANCIAL_DATA],
            conditions={"actor.capability": "data_analysis"}
        )
        self.auth_engine.add_policy(analyst_policy)
        
        # 报告生成Agent策略：读取数据和生成报告
        generator_policy = self.auth_engine.create_policy_from_template(
            role="report_generator",
            actions=[ActionType.READ, ActionType.WRITE],
            resources=[ResourceType.FINANCIAL_DATA],
            conditions={"actor.capability": "report_generation"}
        )
        self.auth_engine.add_policy(generator_policy)
        
        # 审批Agent策略：读取和审批报告
        approver_policy = self.auth_engine.create_policy_from_template(
            role="approver",
            actions=[ActionType.READ, ActionType.EXECUTE],
            resources=[ResourceType.FINANCIAL_DATA],
            conditions={"actor.capability": "approval"}
        )
        self.auth_engine.add_policy(approver_policy)
    
    def print_header(self, title: str) -> None:
        """打印标题"""
        print("\n" + "="*70)
        print(f" {title}")
        print("="*70)
    
    def print_step(self, step: int, description: str) -> None:
        """打印步骤"""
        print(f"\n[{step}] {description}")
    
    def demo_initiate_project(self) -> bool:
        """演示：财务总监初始化项目"""
        self.print_header("阶段1: 财务总监初始化项目")
        
        # 财务总监创建根Token授权给项目管理Agent
        root_claims = TokenClaims(
            sub=self.project_manager.id,
            iss=self.finance_director.id,
            iat=time.time(),
            exp=time.time() + 7200,  # 2小时项目时间
            scopes={
                "read:financial_data",
                "delegate:financial_data", 
                "execute:financial_data"
            },
            max_uses=50,
            context={
                "project": "Q1_financial_report",
                "department": "finance",
                "deadline": time.time() + 7200
            }
        )
        
        root_token = self.token_service.encode(root_claims)
        self.tokens['project_root'] = root_token
        self.token_claims['project_root'] = root_claims
        
        # 记录审计事件
        self.audit_logger.log_event(
            actor_id=self.finance_director.id,
            action="initiate_project",
            resource="Q1_financial_report",
            result="allow",
            details={
                "manager": self.project_manager.name,
                "scopes": list(root_claims.scopes),
                "deadline": "2小时"
            }
        )
        
        print(f"财务总监 {self.finance_director.name} 初始化Q1财务报告项目")
        print(f"授权给: {self.project_manager.name}")
        print(f"项目Token范围: {root_claims.scopes}")
        print(f"项目上下文: {root_claims.context}")
        
        return True
    
    def demo_coordinate_data_collection(self) -> bool:
        """演示：项目管理Agent协调数据收集"""
        self.print_header("阶段2: 项目管理Agent协调数据收集")
        
        project_token = self.tokens.get('project_root')
        if not project_token:
            print("错误: 没有找到项目Token")
            return False
        
        # 项目管理Agent创建委托Token给数据收集Agent
        collector_token = self.delegation_service.create_delegated_token(
            parent_token=project_token,
            child_sub=self.data_collector.id,
            scopes={"read:financial_data"},
            expires_in=1800,  # 30分钟数据收集时间
            max_uses=10,
            context={
                "task": "collect_sales_data",
                "data_sources": ["sales_db", "crm_system"],
                "time_window": "2024-Q1"
            }
        )
        
        if not collector_token:
            print("错误: 创建数据收集Token失败")
            return False
        
        self.tokens['data_collector'] = collector_token
        collector_claims = self.token_service.decode(collector_token)
        self.token_claims['data_collector'] = collector_claims
        
        # 记录审计事件
        self.audit_logger.log_event(
            actor_id=self.project_manager.id,
            action="delegate_data_collection",
            resource="sales_data_2024_q1",
            result="allow",
            details={
                "collector": self.data_collector.name,
                "data_sources": ["sales_db", "crm_system"],
                "expires_in": "30分钟"
            }
        )
        
        print(f"项目管理Agent {self.project_manager.name} 协调数据收集任务")
        print(f"委托给: {self.data_collector.name}")
        print(f"数据收集Token范围: {collector_claims.scopes if collector_claims else 'N/A'}")
        
        # 模拟数据收集过程
        print(f"\n{self.data_collector.name} 正在收集数据...")
        time.sleep(1)
        
        # 检查数据收集权限
        if collector_claims:
            is_authorized = self.auth_engine.evaluate_token_authorization(
                collector_claims, ActionType.READ, ResourceType.FINANCIAL_DATA,
                {"task": "collect_sales_data"}
            )
            
            if is_authorized:
                # 增加Token使用次数
                updated_token = self.token_service.increment_use_count(collector_token)
                if updated_token:
                    self.tokens['data_collector'] = updated_token
                
                # 模拟收集数据
                self.report_state['data_collected'] = True
                self.report_state['data_sources'] = ["sales_db", "crm_system", "erp_system"]
                self.report_state['stage'] = ReportStage.DATA_COLLECTED
                
                # 记录成功事件
                self.audit_logger.log_event(
                    actor_id=self.data_collector.id,
                    action="collect_financial_data",
                    resource="sales_data_2024_q1",
                    result="allow",
                    details={
                        "data_sources": self.report_state['data_sources'],
                        "records_collected": 1500
                    }
                )
                
                print(f"✓ {self.data_collector.name} 成功收集了1500条销售数据")
                print(f"数据来源: {self.report_state['data_sources']}")
                return True
            else:
                # 记录失败事件
                self.audit_logger.log_event(
                    actor_id=self.data_collector.id,
                    action="collect_financial_data",
                    resource="sales_data_2024_q1",
                    result="deny",
                    details={"reason": "insufficient_permissions"}
                )
                print(f"✗ {self.data_collector.name} 没有数据收集权限")
                return False
        
        return False
    
    def demo_data_analysis(self) -> bool:
        """演示：数据分析"""
        self.print_header("阶段3: 数据分析")
        
        if not self.report_state['data_collected']:
            print("错误: 数据尚未收集完成")
            return False
        
        project_token = self.tokens.get('project_root')
        if not project_token:
            print("错误: 没有找到项目Token")
            return False
        
        # 项目管理Agent创建委托Token给数据分析Agent
        analyst_token = self.delegation_service.create_delegated_token(
            parent_token=project_token,
            child_sub=self.data_analyst.id,
            scopes={"read:financial_data", "execute:financial_data"},
            expires_in=2400,  # 40分钟分析时间
            max_uses=15,
            context={
                "task": "analyze_sales_trends",
                "analysis_type": "trend_analysis",
                "metrics": ["revenue", "growth_rate", "customer_acquisition"]
            }
        )
        
        if not analyst_token:
            print("错误: 创建数据分析Token失败")
            return False
        
        self.tokens['data_analyst'] = analyst_token
        analyst_claims = self.token_service.decode(analyst_token)
        self.token_claims['data_analyst'] = analyst_claims
        
        # 记录审计事件
        self.audit_logger.log_event(
            actor_id=self.project_manager.id,
            action="delegate_data_analysis",
            resource="sales_analysis_2024_q1",
            result="allow",
            details={
                "analyst": self.data_analyst.name,
                "analysis_type": "trend_analysis",
                "expires_in": "40分钟"
            }
        )
        
        print(f"项目管理Agent {self.project_manager.name} 委托数据分析任务")
        print(f"委托给: {self.data_analyst.name}")
        
        # 模拟数据分析过程
        print(f"\n{self.data_analyst.name} 正在分析数据...")
        time.sleep(1.5)
        
        if analyst_claims:
            # 检查分析权限
            is_authorized = self.auth_engine.evaluate_token_authorization(
                analyst_claims, ActionType.EXECUTE, ResourceType.FINANCIAL_DATA,
                {"task": "analyze_sales_trends"}
            )
            
            if is_authorized:
                # 增加Token使用次数
                updated_token = self.token_service.increment_use_count(analyst_token)
                if updated_token:
                    self.tokens['data_analyst'] = updated_token
                
                # 模拟分析结果
                self.report_state['analysis_completed'] = True
                self.report_state['insights'] = [
                    "Q1营收同比增长15%",
                    "新客户获取成本降低8%",
                    "毛利率稳定在42%",
                    "移动端销售占比提升至65%"
                ]
                self.report_state['stage'] = ReportStage.ANALYZED
                
                # 记录成功事件
                self.audit_logger.log_event(
                    actor_id=self.data_analyst.id,
                    action="analyze_financial_data",
                    resource="sales_analysis_2024_q1",
                    result="allow",
                    details={
                        "insights_generated": len(self.report_state['insights']),
                        "processing_time": "1.5秒"
                    }
                )
                
                print(f"✓ {self.data_analyst.name} 完成数据分析")
                print("关键洞察:")
                for i, insight in enumerate(self.report_state['insights'], 1):
                    print(f"  {i}. {insight}")
                return True
            else:
                # 记录失败事件
                self.audit_logger.log_event(
                    actor_id=self.data_analyst.id,
                    action="analyze_financial_data",
                    resource="sales_analysis_2024_q1",
                    result="deny",
                    details={"reason": "insufficient_permissions"}
                )
                print(f"✗ {self.data_analyst.name} 没有数据分析权限")
                return False
        
        return False
    
    def demo_report_generation(self) -> bool:
        """演示：报告生成"""
        self.print_header("阶段4: 报告生成")
        
        if not self.report_state['analysis_completed']:
            print("错误: 数据分析尚未完成")
            return False
        
        project_token = self.tokens.get('project_root')
        if not project_token:
            print("错误: 没有找到项目Token")
            return False
        
        # 项目管理Agent创建委托Token给报告生成Agent
        generator_token = self.delegation_service.create_delegated_token(
            parent_token=project_token,
            child_sub=self.report_generator.id,
            scopes={"read:financial_data", "write:financial_data"},
            expires_in=1800,  # 30分钟报告生成时间
            max_uses=5,
            context={
                "task": "generate_financial_report",
                "report_type": "quarterly_summary",
                "template": "standard_financial_template"
            }
        )
        
        if not generator_token:
            print("错误: 创建报告生成Token失败")
            return False
        
        self.tokens['report_generator'] = generator_token
        generator_claims = self.token_service.decode(generator_token)
        self.token_claims['report_generator'] = generator_claims
        
        # 记录审计事件
        self.audit_logger.log_event(
            actor_id=self.project_manager.id,
            action="delegate_report_generation",
            resource="financial_report_2024_q1",
            result="allow",
            details={
                "generator": self.report_generator.name,
                "report_type": "quarterly_summary",
                "expires_in": "30分钟"
            }
        )
        
        print(f"项目管理Agent {self.project_manager.name} 委托报告生成任务")
        print(f"委托给: {self.report_generator.name}")
        
        # 模拟报告生成过程
        print(f"\n{self.report_generator.name} 正在生成报告...")
        time.sleep(1.2)
        
        if generator_claims:
            # 检查报告生成权限
            is_authorized = self.auth_engine.evaluate_token_authorization(
                generator_claims, ActionType.WRITE, ResourceType.FINANCIAL_DATA,
                {"task": "generate_financial_report"}
            )
            
            if is_authorized:
                # 增加Token使用次数
                updated_token = self.token_service.increment_use_count(generator_token)
                if updated_token:
                    self.tokens['report_generator'] = updated_token
                
                # 模拟报告生成
                self.report_state['report_generated'] = True
                self.report_state['report_content'] = {
                    "title": "2024年第一季度财务报告",
                    "period": "2024年1月-3月",
                    "summary": "本季度表现良好，营收增长符合预期。",
                    "key_metrics": {
                        "revenue": "¥15,800,000",
                        "growth_rate": "15%",
                        "profit_margin": "42%",
                        "new_customers": "2,450"
                    },
                    "recommendations": [
                        "加大移动端营销投入",
                        "优化供应链成本",
                        "拓展国际市场"
                    ]
                }
                self.report_state['stage'] = ReportStage.REPORT_GENERATED
                
                # 记录成功事件
                self.audit_logger.log_event(
                    actor_id=self.report_generator.id,
                    action="generate_financial_report",
                    resource="financial_report_2024_q1",
                    result="allow",
                    details={
                        "report_length": "12页",
                        "sections": 6
                    }
                )
                
                print(f"✓ {self.report_generator.name} 完成报告生成")
                print(f"报告标题: {self.report_state['report_content']['title']}")
                print("关键指标:")
                for metric, value in self.report_state['report_content']['key_metrics'].items():
                    print(f"  {metric}: {value}")
                return True
            else:
                # 记录失败事件
                self.audit_logger.log_event(
                    actor_id=self.report_generator.id,
                    action="generate_financial_report",
                    resource="financial_report_2024_q1",
                    result="deny",
                    details={"reason": "insufficient_permissions"}
                )
                print(f"✗ {self.report_generator.name} 没有报告生成权限")
                return False
        
        return False
    
    def demo_report_approval(self) -> bool:
        """演示：报告审批"""
        self.print_header("阶段5: 报告审批")
        
        if not self.report_state['report_generated']:
            print("错误: 报告尚未生成")
            return False
        
        project_token = self.tokens.get('project_root')
        if not project_token:
            print("错误: 没有找到项目Token")
            return False
        
        # 项目管理Agent创建委托Token给审批Agent
        approver_token = self.delegation_service.create_delegated_token(
            parent_token=project_token,
            child_sub=self.approver.id,
            scopes={"read:financial_data", "execute:financial_data"},
            expires_in=900,  # 15分钟审批时间
            max_uses=3,
            context={
                "task": "approve_financial_report",
                "approval_level": "director",
                "required_signatures": 1
            }
        )
        
        if not approver_token:
            print("错误: 创建审批Token失败")
            return False
        
        self.tokens['approver'] = approver_token
        approver_claims = self.token_service.decode(approver_token)
        self.token_claims['approver'] = approver_claims
        
        # 记录审计事件
        self.audit_logger.log_event(
            actor_id=self.project_manager.id,
            action="delegate_report_approval",
            resource="financial_report_approval_2024_q1",
            result="allow",
            details={
                "approver": self.approver.name,
                "approval_level": "director",
                "expires_in": "15分钟"
            }
        )
        
        print(f"项目管理Agent {self.project_manager.name} 委托报告审批任务")
        print(f"委托给: {self.approver.name}")
        
        # 模拟审批过程
        print(f"\n{self.approver.name} 正在审批报告...")
        time.sleep(1)
        
        if approver_claims:
            # 检查审批权限
            is_authorized = self.auth_engine.evaluate_token_authorization(
                approver_claims, ActionType.EXECUTE, ResourceType.FINANCIAL_DATA,
                {"task": "approve_financial_report"}
            )
            
            if is_authorized:
                # 增加Token使用次数
                updated_token = self.token_service.increment_use_count(approver_token)
                if updated_token:
                    self.tokens['approver'] = updated_token
                
                # 模拟审批通过
                self.report_state['approved'] = True
                self.report_state['stage'] = ReportStage.APPROVED
                
                # 记录成功事件
                self.audit_logger.log_event(
                    actor_id=self.approver.id,
                    action="approve_financial_report",
                    resource="financial_report_2024_q1",
                    result="allow",
                    details={
                        "approval_status": "approved",
                        "approval_notes": "报告内容准确，建议采纳"
                    }
                )
                
                print(f"✓ {self.approver.name} 批准了财务报告")
                print(f"审批意见: 报告内容准确，建议采纳")
                return True
            else:
                # 记录失败事件
                self.audit_logger.log_event(
                    actor_id=self.approver.id,
                    action="approve_financial_report",
                    resource="financial_report_2024_q1",
                    result="deny",
                    details={"reason": "insufficient_permissions"}
                )
                print(f"✗ {self.approver.name} 没有报告审批权限")
                return False
        
        return False
    
    def demo_audit_trail(self) -> bool:
        """演示：审计追踪"""
        self.print_header("阶段6: 完整审计追踪")
        
        # 验证审计日志完整性
        integrity_ok = self.audit_logger.verify_integrity()
        
        if not integrity_ok:
            print("错误: 审计日志完整性验证失败")
            return False
        
        # 加载审计事件
        events = self.audit_logger.load_events()
        
        print(f"项目共产生 {len(events)} 个审计事件")
        print("\n完整委托链:")
        
        # 显示Token委托链
        for token_name, token in self.tokens.items():
            if token_name != 'project_root':
                claims = self.token_claims.get(token_name)
                if claims and claims.parent_token:
                    print(f"  {token_name}: {claims.sub} ← {claims.iss}")
        
        print("\n关键审计事件时间线:")
        for event in events[-10:]:  # 显示最近10个事件
            timestamp = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
            print(f"  [{timestamp}] {event.actor_id} {event.action} → {event.result}")
        
        print("\n项目状态总结:")
        print(f"  当前阶段: {self.report_state['stage'].value}")
        print(f"  数据收集: {'✓' if self.report_state['data_collected'] else '✗'}")
        print(f"  数据分析: {'✓' if self.report_state['analysis_completed'] else '✗'}")
        print(f"  报告生成: {'✓' if self.report_state['report_generated'] else '✗'}")
        print(f"  报告审批: {'✓' if self.report_state['approved'] else '✗'}")
        
        return True
    
    def demo_unauthorized_access_attempt(self) -> bool:
        """演示：未授权访问尝试"""
        self.print_header("安全演示: 未授权访问尝试")
        
        # 尝试让数据收集Agent执行它没有权限的操作
        collector_token = self.tokens.get('data_collector')
        if not collector_token:
            print("错误: 没有找到数据收集Token")
            return False
        
        collector_claims = self.token_claims.get('data_collector')
        if not collector_claims:
            print("错误: 没有找到数据收集Token声明")
            return False
        
        print(f"尝试: {self.data_collector.name} 试图修改财务数据...")
        
        # 检查写入权限（应该被拒绝）
        is_authorized = self.auth_engine.evaluate_token_authorization(
            collector_claims, ActionType.WRITE, ResourceType.FINANCIAL_DATA,
            {"task": "modify_sales_data"}
        )
        
        if not is_authorized:
            # 记录拒绝事件
            self.audit_logger.log_event(
                actor_id=self.data_collector.id,
                action="unauthorized_write_attempt",
                resource="financial_data",
                result="deny",
                details={
                    "reason": "collector_token_has_no_write_permission",
                    "attempted_action": "write",
                    "token_scopes": list(collector_claims.scopes)
                }
            )
            
            print(f"✓ 安全系统成功拦截未授权写入尝试")
            print(f"  原因: Token只有读取权限，没有写入权限")
            print(f"  Token范围: {collector_claims.scopes}")
            return True
        else:
            print(f"✗ 安全漏洞: 不应该有写入权限")
            return False
    
    def demo_token_expiration(self) -> bool:
        """演示：Token过期"""
        self.print_header("安全演示: Token过期")
        
        # 创建一个立即过期的Token
        expired_claims = TokenClaims(
            sub=self.data_collector.id,
            iss=self.project_manager.id,
            iat=time.time() - 3600,  # 1小时前签发
            exp=time.time() - 1800,  # 30分钟前过期
            scopes={"read:financial_data"}
        )
        
        expired_token = self.token_service.encode(expired_claims)
        
        print(f"使用过期Token尝试访问数据...")
        
        # 验证Token（应该失败）
        is_valid = self.token_service.validate_token(expired_token)
        
        if not is_valid:
            # 记录过期事件
            self.audit_logger.log_event(
                actor_id=self.data_collector.id,
                action="access_with_expired_token",
                resource="financial_data",
                result="deny",
                details={"reason": "token_expired"}
            )
            
            print(f"✓ 安全系统成功拦截过期Token访问")
            print(f"  原因: Token已过期")
            return True
        else:
            print(f"✗ 安全漏洞: 过期Token不应该有效")
            return False
    
    def run_full_demo(self) -> bool:
        """运行完整演示"""
        print("="*70)
        print("         AI Agent IAM 高级演示: 财务报告生成流水线")
        print("="*70)
        
        steps = [
            ("项目初始化", self.demo_initiate_project),
            ("数据收集协调", self.demo_coordinate_data_collection),
            ("数据分析", self.demo_data_analysis),
            ("报告生成", self.demo_report_generation),
            ("报告审批", self.demo_report_approval),
            ("未授权访问拦截", self.demo_unauthorized_access_attempt),
            ("Token过期拦截", self.demo_token_expiration),
            ("审计追踪", self.demo_audit_trail),
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
            print("\n" + "="*70)
            print("          财务报告生成流水线演示完成!")
            print("="*70)
            print("\n项目成果:")
            if self.report_state['report_content']:
                content = self.report_state['report_content']
                print(f"  报告标题: {content['title']}")
                print(f"  报告期间: {content['period']}")
                print(f"  总结: {content['summary']}")
        else:
            print("\n" + "="*70)
            print("          演示过程中出现错误")
            print("="*70)
        
        return all_passed


if __name__ == "__main__":
    demo = FinancialReportDemo()
    demo.run_full_demo()