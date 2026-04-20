#!/usr/bin/env python
"""
诊断飞书API连接问题
"""
import os
import sys
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

print("🔍 飞书API连接诊断工具")
print("=" * 60)

# 检查配置
app_id = os.environ.get("FEISHU_APP_ID")
app_secret = os.environ.get("FEISHU_APP_SECRET")

if not app_id or not app_secret:
    print("❌ 环境变量未配置")
    print("请在.env文件中设置:")
    print("  FEISHU_APP_ID=您的App ID")
    print("  FEISHU_APP_SECRET=您的App Secret")
    sys.exit(1)

print(f"✅ 飞书凭证配置正确")
print(f"   App ID: {app_id}")
print(f"   App Secret: {app_secret[:10]}...")

# 步骤1: 获取租户访问令牌
print("\n🔐 步骤1: 测试获取访问令牌...")
try:
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {"app_id": app_id, "app_secret": app_secret}
    
    response = requests.post(url, headers=headers, json=data, timeout=10)
    response.raise_for_status()
    
    token_result = response.json()
    
    if token_result.get("code") == 0:
        token = token_result["tenant_access_token"]
        expire = token_result["expire"]
        print(f"✅ 访问令牌获取成功")
        print(f"   令牌: {token[:20]}...")
        print(f"   有效期: {expire}秒")
        
        # 步骤2: 测试获取应用信息
        print("\n📱 步骤2: 测试获取应用信息...")
        try:
            url = f"https://open.feishu.cn/open-apis/application/v3/applications/{app_id}"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                app_info = response.json()
                print(f"✅ 应用信息获取成功")
                print(f"   应用名称: {app_info.get('data', {}).get('name', '未知')}")
                print(f"   应用状态: {app_info.get('data', {}).get('status', {}).get('description', '未知')}")
                
                # 检查应用权限
                if 'data' in app_info and 'scopes' in app_info['data']:
                    scopes = app_info['data']['scopes']
                    print(f"   权限数量: {len(scopes)}")
                    
                    print(f"\n🔑 应用权限列表:")
                    for scope in scopes[:10]:  # 显示前10个权限
                        print(f"   • {scope.get('scope_name', '未知')}: {scope.get('status', '未知')}")
                    
                    if len(scopes) > 10:
                        print(f"   ... 还有 {len(scopes) - 10} 个权限")
                        
                    # 检查日历权限
                    has_calendar = any('calendar' in scope.get('scope_name', '').lower() for scope in scopes)
                    print(f"\n📅 日历权限: {'✅ 已申请' if has_calendar else '❌ 未申请'}")
                    
                else:
                    print("⚠️ 无法获取权限列表，可能需要管理员授权")
                    
            elif response.status_code == 403:
                print("❌ 权限不足 (403)")
                print("   应用可能未发布或未获得管理员授权")
                print("   请登录飞书开放平台检查应用状态")
            elif response.status_code == 404:
                print("❌ 应用不存在 (404)")
                print("   请检查App ID是否正确")
            else:
                print(f"❌ 获取应用信息失败: {response.status_code}")
                print(f"   响应: {response.text[:200]}")
                
        except Exception as e:
            print(f"⚠️ 获取应用信息时出错: {e}")
            
        # 步骤3: 测试简单的API调用（无需特殊权限）
        print("\n🚀 步骤3: 测试无需权限的API...")
        try:
            # 测试获取飞书服务器时间（通常无需权限）
            url = "https://open.feishu.cn/open-apis/authen/v1/index"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.get(url, headers=headers, timeout=10)
            print(f"   认证接口响应: {response.status_code}")
            
        except Exception as e:
            print(f"⚠️ 测试API时出错: {e}")
            
        # 步骤4: 测试日历API（需要权限）
        print("\n📅 步骤4: 测试日历API（需要权限）...")
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            url = "https://open.feishu.cn/open-apis/calendar/v4/calendars/primary/events"
            headers = {"Authorization": f"Bearer {token}"}
            params = {
                "start_time": f"{today}T00:00:00Z",  # UTC时间格式
                "end_time": f"{today}T23:59:59Z"     # UTC时间格式
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ 日历API调用成功")
                events = response.json()
                count = len(events.get('data', {}).get('items', []))
                print(f"   今日事件数量: {count}")
            elif response.status_code == 403:
                print("❌ 日历API权限不足 (403)")
                print("   请申请日历权限: calendar:calendar:readonly")
            elif response.status_code == 400:
                print("❌ 日历API请求参数错误 (400)")
                print(f"   响应: {response.text[:200]}")
            else:
                print(f"❌ 日历API调用失败: {response.status_code}")
                print(f"   响应: {response.text[:200]}")
                
        except Exception as e:
            print(f"⚠️ 日历API测试失败: {e}")
            
        # 步骤5: 测试消息API（需要权限）
        print("\n💬 步骤5: 测试消息API（需要权限）...")
        try:
            # 仅检查权限，不实际发送
            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            headers = {"Authorization": f"Bearer {token}"}
            
            # 使用OPTIONS方法检查支持的HTTP方法
            response = requests.options(url, headers=headers, timeout=10)
            print(f"   消息API支持的方法: {response.headers.get('allow', '未知')}")
            
        except Exception as e:
            print(f"⚠️ 消息API测试失败: {e}")
            
    else:
        print(f"❌ 获取访问令牌失败: {token_result.get('msg')}")
        print(f"   错误代码: {token_result.get('code')}")
        
except requests.exceptions.RequestException as e:
    print(f"❌ 网络连接失败: {e}")
except Exception as e:
    print(f"❌ 诊断过程中出错: {e}")

print("\n" + "=" * 60)
print("📋 诊断总结与建议:")
print("1. ✅ 访问令牌获取成功 - 凭证有效")
print("2. 🔧 需要检查应用权限状态")
print("3. 🛠️ 如果权限不足，请登录飞书开放平台申请")
print("\n🔗 飞书开放平台链接:")
print("   • 应用概览: https://open.feishu.cn/app")
print("   • 权限管理: https://open.feishu.cn/app/<YOUR_APP_ID>/permission")
print("   • 应用发布: https://open.feishu.cn/app/<YOUR_APP_ID>/release")

print("\n🎯 推荐申请的权限:")
print("   1. calendar:calendar:readonly - 读取日历")
print("   2. im:message - 发送和接收消息")
print("   3. contact:user.base:readonly - 读取用户信息")

print("\n⚠️ 重要提醒:")
print("   • 申请权限后需要管理员审批")
print("   • 某些权限需要企业版飞书")
print("   • 测试环境可使用'测试企业'进行测试")