#!/usr/bin/env python3
"""
飞书集成性能测试
测试缓存和并发处理的优化效果
"""
import time
import concurrent.futures
from datetime import datetime
from agent_iam.feishu_integration import FeishuAPIClient


def test_cache_performance():
    """测试缓存性能"""
    print("\n=== 测试缓存性能 ===")
    
    client = FeishuAPIClient()
    
    # 测试参数
    command_type = "calendar"
    subcommand = "list_events"
    params = {"start_date": "2024-01-01", "end_date": "2024-01-31"}
    
    # 第一次调用（无缓存）
    start_time = time.time()
    result1 = client.execute_command(command_type, subcommand, params)
    time_without_cache = time.time() - start_time
    print(f"第一次调用（无缓存）: {time_without_cache:.4f}秒")
    
    # 第二次调用（有缓存）
    start_time = time.time()
    result2 = client.execute_command(command_type, subcommand, params)
    time_with_cache = time.time() - start_time
    print(f"第二次调用（有缓存）: {time_with_cache:.4f}秒")
    
    # 计算性能提升
    if time_without_cache > 0:
        improvement = ((time_without_cache - time_with_cache) / time_without_cache) * 100
        print(f"性能提升: {improvement:.2f}%")
    
    # 验证结果一致性
    print(f"结果一致: {result1 == result2}")


def test_concurrent_performance():
    """测试并发性能"""
    print("\n=== 测试并发性能 ===")
    
    client = FeishuAPIClient()
    
    # 测试命令
    test_commands = [
        ("calendar", "list_events", {"start_date": "2024-01-01", "end_date": "2024-01-31"}),
        ("todo", "list_tasks", {"status": "pending"}),
        ("docs", "list_documents", {"folder_id": "root"}),
        ("meeting", "list_meetings", {"start_date": "2024-01-01", "end_date": "2024-01-31"}),
        ("user", "get_profile", {"user_id": "test_user"}),
    ]
    
    # 串行执行
    start_time = time.time()
    for cmd_type, subcmd, params in test_commands:
        client.execute_command(cmd_type, subcmd, params)
    serial_time = time.time() - start_time
    print(f"串行执行时间: {serial_time:.4f}秒")
    
    # 并发执行
    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for cmd_type, subcmd, params in test_commands:
            futures.append(executor.submit(client.execute_command, cmd_type, subcmd, params))
        
        # 等待所有任务完成
        for future in concurrent.futures.as_completed(futures):
            future.result()
    concurrent_time = time.time() - start_time
    print(f"并发执行时间: {concurrent_time:.4f}秒")
    
    # 计算性能提升
    if serial_time > 0:
        improvement = ((serial_time - concurrent_time) / serial_time) * 100
        print(f"并发性能提升: {improvement:.2f}%")


def test_error_handling_performance():
    """测试错误处理性能"""
    print("\n=== 测试错误处理性能 ===")
    
    client = FeishuAPIClient()
    
    # 测试错误命令
    error_commands = [
        ("invalid", "command", {}),
        ("calendar", "invalid", {}),
        ("user", "get_profile", {"invalid_param": "value"}),
    ]
    
    start_time = time.time()
    for cmd_type, subcmd, params in error_commands:
        result = client.execute_command(cmd_type, subcmd, params)
        # 验证错误处理 - 模拟模式下可能返回成功，但应该有错误信息
        print(f"命令 {cmd_type}:{subcmd} 结果: {result}")
    error_handling_time = time.time() - start_time
    print(f"错误处理时间: {error_handling_time:.4f}秒")
    print(f"平均错误处理时间: {error_handling_time / len(error_commands):.4f}秒")


def test_cache_effectiveness():
    """测试缓存有效性"""
    print("\n=== 测试缓存有效性 ===")
    
    client = FeishuAPIClient()
    
    # 测试多次调用
    command_type = "calendar"
    subcommand = "list_events"
    params = {"start_date": "2024-01-01", "end_date": "2024-01-31"}
    
    times = []
    for i in range(10):
        start_time = time.time()
        client.execute_command(command_type, subcommand, params)
        times.append(time.time() - start_time)
    
    print(f"10次调用时间: {times}")
    print(f"平均时间: {sum(times) / len(times):.4f}秒")
    print(f"最小时间: {min(times):.4f}秒")
    print(f"最大时间: {max(times):.4f}秒")


if __name__ == "__main__":
    print("🚀 开始飞书集成性能测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_cache_performance()
    test_concurrent_performance()
    test_error_handling_performance()
    test_cache_effectiveness()
    
    print("\n✅ 性能测试完成")
