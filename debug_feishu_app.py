#!/usr/bin/env python
"""
调试飞书应用状态和权限问题
"""
import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

print("🔍 飞书应用详细调试工具")
print("=" * 70)

# 检查配置
app_id = os.environ.get("FEISHU_APP_ID")
app_secret = os.environ.get("FEISHU_APP_SECRET")

if not app_id or not app_secret:
    print("❌ 环境变量未配置")
    sys.exit(1)

print(f"📱 App ID: {app_id}")
print(f"🔑 App Secret: {app_secret[:10]}...")

def get_utc_now():
    """获取UTC时间（兼容新旧Python版本）"""
    try:
        return datetime.now(timezone.utc)
    except:
        return datetime.utcnow()

def get_tenant_access_token():
    """获取租户访问令牌"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {"app_id": app_id, "app_secret": app_secret}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("code") == 0:
            return result["tenant_access_token"]
        else:
            print(f"❌ 获取token失败: {result}")
            return None
    except Exception as e:
        print(f"❌ 获取token时出错: {e}")
        return None

def check_application_status(token):
    """检查应用状态"""
    print("\n📊 检查应用状态...")
    
    # 方法1: 通过应用管理API
    url = f"https://open.feishu.cn/open-apis/application/v3/applications/{app_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   应用状态API响应: {response.status_code}")
        
        if response.status_code == 200:
            app_info = response.json()
            print(f"   ✅ 应用存在")
            
            data = app_info.get("data", {})
            print(f"      应用名称: {data.get('name', '未知')}")
            print(f"      应用版本: {data.get('version', '未知')}")
            
            status = data.get("status", {})
            print(f"      应用状态: {status.get('description', '未知')}")
            print(f"      是否可用: {data.get('enable', False)}")
            
            # 检查权限
            scopes = data.get("scopes", [])
            print(f"      已申请权限数: {len(scopes)}")
            
            if scopes:
                print(f"      🔑 权限列表:")
                for scope in scopes[:5]:
                    name = scope.get("scope_name", "未知")
                    status = scope.get("status", {}).get("description", "未知")
                    print(f"        • {name}: {status}")
                
                if len(scopes) > 5:
                    print(f"        ... 还有 {len(scopes) - 5} 个权限")
                    
                # 检查是否有日历权限
                calendar_scopes = [s for s in scopes if "calendar" in s.get("scope_name", "").lower()]
                print(f"      📅 日历相关权限: {len(calendar_scopes)} 个")
                
        elif response.status_code == 403:
            print("   ❌ 权限不足 (403) - 无法访问应用信息")
            print("      可能需要管理员权限或应用未正确配置")
        elif response.status_code == 404:
            print("   ❌ 应用不存在 (404)")
            print("      请检查App ID是否正确")
        else:
            print(f"   ⚠️ 其他状态码: {response.status_code}")
            print(f"      响应: {response.text[:200]}")
            
    except Exception as e:
        print(f"   ❌ 检查应用状态时出错: {e}")

def check_calendar_permissions(token):
    """详细检查日历权限问题"""
    print("\n📅 详细检查日历权限...")
    
    # 测试1: 获取日历列表（需要日历读取权限）
    print("   1. 测试获取日历列表...")
    url = "https://open.feishu.cn/open-apis/calendar/v4/calendars"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"      响应: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            calendars = data.get("data", {}).get("items", [])
            print(f"      ✅ 成功! 找到 {len(calendars)} 个日历")
            for cal in calendars[:3]:
                print(f"        • {cal.get('summary', '未命名')} (ID: {cal.get('calendar_id', '未知')})")
        elif response.status_code == 403:
            print("      ❌ 权限不足 - 需要 calendar:calendar:readonly 权限")
        elif response.status_code == 400:
            print("      ❌ 请求参数错误 (400)")
            print(f"        详细错误: {response.text[:200]}")
        else:
            print(f"      ⚠️ 其他错误: {response.status_code}")
            print(f"        响应: {response.text[:200]}")
            
    except Exception as e:
        print(f"      ❌ 请求异常: {e}")
    
    # 测试2: 尝试不同的时间格式
    print("\n   2. 测试不同时间格式...")
    
    now_utc = get_utc_now()
    time_formats = [
        ("RFC3339完整", now_utc.isoformat().replace("+00:00", "Z")),
        ("RFC3339简单", now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")),
        ("带时区", now_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00")),
        ("仅日期", now_utc.strftime("%Y-%m-%d")),
    ]
    
    for fmt_name, time_str in time_formats:
        print(f"      格式: {fmt_name} -> {time_str}")
        
        url = "https://open.feishu.cn/open-apis/calendar/v4/calendars/primary/events"
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "start_time": time_str,
            "end_time": (now_utc + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "page_size": 10  # 添加page_size参数
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                print(f"      ✅ 成功!")
                data = response.json()
                print(f"        响应结构: {list(data.keys())}")
                break
            elif response.status_code == 400:
                error = response.json()
                print(f"      ❌ 400错误")
                print(f"        错误代码: {error.get('code', '未知')}")
                print(f"        错误信息: {error.get('msg', '未知')}")
                
                # 显示详细错误信息
                details = error.get("error", {}).get("details", [])
                if details:
                    for detail in details:
                        print(f"        详情: {detail.get('key')} = {detail.get('value')}")
            else:
                print(f"      ⚠️ 状态码: {response.status_code}")
                
        except Exception as e:
            print(f"      ❌ 异常: {e}")

def check_user_permissions(token):
    """检查用户相关权限"""
    print("\n👤 检查用户权限...")
    
    # 获取当前用户信息（需要contact权限）
    url = "https://open.feishu.cn/open-apis/authen/v1/user_info"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   用户信息API: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✅ 用户权限验证通过")
            data = response.json()
            user = data.get("data", {})
            print(f"      用户: {user.get('name', '未知')}")
            print(f"      邮箱: {user.get('email', '未知')}")
        elif response.status_code == 403:
            print("   ❌ 用户权限不足")
        else:
            print(f"   ⚠️ 其他响应: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ 检查用户权限时出错: {e}")

def test_simple_api_calls(token):
    """测试简单的API调用"""
    print("\n🔧 测试基础API调用...")
    
    # 测试获取服务器时间
    url = "https://open.feishu.cn/open-apis/authen/v1/index"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   1. 认证端点: {response.status_code}")
    except Exception as e:
        print(f"   1. 认证端点错误: {e}")
    
    # 测试OPTIONS方法
    url = "https://open.feishu.cn/open-apis/calendar/v4/calendars"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.options(url, headers=headers, timeout=10)
        print(f"   2. 日历OPTIONS: {response.status_code}")
        if response.status_code == 200:
            print(f"      支持的方法: {response.headers.get('allow', '未知')}")
    except Exception as e:
        print(f"   2. OPTIONS错误: {e}")

# 主程序
print("\n🔐 获取访问令牌...")
token = get_tenant_access_token()

if not token:
    print("❌ 无法获取访问令牌，调试终止")
    sys.exit(1)

print(f"✅ 令牌获取成功: {token[:20]}...")

# 执行各项检查
check_application_status(token)
check_calendar_permissions(token)
check_user_permissions(token)
test_simple_api_calls(token)

print("\n" + "=" * 70)
print("📋 调试总结与建议")

# 分析可能的问题
print("\n🔍 可能的问题分析:")

# 检查环境变量
feishu_skills_enabled = os.environ.get("FEISHU_SKILLS_ENABLED", "true").lower()
if feishu_skills_enabled != "true":
    print("1. ⚠️ FEISHU_SKILLS_ENABLED 未设置为 true")
else:
    print("1. ✅ FEISHU_SKILLS_ENABLED 设置正确")

# 检查应用权限
print("2. 🔑 应用权限状态:")
print("   - 如果应用返回404: App ID可能不正确")
print("   - 如果返回403: 应用可能需要管理员授权")
print("   - 如果日历API返回400: 时间格式或参数问题")

# 建议操作
print("\n🎯 建议操作:")

print("A. 验证应用配置:")
print("   1. 登录飞书开放平台: https://open.feishu.cn/app")
print("   2. 检查应用是否存在，状态是否为'已启用'")
print("   3. 检查权限是否已申请并通过审批")

print("\nB. 测试不同的API端点:")
print("   1. 先测试不需要权限的端点（如认证端点）")
print("   2. 测试获取用户信息（需要contact权限）")
print("   3. 最后测试日历API")

print("\nC. 如果问题持续:")
print("   1. 尝试创建新的飞书应用")
print("   2. 使用新的App ID和App Secret")
print("   3. 重新申请必要的权限")
print("   4. 确保应用已发布到企业")

print("\nD. IAM系统集成:")
print("   如果飞书API测试成功，运行:")
print("   python feishu_demo.py --real-api")
print("   python test_feishu_client.py")

# 生成配置文件
print("\n🔧 当前配置摘要:")
print(f"   FEISHU_APP_ID: {app_id}")
print(f"   FEISHU_APP_SECRET: {app_secret[:10]}...")
print(f"   FEISHU_SKILLS_ENABLED: {feishu_skills_enabled}")

print("\n⚠️ 如果App ID不正确，请:")
print("   1. 从飞书开放平台获取正确的App ID")
print("   2. 更新.env文件")
print("   3. 重新运行测试")

# 检查IAM模块
print("\n🤖 IAM系统模块检查...")
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from agent_iam.feishu_integration import FeishuIntegration, REAL_API_AVAILABLE
    
    print(f"   ✅ IAM飞书集成模块可用")
    print(f"   REAL_API_AVAILABLE: {REAL_API_AVAILABLE}")
    
    # 测试初始化
    integration = FeishuIntegration()
    print(f"   FeishuIntegration初始化: 成功")
    
except ImportError as e:
    print(f"   ❌ IAM模块导入失败: {e}")
except Exception as e:
    print(f"   ⚠️ IAM模块测试失败: {e}")