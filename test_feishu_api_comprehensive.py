#!/usr/bin/env python
"""
全面测试飞书API，确定问题范围
"""
import os
import sys
import requests
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

print("🔍 全面测试飞书API")
print("=" * 60)

# 获取配置
app_id = os.environ.get("FEISHU_APP_ID")
app_secret = os.environ.get("FEISHU_APP_SECRET")

if not app_id or not app_secret:
    print("❌ 环境变量未配置")
    sys.exit(1)

print(f"📱 App ID: {app_id}")
print(f"🔑 App Secret: {app_secret[:10]}...")

# 获取访问令牌
def get_access_token():
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

token = get_access_token()
if not token:
    print("❌ 无法获取访问令牌")
    sys.exit(1)

print(f"✅ 访问令牌获取成功: {token[:20]}...")

# 测试不同的API端点
print("\n🚀 测试不同API端点...")

api_tests = [
    # 基础认证API
    {
        "name": "用户信息",
        "url": "https://open.feishu.cn/open-apis/authen/v1/user_info",
        "method": "GET",
        "expected": 200,
        "description": "基础认证权限测试"
    },
    
    # 日历相关API
    {
        "name": "日历列表",
        "url": "https://open.feishu.cn/open-apis/calendar/v4/calendars",
        "method": "GET", 
        "expected": 200,
        "description": "日历读取权限测试"
    },
    
    # 尝试不同的日历事件查询方式
    {
        "name": "日历事件(简化查询)",
        "url": "https://open.feishu.cn/open-apis/calendar/v4/calendars/primary/events",
        "method": "GET",
        "params": {"page_size": 10},  # 只提供page_size，不提供时间范围
        "expected": "200或400",
        "description": "测试是否必须提供时间范围"
    },
    
    {
        "name": "日历事件(仅开始时间)",
        "url": "https://open.feishu.cn/open-apis/calendar/v4/calendars/primary/events",
        "method": "GET",
        "params": {"start_time": "2024-01-01", "page_size": 5},
        "expected": "200或400", 
        "description": "测试是否必须提供结束时间"
    },
    
    # 消息API（需要im权限）
    {
        "name": "消息能力检查",
        "url": "https://open.feishu.cn/open-apis/im/v1/messages",
        "method": "OPTIONS",
        "expected": "200或403",
        "description": "检查消息API权限"
    },
    
    # 联系人API（需要contact权限）
    {
        "name": "联系人搜索",
        "url": "https://open.feishu.cn/open-apis/contact/v3/users",
        "method": "GET",
        "params": {"page_size": 5},
        "expected": "200或403",
        "description": "检查联系人API权限"
    },
    
    # 应用相关API
    {
        "name": "应用概览(v3)",
        "url": f"https://open.feishu.cn/open-apis/application/v3/applications/{app_id}",
        "method": "GET",
        "expected": "200或403或404",
        "description": "应用信息API测试"
    },
    
    # 简单健康检查
    {
        "name": "API健康检查",
        "url": "https://open.feishu.cn/open-apis/authen/v1/index",
        "method": "GET",
        "expected": 200,
        "description": "基础API连通性"
    }
]

results = []

for test in api_tests:
    print(f"\n📡 测试: {test['name']}")
    print(f"   描述: {test['description']}")
    print(f"   URL: {test['url']}")
    
    headers = {"Authorization": f"Bearer {token}"}
    params = test.get("params", {})
    
    try:
        if test["method"] == "GET":
            response = requests.get(test["url"], headers=headers, params=params, timeout=10)
        elif test["method"] == "POST":
            response = requests.post(test["url"], headers=headers, json=params, timeout=10)
        elif test["method"] == "OPTIONS":
            response = requests.options(test["url"], headers=headers, timeout=10)
        else:
            print(f"   ❌ 不支持的HTTP方法: {test['method']}")
            results.append((test['name'], "error", f"不支持的HTTP方法"))
            continue
        
        status = response.status_code
        print(f"   状态码: {status}")
        
        # 分析响应
        if status == 200:
            print(f"   ✅ 成功!")
            
            # 显示响应结构
            if response.content:
                try:
                    data = response.json()
                    # 显示关键信息
                    if "data" in data:
                        data_info = data["data"]
                        if isinstance(data_info, dict):
                            keys = list(data_info.keys())
                            print(f"      响应结构: {keys[:5]}...")
                        elif isinstance(data_info, list):
                            print(f"      数据条数: {len(data_info)}")
                except:
                    print(f"      响应内容: {response.text[:100]}")
                    
        elif status == 400:
            print(f"   ❌ 参数错误 (400)")
            try:
                error = response.json()
                print(f"      错误代码: {error.get('code', '未知')}")
                print(f"      错误信息: {error.get('msg', '未知')}")
                
                # 显示详细错误
                error_details = error.get("error", {}).get("details", [])
                if error_details:
                    print(f"      错误详情:")
                    for detail in error_details[:3]:
                        key = detail.get("key", "未知")
                        value = detail.get("value", "未知")
                        print(f"        • {key}: {value}")
            except:
                print(f"      原始错误: {response.text[:100]}")
                
        elif status == 403:
            print(f"   ❌ 权限不足 (403)")
            print(f"      需要相应API权限")
        elif status == 404:
            print(f"   ❌ 未找到 (404)")
        else:
            print(f"   ⚠️ 其他状态码")
            print(f"      响应: {response.text[:100]}")
            
        results.append((test['name'], status, response.text[:100] if response.text else ""))
        
    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
        results.append((test['name'], "exception", str(e)))

# 专门分析日历API问题
print("\n" + "=" * 60)
print("📅 专门分析日历API问题")

# 测试日历API的原始请求
print("\n🔧 测试日历API原始请求...")

