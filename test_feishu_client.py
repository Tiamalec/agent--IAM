#!/usr/bin/env python
"""
测试飞书客户端
"""
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

print("🧪 测试飞书客户端初始化")
print("=" * 50)

# 检查环境变量
app_id = os.environ.get("FEISHU_APP_ID")
app_secret = os.environ.get("FEISHU_APP_SECRET")
skills_enabled = os.environ.get("FEISHU_SKILLS_ENABLED", "true").lower() == "true"

print(f"FEISHU_APP_ID: {app_id[:10] if app_id else '未设置'}...")
print(f"FEISHU_APP_SECRET: {app_secret[:10] if app_secret else '未设置'}...")
print(f"FEISHU_SKILLS_ENABLED: {skills_enabled}")

# 导入模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from agent_iam.feishu_integration import FeishuAPIClient, REAL_API_AVAILABLE
    print(f"\n✅ 模块导入成功")
    print(f"REAL_API_AVAILABLE: {REAL_API_AVAILABLE}")
    
    # 创建客户端
    print("\n🔧 创建FeishuAPIClient...")
    client = FeishuAPIClient()
    
    print(f"use_real_api: {client.use_real_api}")
    print(f"real_client: {'已初始化' if client.real_client else '未初始化'}")
    
    if client.real_client:
        print("🎉 真实飞书API客户端初始化成功！")
        print(f"App ID: {client.real_client.app_id[:10]}...")
        
        # 测试获取访问令牌
        print("\n🔐 测试访问令牌...")
        try:
            token = client.real_client._get_tenant_access_token()
            if token:
                print(f"✅ 访问令牌获取成功: {token[:20]}...")
                
                # 测试一个简单的API调用
                print("\n🚀 测试API调用...")
                try:
                    # 测试日历API
                    result = client.execute_command("calendar", "agenda", {"date": "today"})
                    print(f"API调用结果: {result.get('success', False)}")
                    print(f"数据来源: {result.get('source', 'unknown')}")
                    
                    if result.get('success'):
                        print("🎉 真实飞书API调用成功！")
                    else:
                        print(f"⚠️ API调用失败: {result.get('error', '未知错误')}")
                        
                except Exception as e:
                    print(f"⚠️ API调用异常: {e}")
            else:
                print("❌ 无法获取访问令牌")
                
        except Exception as e:
            print(f"⚠️ 访问令牌测试失败: {e}")
    else:
        print("ℹ️ 使用模拟API模式")
        print("要使用真实API，请确保:")
        print("  1. FEISHU_APP_ID和FEISHU_APP_SECRET已配置")
        print("  2. FEISHU_SKILLS_ENABLED=true")
        print("  3. 飞书SDK已安装 (pip install lark-oapi)")
        
except ImportError as e:
    print(f"❌ 模块导入失败: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"❌ 测试过程中出错: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("📋 总结:")
if app_id and app_secret and skills_enabled:
    print("✅ 环境变量配置正确")
else:
    print("❌ 环境变量配置不完整")
    
# 检查飞书SDK安装
try:
    import lark_oapi
    print("✅ 飞书SDK已安装")
except ImportError:
    print("❌ 飞书SDK未安装")
    print("运行: pip install lark-oapi")