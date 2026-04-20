"""
Streamlit可视化界面：AI Agent IAM系统监控
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import time
import json
from datetime import datetime
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 设置页面配置
st.set_page_config(
    page_title="AI Agent IAM 监控面板",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 导入IAM模块
try:
    from agent_iam.models import Actor, ActorType, ActionType, ResourceType, TokenClaims
    from agent_iam.token_service import TokenService
    from agent_iam.auth_engine import AuthorizationEngine
    from agent_iam.delegation import DelegationService
    from agent_iam.audit_logger import AuditLogger
    from agent_iam.advanced_demo import FinancialReportDemo
    from agent_iam.feishu_integration import FeishuIntegration, FeishuSkill, FeishuAction, FeishuResource
    from agent_iam.feishu_org_sync import FeishuOrgSyncService, SyncConfig
    IAM_AVAILABLE = True
    FEISHU_AVAILABLE = True
except ImportError as e:
    st.error(f"导入IAM模块失败: {e}")
    IAM_AVAILABLE = False
    FEISHU_AVAILABLE = False

# 标题
st.title("🔐 AI Agent IAM 系统监控面板")
st.markdown("---")

if not IAM_AVAILABLE:
    st.warning("IAM模块不可用。请确保已安装所有依赖并正确设置Python路径。")
    st.stop()

# 初始化会话状态
if 'demo' not in st.session_state:
    st.session_state.demo = FinancialReportDemo()
    st.session_state.audit_events = []
    st.session_state.demo_running = False
    st.session_state.demo_results = {}
    
    # 飞书集成初始化
    if FEISHU_AVAILABLE:
        st.session_state.feishu_integration = FeishuIntegration()
        st.session_state.feishu_sync = FeishuOrgSyncService()
        st.session_state.feishu_skills = []
        st.session_state.feishu_sync_stats = None

# 侧边栏
with st.sidebar:
    st.header("控制面板")
    
    if st.button("🚀 运行完整演示", type="primary", use_container_width=True):
        st.session_state.demo_running = True
        st.rerun()
    
    if st.button("🔄 重置演示", use_container_width=True):
        st.session_state.demo = FinancialReportDemo()
        st.session_state.audit_events = []
        st.session_state.demo_running = False
        st.session_state.demo_results = {}
        st.rerun()
    
    st.markdown("---")
    
    # 飞书集成控制
    if FEISHU_AVAILABLE:
        st.header("飞书集成")
        
        # 飞书技能管理
        st.subheader("技能管理")
        available_skills = st.session_state.feishu_integration.list_available_skills()
        selected_skill = st.selectbox(
            "选择飞书技能",
            [skill["skill"] for skill in available_skills],
            index=0
        )
        
        if st.button("📋 查看技能详情", use_container_width=True):
            for skill in available_skills:
                if skill["skill"] == selected_skill:
                    st.json(skill)
        
        # 组织架构同步
        st.subheader("组织架构同步")
        if st.button("🔄 执行全量同步", use_container_width=True):
            with st.spinner("正在同步飞书组织架构..."):
                stats = st.session_state.feishu_sync.sync_full_organization()
                st.session_state.feishu_sync_stats = stats.to_dict()
                st.success(f"同步完成！成功: {stats.success_rate:.2f}%")
        
        if st.button("⚡ 执行增量同步", use_container_width=True):
            with st.spinner("正在增量同步飞书组织架构..."):
                stats = st.session_state.feishu_sync.sync_incremental()
                st.session_state.feishu_sync_stats = stats.to_dict()
                st.success(f"增量同步完成！成功: {stats.success_rate:.2f}%")
    
    st.markdown("---")
    st.header("监控选项")
    
    auto_refresh = st.checkbox("🔄 自动刷新", value=True)
    refresh_interval = st.slider("刷新间隔(秒)", 1, 30, 5)
    
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

# 如果演示正在运行，显示进度
if st.session_state.demo_running:
    with st.status("正在运行财务报告生成演示...", expanded=True) as status:
        # 运行演示步骤
        steps = [
            ("项目初始化", st.session_state.demo.demo_initiate_project),
            ("数据收集协调", st.session_state.demo.demo_coordinate_data_collection),
            ("数据分析", st.session_state.demo.demo_data_analysis),
            ("报告生成", st.session_state.demo.demo_report_generation),
            ("报告审批", st.session_state.demo.demo_report_approval),
            ("未授权访问拦截", st.session_state.demo.demo_unauthorized_access_attempt),
            ("Token过期拦截", st.session_state.demo.demo_token_expiration),
            ("审计追踪", st.session_state.demo.demo_audit_trail),
        ]
        
        results = {}
        for step_name, step_func in steps:
            st.write(f"执行: {step_name}...")
            try:
                success = step_func()
                results[step_name] = success
                if success:
                    st.write(f"✓ {step_name} 成功")
                else:
                    st.write(f"✗ {step_name} 失败")
            except Exception as e:
                st.write(f"✗ {step_name} 出错: {e}")
                results[step_name] = False
        
        status.update(label="演示完成!", state="complete")
        st.session_state.demo_results = results
        st.session_state.demo_running = False
        st.session_state.audit_events = st.session_state.demo.audit_logger.load_events()

# 主内容区域
if FEISHU_AVAILABLE:
    # 飞书集成状态
    st.markdown("---")
    st.header("📱 飞书集成状态")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("技能管理")
        available_skills = st.session_state.feishu_integration.list_available_skills()
        st.metric("可用技能数", len(available_skills))
        
        # 技能列表
        if available_skills:
            skill_names = [skill["skill"] for skill in available_skills]
            selected_skill = st.selectbox("选择技能查看详情", skill_names)
            for skill in available_skills:
                if skill["skill"] == selected_skill:
                    st.json(skill)
        else:
            st.info("暂无可用技能")
    
    with col2:
        st.subheader("组织架构同步")
        sync_status = st.session_state.feishu_sync.get_sync_status()
        st.metric("部门数量", sync_status.get("department_count", 0))
        st.metric("用户数量", sync_status.get("user_count", 0))
        
        # 同步状态
        if st.session_state.feishu_sync_stats:
            st.json(st.session_state.feishu_sync_stats)
        else:
            st.info("请执行同步操作")

# 主内容区域
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📊 Agent关系图")
    
    # 创建Agent关系图
    if hasattr(st.session_state.demo, 'actors'):
        actors = st.session_state.demo.__dict__
        actor_list = [v for k, v in actors.items() if isinstance(v, Actor)]
        
        # 创建关系数据
        edges = []
        nodes = []
        
        for actor in actor_list:
            nodes.append({
                "id": actor.id[:8],
                "label": actor.name,
                "type": actor.type.value,
                "size": 20
            })
        
        # 添加Token委托关系
        for token_name, token in st.session_state.demo.tokens.items():
            claims = st.session_state.demo.token_claims.get(token_name)
            if claims:
                edges.append({
                    "source": claims.iss[:8] if claims.iss in [a.id for a in actor_list] else "system",
                    "target": claims.sub[:8],
                    "label": f"Token: {token_name}",
                    "value": 1
                })
        
        # 使用Plotly创建网络图
        if nodes and edges:
            # 创建节点位置
            node_positions = {}
            for i, node in enumerate(nodes):
                angle = 2 * 3.14159 * i / len(nodes)
                node_positions[node["id"]] = (i, i)
            
            # 创建边
            edge_x = []
            edge_y = []
            for edge in edges:
                x0, y0 = node_positions.get(edge["source"], (0, 0))
                x1, y1 = node_positions.get(edge["target"], (0, 0))
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])
            
            # 创建节点
            node_x = [pos[0] for pos in node_positions.values()]
            node_y = [pos[1] for pos in node_positions.values()]
            node_text = [f"{node['label']} ({node['type']})" for node in nodes]
            node_colors = []
            for node in nodes:
                if node["type"] == "user":
                    node_colors.append("blue")
                elif node["type"] == "master_agent":
                    node_colors.append("green")
                else:
                    node_colors.append("orange")
            
            # 创建图
            fig = go.Figure()
            
            # 添加边
            fig.add_trace(go.Scatter(
                x=edge_x, y=edge_y,
                line=dict(width=1, color='gray'),
                hoverinfo='none',
                mode='lines',
                name='委托关系'
            ))
            
            # 添加节点
            fig.add_trace(go.Scatter(
                x=node_x, y=node_y,
                mode='markers+text',
                text=node_text,
                textposition="bottom center",
                marker=dict(
                    size=20,
                    color=node_colors,
                    line=dict(width=2, color='white')
                ),
                name='Agent',
                hoverinfo='text'
            ))
            
            fig.update_layout(
                title="Agent关系与Token委托链",
                showlegend=True,
                hovermode='closest',
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无Agent关系数据。请先运行演示。")
    else:
        st.info("等待演示运行以生成关系图...")

with col2:
    st.header("📈 系统状态")
    
    # 显示演示结果
    if st.session_state.demo_results:
        success_count = sum(1 for r in st.session_state.demo_results.values() if r)
        total_count = len(st.session_state.demo_results)
        
        st.metric("演示成功率", f"{success_count}/{total_count}")
        
        # 进度条
        progress = success_count / total_count if total_count > 0 else 0
        st.progress(progress)
        
        # 结果显示
        st.subheader("步骤结果")
        for step, result in st.session_state.demo_results.items():
            icon = "✅" if result else "❌"
            st.write(f"{icon} {step}")
    else:
        st.info("点击侧边栏按钮运行演示以查看结果")
    
    # 报告状态
    if hasattr(st.session_state.demo, 'report_state'):
        report_state = st.session_state.demo.report_state
        st.subheader("📋 报告生成状态")
        
        status_icons = {
            "data_collected": "✅" if report_state.get('data_collected') else "⏳",
            "analysis_completed": "✅" if report_state.get('analysis_completed') else "⏳",
            "report_generated": "✅" if report_state.get('report_generated') else "⏳",
            "approved": "✅" if report_state.get('approved') else "⏳",
        }
        
        for key, icon in status_icons.items():
            st.write(f"{icon} {key.replace('_', ' ').title()}")

# 审计日志部分
st.markdown("---")
st.header("📝 实时审计日志")

if st.session_state.audit_events:
    # 转换为DataFrame
    audit_data = []
    for event in st.session_state.audit_events[-20:]:  # 显示最近20条
        audit_data.append({
            "时间": datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S"),
            "Actor": event.actor_id[:8],
            "操作": event.action,
            "资源": event.resource,
            "结果": event.result,
            "详细信息": json.dumps(event.details, ensure_ascii=False)[:50] + "..."
        })
    
    df = pd.DataFrame(audit_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # 审计统计
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总审计事件", len(st.session_state.audit_events))
    with col2:
        allow_count = sum(1 for e in st.session_state.audit_events if e.result == "allow")
        st.metric("允许操作", allow_count)
    with col3:
        deny_count = sum(1 for e in st.session_state.audit_events if e.result == "deny")
        st.metric("拒绝操作", deny_count)
    with col4:
        integrity = st.session_state.demo.audit_logger.verify_integrity()
        st.metric("完整性检查", "通过" if integrity else "失败")
    
    # 时间序列图
    if len(st.session_state.audit_events) > 1:
        times = [datetime.fromtimestamp(e.timestamp) for e in st.session_state.audit_events]
        results = [1 if e.result == "allow" else 0 for e in st.session_state.audit_events]
        
        fig = px.scatter(
            x=times, y=results,
            labels={"x": "时间", "y": "结果"},
            title="审计事件时间序列",
            color=results,
            color_continuous_scale=["red", "green"]
        )
        fig.update_traces(marker=dict(size=10))
        fig.update_layout(yaxis=dict(tickvals=[0, 1], ticktext=["拒绝", "允许"]))
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("暂无审计日志数据。请先运行演示。")

# Token信息部分
st.markdown("---")
st.header("🔑 Token状态监控")

if hasattr(st.session_state.demo, 'tokens') and st.session_state.demo.tokens:
    token_data = []
    for token_name, token in st.session_state.demo.tokens.items():
        claims = st.session_state.demo.token_claims.get(token_name)
        if claims:
            token_data.append({
                "名称": token_name,
                "主体": claims.sub[:8],
                "签发者": claims.iss[:8],
                "范围": ", ".join(list(claims.scopes)[:2]) + ("..." if len(claims.scopes) > 2 else ""),
                "使用次数": f"{claims.used_count}/{claims.max_uses if claims.max_uses else '∞'}",
                "状态": "有效" if claims.is_valid() else "无效"
            })
    
    if token_data:
        df_tokens = pd.DataFrame(token_data)
        st.dataframe(df_tokens, use_container_width=True, hide_index=True)
    else:
        st.info("暂无Token信息")
else:
    st.info("等待演示运行以生成Token信息")

# 权限检查演示
st.markdown("---")
st.header("🔍 实时权限检查")

col1, col2, col3 = st.columns(3)

with col1:
    actor_options = ["财务总监", "项目管理Agent", "数据收集Agent", "数据分析Agent", "报告生成Agent", "审批Agent"]
    selected_actor = st.selectbox("选择Agent", actor_options)
    
with col2:
    action_options = ["读取", "写入", "执行", "删除", "委托"]
    selected_action = st.selectbox("选择操作", action_options)
    
with col3:
    resource_options = ["财务数据", "用户数据", "系统配置", "Agent注册表"]
    selected_resource = st.selectbox("选择资源", resource_options)

# 映射选择到实际值
actor_map = {
    "财务总监": "finance_director",
    "项目管理Agent": "project_manager",
    "数据收集Agent": "data_collector",
    "数据分析Agent": "data_analyst",
    "报告生成Agent": "report_generator",
    "审批Agent": "approver"
}

action_map = {
    "读取": ActionType.READ,
    "写入": ActionType.WRITE,
    "执行": ActionType.EXECUTE,
    "删除": ActionType.DELETE,
    "委托": ActionType.DELEGATE
}

resource_map = {
    "财务数据": ResourceType.FINANCIAL_DATA,
    "用户数据": ResourceType.USER_DATA,
    "系统配置": ResourceType.SYSTEM_CONFIG,
    "Agent注册表": ResourceType.AGENT_REGISTRY
}

if st.button("检查权限", type="secondary"):
    actor_role = actor_map.get(selected_actor)
    action = action_map.get(selected_action)
    resource = resource_map.get(selected_resource)
    
    if actor_role and action and resource:
        is_authorized = st.session_state.demo.auth_engine.evaluate_rbac(
            actor_role, action, resource
        )
        
        if is_authorized:
            st.success(f"✅ {selected_actor} 有权限 {selected_action} {selected_resource}")
        else:
            st.error(f"❌ {selected_actor} 没有权限 {selected_action} {selected_resource}")
    else:
        st.warning("请选择有效的Agent、操作和资源")

# 页脚
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p>AI Agent IAM 系统监控面板 | 版本 1.0 | 飞书AI实战挑战赛</p>
</div>
""", unsafe_allow_html=True)