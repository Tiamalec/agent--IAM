#!/usr/bin/env python
"""
飞书IAM集成使用示例
展示如何将IAM系统与飞书平台集成
"""
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

print("🚀 飞书IAM集成示例")
print("=" * 60)

# 检查环境变量配置
app_id = os.environ.get("FEISHU_APP_ID")
app_secret = os.environ.get("FEISHU_APP_SECRET")
redirect_uri = os.environ.get("FEISHU_REDIRECT_URI")

if not app_id or not app_secret:
    print("❌ 请配置飞书环境变量:")
    print("   FEISHU_APP_ID=您的App ID")
    print("   FEISHU_APP_SECRET=您的App Secret")
    print("   FEISHU_REDIRECT_URI=您的回调地址（可选）")
    sys.exit(1)

print(f"✅ 飞书凭证配置正确")
print(f"   App ID: {app_id[:10]}...")
print(f"   App Secret: {app_secret[:10]}...")

# 导入飞书集成模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from agent_iam.feishu_integration import (
        FeishuOAuth2Client,
        FeishuSSOManager,
        FeishuOrgSync,
        FeishuPermissionMapper,
        FeishuSkill,
        FeishuAction,
        FeishuResource
    )
    from agent_iam.token_service import TokenService
    from agent_iam.auth_engine import AuthorizationEngine
    from agent_iam.models import ActorType
    
    print("✅ 飞书集成模块导入成功")
    
except ImportError as e:
    print(f"❌ 模块导入失败: {e}")
    sys.exit(1)

def example_oauth2_flow():
    """示例1: OAuth2.0登录流程"""
    print("\n🔐 示例1: OAuth2.0登录流程")
    print("-" * 40)
    
    # 初始化OAuth2客户端
    oauth_client = FeishuOAuth2Client(
        app_id=app_id,
        app_secret=app_secret,
        redirect_uri=redirect_uri
    )
    
    # 生成授权URL
    auth_url = oauth_client.get_authorization_url(
        state="test_state_123",
        scope="contact:user.base:readonly"
    )
    
    print(f"📋 授权URL: {auth_url[:80]}...")
    print("   用户访问此URL进行授权，然后重定向到回调地址")
    print("   回调地址将包含授权码，用于获取访问令牌")
    
    # 模拟授权码（实际中从回调URL获取）
    test_code = "test_authorization_code"
    
    print(f"\n🔄 使用授权码获取访问令牌...")
    token_result = oauth_client.exchange_code_for_token(test_code)
    
    if token_result.get("success"):
        print(f"✅ 令牌获取成功（模拟）")
        print(f"   访问令牌: {token_result.get('access_token', '')[:20]}...")
        print(f"   刷新令牌: {token_result.get('refresh_token', '')[:20]}...")
        print(f"   有效期: {token_result.get('expires_in', 0)}秒")
    else:
        print(f"❌ 令牌获取失败: {token_result.get('error', '未知错误')}")
        print("   注意：这是一个模拟，需要真实的授权码才能成功")

def example_sso_integration():
    """示例2: SSO单点登录集成"""
    print("\n🔐 示例2: SSO单点登录集成")
    print("-" * 40)
    
    # 初始化IAM服务
    token_service = TokenService(secret_key="test_secret_key")
    auth_engine = AuthorizationEngine()
    
    # 初始化OAuth2客户端
    oauth_client = FeishuOAuth2Client(
        app_id=app_id,
        app_secret=app_secret,
        redirect_uri=redirect_uri
    )
    
    # 初始化SSO管理器
    sso_manager = FeishuSSOManager(oauth_client, token_service, auth_engine)
    
    # 模拟授权码（实际中从回调URL获取）
    test_code = "test_sso_code_123"
    
    print(f"🔄 使用SSO管理器验证用户...")
    actor, iam_token, user_info = sso_manager.authenticate_user(test_code)
    
    if actor and iam_token:
        print(f"✅ SSO登录成功")
        print(f"   用户: {actor.name}")
        print(f"   用户ID: {actor.id}")
        print(f"   IAM令牌: {iam_token[:50]}...")
        print(f"   飞书用户信息: {user_info.get('name', '未知')}")
        print(f"   邮箱: {user_info.get('email', '未知')}")
    else:
        print(f"❌ SSO登录失败（模拟）")
        print("   注意：这是一个模拟，需要真实的授权码才能成功")

