#!/usr/bin/env python
"""
测试真实飞书API连接
"""
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 检查飞书凭证
app_id = os.environ.get("FEISHU_APP_ID")
app_secret = os.environ.get("FEISHU_APP_SECRET")

print("🧪 测试真实飞书API连接")
print("=" * 50)

if not app_id or not app_secret:
    print("❌ 飞书凭证未配置")
    print("请在.env文件中设置:")
    print("  FEISHU_APP_ID=你的App ID")
    print("  FEISHU_APP_SECRET=你的App Secret")
    sys.exit(1)

print(f"✅ 找到飞书凭证")
print(f"   App ID: {app_id[:10]}...")
print(f"   App Secret: {app_secret[:10]}...")

# 尝试获取租户访问令牌
print("\n🔐 测试获取飞书访问令牌...")
try:
    import requests
    import time
    
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {"app_id": app_id, "app_secret": app_secret}
    
    response = requests.post(url, headers=headers, json=data, timeout=10)
    response.raise_for_status()
    
    result = response.json()
    
    if result.get("code") == 0:
        print("✅ 飞书API连接测试成功")
        print(f"   访问令牌获取成功")
        print(f"   令牌有效期: {result.get('expire', 0)}秒")
        
        # 测试IAM系统与飞书的集成
        print("\n🤖 测试IAM系统与飞书集成...")
        try:
            # 导入IAM模块
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            
            from agent_iam.feishu_integration import FeishuIntegration
            from agent_iam.models import Actor, ActorType
            
            # 初始化飞书集成
            integration = FeishuIntegration()
            
            # 创建测试Agent
            test_agent = Actor(name="测试AI助手", type=ActorType.MASTER_AGENT)
            
            # 查看支持的Skills
            skills = integration.list_available_skills()
            print(f"✅ IAM系统支持 {len(skills)} 个飞书Skills")
            
            # 测试API调用（使用真实API）
            print("\n🚀 测试真实飞书API调用...")
            
            # 由于真实API需要具体的权限和配置，我们先测试连接
            # 实际调用需要在飞书开放平台配置相应权限
            print("📋 飞书API权限检查:")
            print("   1. 确保应用已在飞书开放平台发布")
            print("   2. 检查应用权限是否已申请并通过")
            print("   3. 确认租户管理员已授权")
            
            # 简单的API调用测试
            print("\n🔧 测试基础API调用...")
            try:
                # 测试获取用户信息（需要contact权限）
                from agent_iam.feishu_integration import FeishuSkill
                
                # 尝试执行一个简单的飞书命令
                from agent_iam.feishu_real_client import RealFeishuAPIClient
                
                client = RealFeishuAPIClient(app_id, app_secret)
                print("✅ 真实飞书API客户端创建成功")
                
                # 测试获取租户访问令牌
                token = client._get_tenant_access_token()
                if token:
                    print(f"✅ 租户访问令牌获取成功: {token[:20]}...")
                    
                    # 测试一个简单的API
                    print("📅 测试日历API...")
                    try:
                        # 获取今天的事件（需要日历权限）
                        today = "2024-01-01"  # 占位日期
                        result = client.get_calendar_events(start_time=f"{today}T00:00:00+08:00")
                        print(f"✅ 日历API调用成功")
                    except Exception as e:
                        print(f"⚠️ 日历API调用失败（可能需要权限）: {e}")
                        
                else:
                    print("❌ 无法获取访问令牌")
                    
            except Exception as e:
                print(f"⚠️ API客户端测试失败: {e}")
                print("这可能是因为:")
                print("  1. 应用未发布或未授权")
                print("  2. 缺少必要的API权限")
                print("  3. 网络或配置问题")
            
        except ImportError as e:
            print(f"⚠️ IAM模块导入失败: {e}")
            print("请确保在项目根目录运行此脚本")
        except Exception as e:
            print(f"⚠️ IAM集成测试失败: {e}")
            
    else:
        print(f"❌ 飞书API错误: {result.get('msg', '未知错误')}")
        print(f"   错误代码: {result.get('code')}")
        
except requests.exceptions.RequestException as e:
    print(f"❌ 网络连接失败: {e}")
    print("请检查网络连接和代理设置")
except Exception as e:
    print(f"❌ 测试过程中出错: {e}")

print("\n" + "=" * 50)
print("📋 下一步行动:")
print("1. 登录飞书开放平台 (https://open.feishu.cn)")
print("2. 检查应用状态和权限")
print("3. 发布应用并获取管理员授权")
print("4. 运行完整测试: python feishu_demo.py")
print("\n💡 提示: 如果权限不足，请先申请以下权限:")
print("   • contact:user.base:readonly (读取用户信息)")
print("   • im:message (发送消息)")
print("   • calendar:calendar:readonly (读取日历)")