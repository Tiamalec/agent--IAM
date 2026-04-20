"""
飞书AI Agent集成演示
展示AI Agent IAM系统与飞书lark-cli的集成
"""
import time
import json
from typing import Dict, List

from agent_iam.models import Actor, ActorType, TokenClaims
from agent_iam.token_service import TokenService
from agent_iam.auth_engine import AuthorizationEngine
from agent_iam.delegation import DelegationService
from agent_iam.audit_logger import AuditLogger
from agent_iam.feishu_integration import (
    FeishuIntegration, FeishuSkill, FeishuAgent,
    FeishuAction, FeishuResource
)


class FeishuIntegrationDemo:
    """飞书集成演示"""
    
    def __init__(self):
        # 初始化IAM服务
        self.token_service = TokenService(secret_key="feishu_demo_secret")
        self.auth_engine = AuthorizationEngine()
        self.delegation_service = DelegationService(self.token_service)
        self.audit_logger = AuditLogger("feishu_demo_audit.jsonl")
        
        # 初始化飞书集成
        self.feishu_integration = FeishuIntegration()
        
        # 创建参与者
        self.admin = Actor(name="企业管理员", type=ActorType.USER,
                          attributes={"department": "it", "role": "admin"})
        
        # 创建飞书AI Agents
        self.calendar_agent = FeishuAgent(
            name="智能日程助手",
            agent_type=ActorType.MASTER_AGENT,
            feishu_app_id="feishu_app_calendar_001",
            feishu_skills=[FeishuSkill.CALENDAR]
        )
        
        self.message_agent = FeishuAgent(
            name="智能消息助手", 
            agent_type=ActorType.WORKER_AGENT,
            feishu_app_id="feishu_app_im_001",
            feishu_skills=[FeishuSkill.IM]
        )
        
        self.document_agent = FeishuAgent(
            name="智能文档助手",
            agent_type=ActorType.WORKER_AGENT,
            feishu_app_id="feishu_app_doc_001",
            feishu_skills=[FeishuSkill.DOC]
        )
        
        self.task_agent = FeishuAgent(
            name="智能任务助手",
            agent_type=ActorType.WORKER_AGENT,
            feishu_app_id="feishu_app_task_001",
            feishu_skills=[FeishuSkill.TASK]
        )
        
        # Token存储
        self.tokens: Dict[str, str] = {}
        
        # 设置策略
        self._setup_policies()
    
    def print_header(self, title: str, emoji: str = "🚀") -> None:
        """打印标题"""
        print(f"\n{emoji} " + "="*70)
        print(f"  {title}")
        print("="*70)
    
    def _setup_policies(self) -> None:
        """设置飞书集成策略"""
        print("设置飞书集成策略...")
        
        # 列出所有可用的飞书Skills
        available_skills = self.feishu_integration.list_available_skills()
        print(f"发现 {len(available_skills)} 个飞书Skills:")
        
        for skill_info in available_skills[:5]:  # 显示前5个
            print(f"  • {skill_info['skill']}: {skill_info['description']}")
        
        if len(available_skills) > 5:
            print(f"  ... 还有 {len(available_skills) - 5} 个Skills")
    
    def demo_feishu_skill_registration(self) -> bool:
        """演示：飞书Skill注册和授权"""
        self.print_header("阶段1: 飞书Skill注册和授权", "🔐")
        
        print("场景: 企业管理员为AI Agent注册飞书Skills")
        print("-"*50)
        
        # 管理员创建根Token
        root_claims = TokenClaims(
            sub=self.calendar_agent.id,
            iss=self.admin.id,
            iat=time.time(),
            exp=time.time() + 7200,
            scopes={
                "manage:feishu_skills",
                "delegate:feishu_skills",
                "execute:feishu_calendar"
            },
            max_uses=100,
            context={
                "platform": "feishu",
                "integration_type": "skill_registration"
            }
        )
        
        root_token = self.token_service.encode(root_claims)
        self.tokens['admin_root'] = root_token
        
        print(f"✅ 企业管理员创建根Token")
        print(f"   授权给: {self.calendar_agent.name}")
        print(f"   权限范围: {root_claims.scopes}")
        
        # 注册飞书Skills
        print(f"\n📋 注册飞书Skills:")
        
        agents = [self.calendar_agent, self.message_agent, self.document_agent, self.task_agent]
        for agent in agents:
            skill_tokens = self.feishu_integration.register_feishu_agent(
                agent, agent.feishu_skills
            )
            
            for skill_name, token in skill_tokens.items():
                agent.set_skill_token(FeishuSkill(skill_name), token)
                print(f"  ✅ {agent.name} 注册 {skill_name} Skill")
                print(f"      Token: {token[:30]}...")
        
        # 记录审计事件
        self.audit_logger.log_event(
            actor_id=self.admin.id,
            action="register_feishu_skills",
            resource="feishu_integration",
            result="allow",
            details={
                "agents_registered": len(agents),
                "total_skills": sum(len(a.feishu_skills) for a in agents),
                "platform": "feishu"
            }
        )
        
        return True
    
    def demo_calendar_agent_workflow(self) -> bool:
        """演示：日历Agent工作流"""
        self.print_header("阶段2: 日历Agent智能工作流", "📅")
        
        print("场景: 智能日程助手自动安排团队会议")
        print("-"*50)
        
        # 获取日历Agent的Skill Token
        calendar_token = self.calendar_agent.get_skill_token(FeishuSkill.CALENDAR)
        if not calendar_token:
            print("❌ 错误: 日历Agent没有有效的Skill Token")
            return False
        
        print(f"📅 {self.calendar_agent.name} 开始工作...")
        
        # 1. 查看今日日程
        print(f"\n1️⃣ 查看今日日程:")
        command_result = self.feishu_integration.execute_feishu_command(
            calendar_token,
            "calendar agenda",
            {"date": "today"}
        )
        
        if command_result.get("success"):
            events = command_result.get("result", {}).get("events", [])
            print(f"   ✅ 获取到 {len(events)} 个日程事件")
            for event in events[:3]:
                print(f"      • {event.get('title')} ({event.get('time')})")
        else:
            print(f"   ❌ 失败: {command_result.get('error')}")
        
        # 2. 创建新会议
        print(f"\n2️⃣ 创建团队周会:")
        create_result = self.feishu_integration.execute_feishu_command(
            calendar_token,
            "calendar create",
            {
                "title": "AI项目组周会",
                "time": "2026-04-16 10:00-11:30",
                "location": "会议室A",
                "attendees": ["team@company.com"]
            }
        )
        
        if create_result.get("success"):
            meeting_info = create_result.get("result", {})
            print(f"   ✅ 成功创建会议")
            print(f"      会议ID: {meeting_info.get('meeting_id', 'N/A')}")
            print(f"      时间: {meeting_info.get('time', 'N/A')}")
            print(f"      地点: {meeting_info.get('location', 'N/A')}")
        else:
            print(f"   ❌ 失败: {create_result.get('error')}")
        
        # 记录审计
        self.audit_logger.log_event(
            actor_id=str(self.calendar_agent.id),
            action="feishu_calendar_workflow",
            resource="calendar_scheduling",
            result="allow",
            details={
                "agent": str(self.calendar_agent.name),
                "actions_performed": ["view_agenda", "create_meeting"],
                "meeting_created": create_result.get("success", False)
            }
        )
        
        return True
    
    def demo_multi_agent_collaboration(self) -> bool:
        """演示：多Agent飞书协作"""
        self.print_header("阶段3: 多Agent飞书协作", "🤝")
        
        print("场景: 多个AI Agent协作完成项目任务")
        print("-"*50)
        
        print("项目任务: 准备季度业务评审会议")
        print("涉及Agent: 日历助手 + 消息助手 + 文档助手 + 任务助手")
        
        workflow_steps = [
            {
                "agent": self.calendar_agent,
                "skill": FeishuSkill.CALENDAR,
                "action": "安排会议时间",
                "command": "calendar schedule",
                "params": {"title": "Q2业务评审", "duration": "2小时"}
            },
            {
                "agent": self.message_agent,
                "skill": FeishuSkill.IM,
                "action": "发送会议通知",
                "command": "im send",
                "params": {"to": "project_team", "content": "Q2评审会议已安排"}
            },
            {
                "agent": self.document_agent,
                "skill": FeishuSkill.DOC,
                "action": "创建评审文档",
                "command": "doc create",
                "params": {"title": "Q2业务评审材料", "template": "review"}
            },
            {
                "agent": self.task_agent,
                "skill": FeishuSkill.TASK,
                "action": "分配准备任务",
                "command": "task create",
                "params": {"title": "准备评审数据", "assignee": "data_team"}
            }
        ]
        
        all_success = True
        for step in workflow_steps:
            agent = step["agent"]
            skill = step["skill"]
            action = step["action"]
            
            print(f"\n🔧 {agent.name} {action}:")
            
            # 获取Skill Token
            token = agent.get_skill_token(skill)
            if not token:
                print(f"   ❌ 错误: {agent.name} 没有 {skill.value} Token")
                all_success = False
                continue
            
            # 执行命令
            result = self.feishu_integration.execute_feishu_command(
                token, step["command"], step["params"]
            )
            
            if result.get("success"):
                print(f"   ✅ 成功")
                if result.get("result"):
                    result_data = result["result"]
                    if isinstance(result_data, dict):
                        for key, value in result_data.items():
                            if key not in ["success", "error"]:
                                print(f"      {key}: {value}")
            else:
                print(f"   ❌ 失败: {result.get('error')}")
                all_success = False
            
            # 短暂暂停
            time.sleep(0.5)
        
        # 记录审计
        self.audit_logger.log_event(
            actor_id="multi_agent_system",
            action="feishu_multi_agent_collaboration",
            resource="project_review_workflow",
            result="allow" if all_success else "partial",
            details={
                "agents_involved": len(workflow_steps),
                "steps_completed": sum(1 for step in workflow_steps if True),
                "workflow": "quarterly_business_review"
            }
        )
        
        return all_success
    
    def demo_permission_control(self) -> bool:
        """演示：精细权限控制"""
        self.print_header("阶段4: 精细权限控制", "🛡️")
        
        print("场景: 演示飞书Skills的细粒度权限控制")
        print("-"*50)
        
        test_cases = [
            {
                "agent": self.message_agent,
                "skill": FeishuSkill.IM,
                "action": "send",
                "resource": "message",
                "should_allow": True,
                "description": "消息助手发送消息"
            },
            {
                "agent": self.calendar_agent,
                "skill": FeishuSkill.IM,
                "action": "send",
                "resource": "message",
                "should_allow": False,
                "description": "日历助手尝试发送消息（无权限）"
            },
            {
                "agent": self.document_agent,
                "skill": FeishuSkill.DOC,
                "action": "create",
                "resource": "document",
                "should_allow": True,
                "description": "文档助手创建文档"
            },
            {
                "agent": self.task_agent,
                "skill": FeishuSkill.DOC,
                "action": "create",
                "resource": "document",
                "should_allow": False,
                "description": "任务助手尝试创建文档（无权限）"
            },
            {
                "agent": self.calendar_agent,
                "skill": FeishuSkill.CALENDAR,
                "action": "read",
                "resource": "calendar",
                "should_allow": True,
                "description": "日历助手查看日历"
            },
            {
                "agent": self.calendar_agent,
                "skill": FeishuSkill.CALENDAR,
                "action": "manage",
                "resource": "tenant",
                "should_allow": False,
                "description": "日历助手尝试管理租户（越权）"
            }
        ]
        
        passed_tests = 0
        total_tests = len(test_cases)
        
        for i, test in enumerate(test_cases, 1):
            agent = test["agent"]
            skill = test["skill"]
            
            print(f"\n{i}. {test['description']}:")
            
            # 获取Skill Token
            token = agent.get_skill_token(skill)
            if not token:
                print(f"   ❌ 没有Token - {'符合预期' if not test['should_allow'] else '不符合预期'}")
                if not test['should_allow']:
                    passed_tests += 1
                continue
            
            # 验证权限
            has_permission = self.feishu_integration.validate_skill_token(
                token, test["action"], test["resource"]
            )
            
            expected = "允许" if test["should_allow"] else "拒绝"
            actual = "允许" if has_permission else "拒绝"
            
            if (has_permission == test["should_allow"]):
                print(f"   ✅ {actual} (符合预期: {expected})")
                passed_tests += 1
            else:
                print(f"   ❌ {actual} (不符合预期: {expected})")
        
        # 记录审计
        self.audit_logger.log_event(
            actor_id="permission_system",
            action="feishu_permission_test",
            resource="access_control",
            result="allow",
            details={
                "tests_total": total_tests,
                "tests_passed": passed_tests,
                "success_rate": f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%"
            }
        )
        
        print(f"\n📊 权限测试结果: {passed_tests}/{total_tests} 通过")
        
        return passed_tests == total_tests
    
    def demo_audit_and_compliance(self) -> bool:
        """演示：审计和合规性"""
        self.print_header("阶段5: 审计和合规性", "📝")
        
        print("场景: 展示飞书集成的完整审计追踪")
        print("-"*50)
        
        # 加载审计事件
        events = self.audit_logger.load_events()
        
        print(f"📊 审计统计:")
        print(f"  总事件数: {len(events)}")
        
        # 按类型统计
        feishu_events = [e for e in events if "feishu" in e.action or "feishu" in e.resource]
        print(f"  飞书相关事件: {len(feishu_events)}")
        
        # 按结果统计
        allow_events = [e for e in feishu_events if e.result == "allow"]
        deny_events = [e for e in feishu_events if e.result == "deny"]
        print(f"  允许操作: {len(allow_events)}")
        print(f"  拒绝操作: {len(deny_events)}")
        
        # 按Agent统计
        agent_actions = {}
        for event in feishu_events:
            agent_actions[event.actor_id] = agent_actions.get(event.actor_id, 0) + 1
        
        print(f"\n👥 Agent活动统计:")
        for agent_id, count in agent_actions.items():
            agent_name = "未知"
            if agent_id == self.admin.id:
                agent_name = "企业管理员"
            elif agent_id == self.calendar_agent.id:
                agent_name = "智能日程助手"
            elif agent_id == self.message_agent.id:
                agent_name = "智能消息助手"
            elif agent_id == self.document_agent.id:
                agent_name = "智能文档助手"
            elif agent_id == self.task_agent.id:
                agent_name = "智能任务助手"
            
            print(f"  {agent_name}: {count} 次操作")
        
        # 完整性验证
        integrity_ok = self.audit_logger.verify_integrity()
        print(f"\n🔒 审计日志完整性: {'✅ 通过' if integrity_ok else '❌ 失败'}")
        
        # 显示最近事件
        print(f"\n⏰ 最近飞书操作:")
        recent_feishu_events = feishu_events[-5:] if len(feishu_events) >= 5 else feishu_events
        for event in recent_feishu_events:
            timestamp = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
            print(f"  [{timestamp}] {event.actor_id} {event.action} → {event.result}")
        
        return integrity_ok
    
    def demo_integration_overview(self) -> bool:
        """演示：集成概览"""
        self.print_header("阶段6: 飞书集成概览", "🏆")
        
        print("🎯 集成架构:")
        print("  企业管理员 → IAM系统 → 飞书AI Agents → 飞书lark-cli → 飞书业务数据")
        print("")
        print("🔧 核心集成点:")
        print("  1. Skill-based权限映射: IAM权限 ↔ 飞书Skills")
        print("  2. Token委托链: 管理员Token → Agent Token → Skill Token")
        print("  3. 统一审计: 所有飞书操作记录到IAM审计日志")
        print("  4. 细粒度控制: 基于Skill、Action、Resource的三层权限控制")
        print("")
        print("🚀 业务价值:")
        print("  • 安全可控的AI Agent飞书操作")
        print("  • 统一的权限管理和审计追踪")
        print("  • 支持复杂的多Agent协作工作流")
        print("  • 符合企业安全合规要求")
        print("")
        print("📊 演示成果:")
        
        # 统计信息
        agents = [self.calendar_agent, self.message_agent, self.document_agent, self.task_agent]
        total_skills = sum(len(agent.feishu_skills) for agent in agents)
        
        events = self.audit_logger.load_events()
        feishu_events = [e for e in events if "feishu" in e.action or "feishu" in e.resource]
        
        print(f"  • 注册AI Agents: {len(agents)}")
        print(f"  • 分配飞书Skills: {total_skills}")
        print(f"  • 生成审计事件: {len(feishu_events)}")
        print(f"  • 完整性验证: {'通过' if self.audit_logger.verify_integrity() else '失败'}")
        
        return True
    
    def run_full_demo(self) -> bool:
        """运行完整演示"""
        print("="*70)
        print("        🏆 AI Agent IAM × 飞书集成演示")
        print("="*70)
        print("          安全、可控的飞书AI Agent协作平台")
        print("="*70)
        
        demo_steps = [
            ("飞书Skill注册和授权", self.demo_feishu_skill_registration),
            ("日历Agent智能工作流", self.demo_calendar_agent_workflow),
            ("多Agent飞书协作", self.demo_multi_agent_collaboration),
            ("精细权限控制", self.demo_permission_control),
            ("审计和合规性", self.demo_audit_and_compliance),
            ("集成概览", self.demo_integration_overview),
        ]
        
        print(f"\n📋 演示计划 ({len(demo_steps)}个阶段):")
        for i, (name, _) in enumerate(demo_steps, 1):
            print(f"  {i}. {name}")
        
        input("\n按Enter键开始演示...")
        
        results = {}
        for step_name, step_func in demo_steps:
            print(f"\n>>> 开始阶段: {step_name}")
            try:
                success = step_func()
                results[step_name] = success
                print(f"✅ {step_name}: {'成功' if success else '失败'}")
                time.sleep(1)
            except Exception as e:
                print(f"❌ {step_name} 出错: {e}")
                results[step_name] = False
        
        # 演示总结
        success_count = sum(1 for r in results.values() if r)
        total_count = len(results)
        
        print(f"\n" + "="*70)
        print(f"                    演示完成!")
        print("="*70)
        print(f"📊 结果统计: {success_count}/{total_count} 个阶段演示成功")
        print(f"🎯 成功率: {(success_count/total_count*100):.1f}%")
        
        if success_count == total_count:
            print(f"🏆 所有阶段演示成功!")
        else:
            print(f"⚠️  部分阶段演示失败")
        
        print("="*70)
        
        return success_count == total_count


if __name__ == "__main__":
    demo = FeishuIntegrationDemo()
    success = demo.run_full_demo()
    
    if success:
        print("\n🎉 飞书集成演示成功完成！")
        print("💡 下一步:")
        print("  • 查看完整代码: agent_iam/feishu_integration.py")
        print("  • 运行原始演示: python competition_demo.py")
        print("  • 体验可视化: streamlit run streamlit_app.py")
        print("  • 实际集成飞书lark-cli需要配置真实飞书应用凭证")
    else:
        print("\n❌ 演示过程中出现问题。")
    
    exit(0 if success else 1)