def example_org_sync():
    """示例3: 组织架构同步"""
    print("\n🏢 示例3: 组织架构同步")
    print("-" * 40)
    
    # 初始化组织架构同步器
    org_sync = FeishuOrgSync(app_id=app_id, app_secret=app_secret)
    
    print("🔄 获取部门列表...")
    dept_result = org_sync.get_departments()
    
    if dept_result.get("success"):
        departments = dept_result.get("departments", [])
        print(f"✅ 获取到 {len(departments)} 个部门")
        
        # 显示前3个部门
        for i, dept in enumerate(departments[:3]):
            print(f"   {i+1}. {dept.get('name')} (ID: {dept.get('department_id')})")
        
        if len(departments) > 3:
            print(f"   ... 还有 {len(departments) - 3} 个部门")
    else:
        print(f"❌ 获取部门失败: {dept_result.get('error', '未知错误')}")
        print("   注意：需要飞书应用有contact权限")
    
    print("\n🔄 获取用户列表...")
    users_result = org_sync.get_users()
    
    if users_result.get("success"):
        users = users_result.get("users", [])
        print(f"✅ 获取到 {len(users)} 个用户")
        
        # 显示前3个用户
        for i, user in enumerate(users[:3]):
            print(f"   {i+1}. {user.get('name')} ({user.get('email', '无邮箱')})")
        
        if len(users) > 3:
            print(f"   ... 还有 {len(users) - 3} 个用户")
    else:
        print(f"❌ 获取用户失败: {users_result.get('error', '未知错误')}")

def example_permission_mapping():
    """示例4: 权限映射配置"""
    print("\n🔧 示例4: 权限映射配置")
    print("-" * 40)
    
    # 初始化权限映射器
    permission_mapper = FeishuPermissionMapper()
    
    # 示例：将飞书日历Skill映射到IAM Scopes
    skill = FeishuSkill.CALENDAR
    action = FeishuAction.READ
    resource = FeishuResource.CALENDAR
    
    print(f"🔄 映射飞书权限到IAM Scopes:")
    print(f"   Skill: {skill.value}")
    print(f"   Action: {action.value}")
    print(f"   Resource: {resource.value}")
    
    iam_scopes = permission_mapper.map_feishu_to_iam(skill, action, resource)
    
    if iam_scopes:
        print(f"✅ 映射结果:")
        for scope in iam_scopes:
            print(f"   - {scope}")
    else:
        print(f"❌ 无映射规则")
    
    # 反向映射示例
    print(f"\n🔄 反向映射（IAM Scopes到飞书权限）:")
    test_scopes = {"read:calendar", "read:event", "send:message"}
    
    feishu_permissions = permission_mapper.map_iam_to_feishu(test_scopes)
    
    if feishu_permissions:
        print(f"✅ 映射结果:")
        for perm in feishu_permissions:
            print(f"   - {perm['skill'].value}.{perm['action']}")
            print(f"     所需Scopes: {perm['required_scopes']}")
    else:
        print(f"❌ 无映射规则")
    
    # 权限验证示例
    print(f"\n🔄 权限验证示例:")
    user_scopes = {"read:calendar", "read:event", "write:calendar"}
    has_permission = permission_mapper.validate_iam_scopes_for_feishu(
        skill, action, user_scopes
    )
    
    print(f"   用户Scopes: {user_scopes}")
    print(f"   执行 {skill.value}.{action.value} 所需Scopes: {permission_mapper.get_required_scopes_for_feishu(skill, action)}")
    print(f"   权限验证结果: {'✅ 通过' if has_permission else '❌ 拒绝'}")

def example_integration_summary():
    """示例5: 集成架构概览"""
    print("\n🏗️  示例5: 集成架构概览")
    print("-" * 40)
    
    print("📊 集成组件:")
    print("   1. FeishuOAuth2Client - OAuth2.0身份验证")
    print("   2. FeishuSSOManager - 单点登录管理")
    print("   3. FeishuOrgSync - 组织架构同步")
    print("   4. FeishuPermissionMapper - 权限映射配置")
    print("   5. FeishuIntegration - 核心集成服务（兼容旧版）")
    
    print("\n🔗 集成流程:")
    print("   1. 用户通过飞书OAuth2.0登录")
    print("   2. SSO管理器验证用户并创建IAM令牌")
    print("   3. 定期同步组织架构数据")
    print("   4. 权限映射器控制飞书操作权限")
    print("   5. 统一审计日志记录所有操作")
    
    print("\n⚙️  配置要求:")
    print("   1. 飞书应用凭证（App ID/Secret）")
    print("   2. OAuth2.0回调地址")
    print("   3. 必要的API权限（contact, calendar, im等）")
    print("   4. IAM系统配置")

def main():
    """主函数"""
    print("\n🎯 开始执行飞书IAM集成示例")
    print("=" * 60)
    
    try:
        # 执行各个示例
        example_oauth2_flow()
        example_sso_integration()
        example_org_sync()
        example_permission_mapping()
        example_integration_summary()
        
        print("\n" + "=" * 60)
        print("🎉 示例执行完成")
        print("\n💡 下一步:")
        print("   1. 配置真实的飞书应用凭证")
        print("   2. 设置OAuth2.0回调地址")
        print("   3. 申请必要的API权限")
        print("   4. 集成到您的IAM系统")
        print("   5. 运行完整测试: python -m pytest tests/")
        
    except Exception as e:
        print(f"\n❌ 示例执行出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()