#!/usr/bin/env python3
"""
飞书集成兼容性测试
测试不同网络环境和飞书版本下的稳定性
"""
import time
import random
from datetime import datetime
from agent_iam.feishu_integration import FeishuAPIClient


def test_network_latency():
    """测试不同网络延迟下的性能"""
    print("\n=== 测试网络延迟兼容性 ===")
    
    client = FeishuAPIClient()
    
    # 模拟不同网络延迟
    latencies = [0.1, 0.5, 1.0, 2.0]  # 秒
    
    for latency in latencies:
        print(f"\n测试延迟: {latency}秒")
        
        # 模拟网络延迟
        original_execute = client._execute_simulated
        
        def delayed_execute(cmd_type, subcmd, params):
            time.sleep(latency)
            return original_execute(cmd_type, subcmd, params)
        
        client._execute_simulated = delayed_execute
        
        # 测试API调用
        start_time = time.time()
        result = client.execute_command("calendar", "list_events", {"start_date": "2024-01-01", "end_date": "2024-01-31"})
        actual_time = time.time() - start_time
        
        print(f"API调用时间: {actual_time:.2f}秒 (预期: ~{latency:.2f}秒)")
        print(f"调用成功: {result.get('success', False)}")


def test_api_versions():
    """测试不同飞书API版本的兼容性"""
    print("\n=== 测试API版本兼容性 ===")
    
    client = FeishuAPIClient()
    
    # 模拟不同API版本
    api_versions = ["v1", "v2", "v3"]
    
    for version in api_versions:
        print(f"\n测试API版本: {version}")
        
        # 测试不同版本的命令格式
        result = client.execute_command(
            "calendar", 
            f"list_events_{version}", 
            {"start_date": "2024-01-01", "end_date": "2024-01-31", "api_version": version}
        )
        
        print(f"调用结果: {result}")
        print(f"调用成功: {result.get('success', False)}")


def test_edge_cases():
    """测试边界情况"""
    print("\n=== 测试边界情况 ===")
    
    client = FeishuAPIClient()
    
    # 测试用例
    edge_cases = [
        # 空参数
        ("calendar", "list_events", {}),
        # 大量参数
        ("calendar", "list_events", {"start_date": "2024-01-01", "end_date": "2024-12-31", "page_size": 100, "page_token": "test_token", "filter": "all"}),
        # 特殊字符
        ("docs", "search", {"query": "测试 特殊字符 !@#$%^&*()"}),
        # 超长参数
        ("docs", "create", {"title": "a" * 1000, "content": "b" * 5000}),
    ]
    
    for cmd_type, subcmd, params in edge_cases:
        print(f"\n测试: {cmd_type}:{subcmd} (参数长度: {len(str(params))}字符)")
        
        try:
            start_time = time.time()
            result = client.execute_command(cmd_type, subcmd, params)
            execution_time = time.time() - start_time
            
            print(f"执行时间: {execution_time:.4f}秒")
            print(f"调用成功: {result.get('success', False)}")
        except Exception as e:
            print(f"异常: {e}")


def test_error_recovery():
    """测试错误恢复能力"""
    print("\n=== 测试错误恢复能力 ===")
    
    client = FeishuAPIClient()
    
    # 模拟网络错误
    print("测试网络错误恢复...")
    
    # 模拟网络错误的执行函数
    def error_execute(cmd_type, subcmd, params):
        # 随机抛出异常
        if random.random() < 0.5:
            raise Exception("模拟网络错误")
        return {"success": True, "data": {"message": "模拟执行成功"}}
    
    original_execute = client._execute_simulated
    client._execute_simulated = error_execute
    
    # 测试多次调用
    success_count = 0
    total_count = 10
    
    for i in range(total_count):
        try:
            result = client.execute_command("calendar", "list_events", {"start_date": "2024-01-01", "end_date": "2024-01-31"})
            if result.get('success', False):
                success_count += 1
            print(f"尝试 {i+1}/{total_count}: {'成功' if result.get('success', False) else '失败'}")
        except Exception as e:
            print(f"尝试 {i+1}/{total_count}: 异常 - {e}")
    
    print(f"\n错误恢复测试结果: {success_count}/{total_count} 成功")


def test_concurrent_edge_cases():
    """测试并发边界情况"""
    print("\n=== 测试并发边界情况 ===")
    
    client = FeishuAPIClient()
    
    # 测试高并发
    import concurrent.futures
    
    def test_task(task_id):
        try:
            result = client.execute_command(
                "calendar", 
                "list_events", 
                {"start_date": "2024-01-01", "end_date": "2024-01-31", "task_id": task_id}
            )
            return task_id, result.get('success', False)
        except Exception as e:
            return task_id, False
    
    # 测试不同并发数
    concurrency_levels = [5, 10, 20]
    
    for concurrency in concurrency_levels:
        print(f"\n测试并发数: {concurrency}")
        
        start_time = time.time()
        success_count = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(test_task, i) for i in range(concurrency)]
            
            for future in concurrent.futures.as_completed(futures):
                task_id, success = future.result()
                if success:
                    success_count += 1
        
        execution_time = time.time() - start_time
        print(f"执行时间: {execution_time:.2f}秒")
        print(f"成功率: {success_count}/{concurrency}")


if __name__ == "__main__":
    print("🚀 开始飞书集成兼容性测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_network_latency()
    test_api_versions()
    test_edge_cases()
    test_error_recovery()
    test_concurrent_edge_cases()
    
    print("\n✅ 兼容性测试完成")