# 获取日历设置
print("1. 获取日历设置详情...")
calendars_url = "https://open.feishu.cn/open-apis/calendar/v4/calendars"
headers = {"Authorization": f"Bearer {token}"}

try:
    response = requests.get(calendars_url, headers=headers, timeout=10)
    if response.status_code == 200:
        data = response.json()
        calendars = data.get("data", {}).get("items", [])
        print(f"   找到 {len(calendars)} 个日历")
        
        if calendars:
            for i, cal in enumerate(calendars[:3]):
                cal_id = cal.get("calendar_id", "未知")
                cal_summary = cal.get("summary", "未命名")
                cal_type = cal.get("type", "未知")
                print(f"     {i+1}. {cal_summary} (ID: {cal_id}, 类型: {cal_type})")
                
                # 测试该日历的事件
                events_url = f"https://open.feishu.cn/open-apis/calendar/v4/calendars/{cal_id}/events"
                
                # 尝试不同的查询方式
                test_queries = [
                    {"name": "空查询", "params": {}},
                    {"name": "仅page_size", "params": {"page_size": 5}},
                    {"name": "简单日期", "params": {"start_time": "2024-01-01", "page_size": 5}},
                ]
                
                for query in test_queries:
                    print(f"       测试 {query['name']}...")
                    try:
                        resp = requests.get(events_url, headers=headers, params=query['params'], timeout=10)
                        print(f"         状态码: {resp.status_code}")
                        if resp.status_code == 400:
                            error = resp.json()
                            print(f"         错误: {error.get('msg', '未知')}")
                    except Exception as e:
                        print(f"         异常: {e}")
    else:
        print(f"   获取日历失败: {response.status_code}")
        
except Exception as e:
    print(f"   日历API测试异常: {e}")

# 测试事件创建（需要写权限）
print("\n2. 测试事件创建（需要写权限）...")
if calendars:
    cal_id = calendars[0].get("calendar_id") if calendars else "primary"
    
    # 尝试创建测试事件
    create_url = f"https://open.feishu.cn/open-apis/calendar/v4/calendars/{cal_id}/events"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    event_data = {
        "summary": "测试事件",
        "description": "IAM系统测试事件",
        "start_time": {"date_time": "2024-01-01T10:00:00+08:00"},
        "end_time": {"date_time": "2024-01-01T11:00:00+08:00"}
    }
    
    try:
        response = requests.post(create_url, headers=headers, json=event_data, timeout=10)
        print(f"   创建事件状态码: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ 事件创建成功!")
        elif response.status_code == 403:
            print(f"   ❌ 创建事件权限不足")
        elif response.status_code == 400:
            error = response.json()
            print(f"   ❌ 参数错误: {error.get('msg', '未知')}")
    except Exception as e:
        print(f"   创建事件异常: {e}")

# 结果总结
print("\n" + "=" * 60)
print("📋 测试结果总结")

success_count = sum(1 for name, status, _ in results if status == 200)
total_count = len(results)

print(f"✅ 成功: {success_count}/{total_count}")
print(f"❌ 失败: {total_count - success_count}/{total_count}")

print("\n🔍 关键发现:")

# 检查用户信息API
user_info_ok = any(name == "用户信息" and status == 200 for name, status, _ in results)
if user_info_ok:
    print("✅ 用户信息API正常 - 基础认证权限有效")
else:
    print("❌ 用户信息API失败 - 基础权限可能有问题")

# 检查日历列表API
calendar_list_ok = any(name == "日历列表" and status == 200 for name, status, _ in results)
if calendar_list_ok:
    print("✅ 日历列表API正常 - 日历读取权限存在")
else:
    print("❌ 日历列表API失败 - 日历权限可能未正确配置")

# 检查应用信息API
app_info_ok = any(name == "应用概览(v3)" and status == 200 for name, status, _ in results)
if app_info_ok:
    print("✅ 应用信息API正常 - 应用可被API访问")
else:
    print("⚠️ 应用信息API失败 - 但应用可能在飞书平台存在")

print("\n🎯 针对日历事件API失败的建议:")

if calendar_list_ok:
    print("1. 日历权限存在，但事件API参数可能有问题")
    print("2. 尝试以下解决方案:")
    print("   • 检查日历是否为空（没有事件）")
    print("   • 确认时间格式正确（RFC3339带时区）")
    print("   • 确保提供了所有必需参数")
    print("   • 检查是否有事件查看权限限制")
else:
    print("1. 日历权限可能未完全配置")
    print("2. 需要权限: calendar:calendar:readonly")

print("\n🚀 下一步行动:")

print("A. 如果只想测试IAM系统功能:")
print("   暂时使用模拟模式:")
print("   FEISHU_SKILLS_ENABLED=false python feishu_demo.py")

print("\nB. 如果要解决真实API问题:")
print("   1. 检查飞书开放平台权限配置")
print("   2. 确保应用已发布")
print("   3. 检查API调用参数")
print("   4. 联系飞书技术支持")

print("\nC. IAM系统集成测试:")
print("   运行: python test_iam_feishu_integration.py")
print("   如果真实API有问题，系统会自动回退到模拟模式")

# 检查IAM系统配置
print("\n🔧 IAM系统当前配置:")
feishu_skills_enabled = os.environ.get("FEISHU_SKILLS_ENABLED", "true").lower()
print(f"   FEISHU_SKILLS_ENABLED: {feishu_skills_enabled}")

if feishu_skills_enabled == "true":
    print("   ✅ IAM系统将尝试使用真实API")
    print("   ⚠️ 如果真实API失败，部分功能可能使用模拟数据")
else:
    print("   ℹ️ IAM系统使用模拟模式")
    print("   要使用真实API，请设置FEISHU_SKILLS_ENABLED=true")