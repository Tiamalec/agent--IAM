#!/usr/bin/env python
"""
测试飞书日历API权限
专门验证日历权限是否生效
"""
import os
import sys
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

print("📅 飞书日历API权限测试")
print("=" * 60)

# 检查配置
app_id = os.environ.get("FEISHU_APP_ID")
app_secret = os.environ.get("FEISHU_APP_SECRET")

if not app_id or not app_secret:
    print("❌ 环境变量未配置")
    sys.exit(1)

print(f"✅ 使用App ID: {app_id}")
print(f"✅ 使用App Secret: {app_secret[:10]}...")

def get_tenant_access_token(app_id, app_secret):
    """获取租户访问令牌"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {"app_id": app_id, "app_secret": app_secret}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("code") == 0:
            return result["tenant_access_token"], result["expire"]
        else:
            print(f"❌ 获取token失败: {result.get('msg')}")
            return None, 0
    except Exception as e:
        print(f"❌ 获取token时出错: {e}")
        return None, 0

def test_calendar_api_with_different_formats(token):
    """使用不同时间格式测试日历API"""
    formats_to_test = [
        # 格式1: UTC带Z后缀
        {
            "name": "UTC带Z后缀",
            "start_time": datetime.utcnow().isoformat() + "Z",
            "end_time": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z"
        },
        # 格式2: UTC不带Z后缀
        {
            "name": "UTC不带Z后缀", 
            "start_time": datetime.utcnow().isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=1)).isoformat()
        },
        # 格式3: 本地时间带时区
        {
            "name": "本地时间带+08:00时区",
            "start_time": datetime.now().isoformat(),
            "end_time": (datetime.now() + timedelta(days=1)).isoformat()
        },
        # 格式4: 简单的今天日期
        {
            "name": "今天日期范围",
            "start_time": datetime.utcnow().strftime("%Y-%m-%d") + "T00:00:00Z",
            "end_time": datetime.utcnow().strftime("%Y-%m-%d") + "T23:59:59Z"
        },
        # 格式5: RFC3339格式（飞书官方推荐）
        {
            "name": "RFC3339格式",
            "start_time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    ]
    
    results = []
    
    for fmt in formats_to_test:
        print(f"\n🔄 测试格式: {fmt['name']}")
        print(f"   start_time: {fmt['start_time']}")
        print(f"   end_time: {fmt['end_time']}")
        
        url = "https://open.feishu.cn/open-apis/calendar/v4/calendars/primary/events"
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "start_time": fmt["start_time"],
            "end_time": fmt["end_time"]
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            result = {
                "format": fmt["name"],
                "status_code": response.status_code,
                "success": response.status_code == 200
            }
            
            if response.status_code == 200:
                data = response.json()
                events = data.get("data", {}).get("items", [])
                result["event_count"] = len(events)
                result["message"] = "成功"
                print(f"   ✅ 成功! 获取到 {len(events)} 个事件")
                
                # 显示事件详情
                for i, event in enumerate(events[:2]):
                    summary = event.get("summary", "无标题")
                    start_time = event.get("start", {}).get("date_time", "未知")
                    print(f"      {i+1}. {summary} ({start_time})")
                    
            elif response.status_code == 400:
                error_data = response.json()
                result["error"] = error_data.get("msg", "未知错误")
                result["details"] = error_data
                print(f"   ❌ 参数错误 (400): {error_data.get('msg', '未知')}")
                
            elif response.status_code == 403:
                print(f"   ❌ 权限不足 (403)")
                print(f"      需要权限: calendar:calendar:readonly")
                result["error"] = "权限不足"
                
            else:
                print(f"   ❌ 失败 ({response.status_code}): {response.text[:100]}")
                result["error"] = f"HTTP {response.status_code}"
                
            results.append(result)
            
        except Exception as e:
            print(f"   ❌ 请求异常: {e}")
            results.append({
                "format": fmt["name"],
                "status_code": 0,
                "success": False,
                "error": str(e)
            })
    
    return results

def test_calendar_scopes(token):
    """测试日历相关权限范围"""
    print("\n🔍 测试日历权限范围...")
    
    # 测试不同的日历操作
    tests = [
        {
            "name": "获取主日历事件",
            "url": "https://open.feishu.cn/open-apis/calendar/v4/calendars/primary/events",
            "method": "GET",
            "params": {
                "start_time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_time": (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
            }
        },
        {
            "name": "获取日历列表",
            "url": "https://open.feishu.cn/open-apis/calendar/v4/calendars",
            "method": "GET",
            "params": {}
        },
        {
            "name": "获取日历ACL",
            "url": "https://open.feishu.cn/open-apis/calendar/v4/calendars/primary/acl",
            "method": "GET",
            "params": {}
        }
    ]
    
    for test in tests:
        print(f"\n📋 测试: {test['name']}")
        print(f"   端点: {test['url']}")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            if test["method"] == "GET":
                response = requests.get(test["url"], headers=headers, params=test["params"], timeout=10)
            else:
                response = requests.post(test["url"], headers=headers, json=test["params"], timeout=10)
            
            if response.status_code == 200:
                print(f"   ✅ 权限验证通过")
                data = response.json()
                # 显示部分数据
                if "calendars" in str(data):
                    calendars = data.get("data", {}).get("items", [])
                    print(f"   找到 {len(calendars)} 个日历")
                elif "events" in str(data):
                    events = data.get("data", {}).get("items", [])
                    print(f"   找到 {len(events)} 个事件")
            elif response.status_code == 403:
                print(f"   ❌ 权限不足 (403)")
                print(f"      此操作需要额外权限")
            else:
                print(f"   ⚠️ 其他响应: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ 测试失败: {e}")

# 主测试流程
print("\n🔐 1. 获取访问令牌...")
token, expire = get_tenant_access_token(app_id, app_secret)

if not token:
    print("❌ 无法获取访问令牌，测试终止")
    sys.exit(1)

print(f"✅ 令牌获取成功: {token[:20]}...")
print(f"✅ 有效期: {expire}秒")

print("\n🚀 2. 测试日历API（不同时间格式）...")
results = test_calendar_api_with_different_formats(token)

# 分析结果
print("\n" + "=" * 60)
print("📊 测试结果分析")

successful_tests = [r for r in results if r.get("success")]
if successful_tests:
    print(f"✅ {len(successful_tests)}/{len(results)} 种时间格式测试成功")
    
    # 找出成功的时间格式
    successful_format = successful_tests[0]["format"]
    print(f"✅ 可用的时间格式: {successful_format}")
    
    # 测试更多日历权限
    test_calendar_scopes(token)
    
    print("\n🎉 日历权限验证成功！")
    print("   您的IAM系统现在可以访问飞书日历数据")
    
else:
    print(f"❌ 所有时间格式测试失败")
    
    # 分析失败原因
    error_counts = {}
    for result in results:
        error = result.get("error", "未知错误")
        error_counts[error] = error_counts.get(error, 0) + 1
    
    print("\n🔍 错误分析:")
    for error, count in error_counts.items():
        print(f"   • {error}: {count}次")
    
    if "权限不足" in error_counts:
        print("\n⚠️ 可能的问题:")
        print("   1. 日历权限未正确申请或审批")
        print("   2. 应用未发布或未获得管理员授权")
        print("   3. 权限配置有延迟，请等待几分钟后重试")
    
    if "参数错误" in error_counts:
        print("\n⚠️ 时间格式问题:")
        print("   飞书API期望的时间格式可能是:")
        print("   • RFC3339格式: 2024-01-01T00:00:00Z")
        print("   • 或带时区: 2024-01-01T00:00:00+08:00")

print("\n" + "=" * 60)
print("📋 下一步建议:")

# 检查其他权限
print("\n🔑 检查其他飞书权限状态...")
try:
    # 测试消息API权限
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.options(url, headers=headers, timeout=5)
    
    if response.status_code == 200:
        print("✅ 消息API权限可能已配置")
    elif response.status_code == 403:
        print("❌ 消息API权限不足 (需要 im:message 权限)")
    else:
        print(f"⚠️ 消息API状态: {response.status_code}")
        
except Exception as e:
    print(f"⚠️ 检查消息API时出错: {e}")

print("\n💡 如果日历API工作正常，您可以:")
print("   1. 运行完整IAM测试: python feishu_demo.py")
print("   2. 启动API服务: python run_api.py")
print("   3. 测试其他飞书Skills集成")

# 生成配置文件建议
print("\n🔧 配置建议（如果测试成功）:")
print("   在.env文件中确保:")
print("   FEISHU_SKILLS_ENABLED=true")
print("   FEISHU_APP_ID=您的App ID")
print("   FEISHU_APP_SECRET=您的App Secret")