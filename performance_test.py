#!/usr/bin/env python
"""
IAM系统性能测试脚本
测试API端点的性能和并发处理能力
"""
import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict, Any
import json
import sys

class PerformanceTester:
    """性能测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.results = []
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def test_endpoint(self, endpoint: str, method: str = "GET", 
                           payload: Dict = None, headers: Dict = None,
                           iterations: int = 100, concurrency: int = 10) -> Dict[str, Any]:
        """
        测试单个端点
        
        Args:
            endpoint: API端点路径
            method: HTTP方法
            payload: 请求负载
            headers: 请求头
            iterations: 总请求次数
            concurrency: 并发数
            
        Returns:
            测试结果
        """
        print(f"\n🔧 测试端点: {endpoint}")
        print(f"   方法: {method}, 迭代: {iterations}, 并发: {concurrency}")
        
        url = f"{self.base_url}{endpoint}"
        semaphore = asyncio.Semaphore(concurrency)
        
        async def make_request():
            async with semaphore:
                start_time = time.time()
                try:
                    if method == "GET":
                        async with self.session.get(url, headers=headers) as response:
                            status = response.status
                            await response.read()
                    elif method == "POST":
                        async with self.session.post(url, json=payload, headers=headers) as response:
                            status = response.status
                            await response.read()
                    elif method == "PUT":
                        async with self.session.put(url, json=payload, headers=headers) as response:
                            status = response.status
                            await response.read()
                    else:
                        return None, None
                    
                    end_time = time.time()
                    duration = (end_time - start_time) * 1000  # 转换为毫秒
                    return status, duration
                    
                except Exception as e:
                    end_time = time.time()
                    duration = (end_time - start_time) * 1000
                    return None, duration
        
        # 执行并发请求
        start_time = time.time()
        tasks = [make_request() for _ in range(iterations)]
        responses = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # 分析结果
        durations = []
        success_count = 0
        error_count = 0
        status_codes = {}
        
        for status, duration in responses:
            if duration is not None:
                durations.append(duration)
            
            if status and 200 <= status < 300:
                success_count += 1
                status_codes[status] = status_codes.get(status, 0) + 1
            else:
                error_count += 1
        
        if durations:
            result = {
                "endpoint": endpoint,
                "method": method,
                "total_requests": iterations,
                "success_requests": success_count,
                "error_requests": error_count,
                "success_rate": (success_count / iterations) * 100 if iterations > 0 else 0,
                "total_time_seconds": total_time,
                "requests_per_second": iterations / total_time if total_time > 0 else 0,
                "avg_response_time_ms": statistics.mean(durations),
                "min_response_time_ms": min(durations) if durations else 0,
                "max_response_time_ms": max(durations) if durations else 0,
                "p50_response_time_ms": statistics.median(durations) if durations else 0,
                "p95_response_time_ms": statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else 0,
                "p99_response_time_ms": statistics.quantiles(durations, n=100)[98] if len(durations) >= 100 else 0,
                "status_codes": status_codes,
                "timestamp": time.time()
            }
        else:
            result = {
                "endpoint": endpoint,
                "method": method,
                "total_requests": iterations,
                "success_requests": success_count,
                "error_requests": error_count,
                "success_rate": 0,
                "error": "所有请求都失败了",
                "timestamp": time.time()
            }
        
        self.results.append(result)
        self._print_result(result)
        return result
    
    def _print_result(self, result: Dict[str, Any]):
        """打印测试结果"""
        print(f"✅ 测试完成:")
        print(f"   总请求数: {result['total_requests']}")
        print(f"   成功请求: {result['success_requests']}")
        print(f"   失败请求: {result['error_requests']}")
        print(f"   成功率: {result['success_rate']:.2f}%")
        
        if 'error' not in result:
            print(f"   总时间: {result['total_time_seconds']:.2f}秒")
            print(f"   请求/秒: {result['requests_per_second']:.2f}")
            print(f"   平均响应时间: {result['avg_response_time_ms']:.2f}ms")
            print(f"   最小响应时间: {result['min_response_time_ms']:.2f}ms")
            print(f"   最大响应时间: {result['max_response_time_ms']:.2f}ms")
            print(f"   P50响应时间: {result['p50_response_time_ms']:.2f}ms")
            print(f"   P95响应时间: {result['p95_response_time_ms']:.2f}ms")
            print(f"   P99响应时间: {result['p99_response_time_ms']:.2f}ms")
        
        if result.get('status_codes'):
            print(f"   状态码分布: {result['status_codes']}")
        
        print()
    
    def save_results(self, filename: str = "performance_results.json"):
        """保存测试结果到文件"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                "test_timestamp": time.time(),
                "base_url": self.base_url,
                "results": self.results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"📊 测试结果已保存到: {filename}")

async def run_performance_tests():
    """运行性能测试套件"""
    print("🚀 IAM系统性能测试")
    print("=" * 60)
    
    async with PerformanceTester() as tester:
        # 测试健康检查端点
        await tester.test_endpoint("/health", "GET", iterations=100, concurrency=10)
        
        # 测试根端点
        await tester.test_endpoint("/", "GET", iterations=100, concurrency=10)
        
        # 测试获取参与者列表（需要令牌）
        # 注意：这里需要有效的Token，实际测试时需要先获取Token
        # headers = {"Authorization": "Bearer your_token_here"}
        # await tester.test_endpoint("/actors", "GET", headers=headers, iterations=50, concurrency=5)
        
        # 测试飞书授权URL端点
        await tester.test_endpoint("/feishu/auth/url", "GET", iterations=50, concurrency=5)
        
        # 测试权限映射端点（需要令牌）
        # payload = {"skill": "lark-calendar", "action": "read", "resource": "calendar"}
        # await tester.test_endpoint("/feishu/permissions/map", "POST", payload=payload, headers=headers, iterations=50, concurrency=5)
        
        # 保存结果
        tester.save_results()
    
    print("🎉 性能测试完成！")
    print("\n📈 性能指标参考:")
    print("   - 健康检查端点: < 50ms")
    print("   - 简单API端点: < 100ms")
    print("   - 复杂API端点: < 300ms")
    print("   - 成功率: > 99%")
    print("   - 并发处理: 支持10-100并发")

async def run_load_test():
    """运行负载测试（高并发）"""
    print("\n🔥 负载测试 - 高并发场景")
    print("=" * 60)
    
    async with PerformanceTester() as tester:
        # 高并发测试健康检查端点
        await tester.test_endpoint("/health", "GET", iterations=1000, concurrency=100)
        
        # 保存结果
        tester.save_results("load_test_results.json")

async def run_stress_test():
    """运行压力测试（长时间运行）"""
    print("\n⚡ 压力测试 - 长时间运行")
    print("=" * 60)
    
    async with PerformanceTester() as tester:
        results = []
        
        # 连续运行5轮，每轮间隔10秒
        for i in range(5):
            print(f"\n🔄 第 {i+1}/5 轮压力测试")
            result = await tester.test_endpoint("/health", "GET", iterations=200, concurrency=20)
            results.append(result)
            
            if i < 4:
                await asyncio.sleep(10)  # 等待10秒
        
        # 分析多轮测试结果
        if results and 'avg_response_time_ms' in results[0]:
            avg_times = [r['avg_response_time_ms'] for r in results]
            print(f"\n📊 压力测试总结:")
            print(f"   平均响应时间变化: {min(avg_times):.2f}ms → {max(avg_times):.2f}ms")
            print(f"   响应时间稳定性: {statistics.stdev(avg_times) if len(avg_times) > 1 else 0:.2f}ms")
        
        tester.save_results("stress_test_results.json")

def generate_report():
    """生成性能测试报告"""
    try:
        with open("performance_results.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print("\n📋 性能测试报告")
        print("=" * 60)
        print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(data['test_timestamp']))}")
        print(f"测试地址: {data['base_url']}")
        print()
        
        for result in data['results']:
            print(f"🔹 {result['endpoint']} ({result['method']})")
            print(f"   成功率: {result['success_rate']:.2f}%")
            if 'avg_response_time_ms' in result:
                print(f"   平均响应时间: {result['avg_response_time_ms']:.2f}ms")
                print(f"   P95响应时间: {result.get('p95_response_time_ms', 0):.2f}ms")
                print(f"   吞吐量: {result['requests_per_second']:.2f} req/s")
            print()
        
        print("✅ 性能评估:")
        print("   - 所有端点成功率应 > 99%")
        print("   - 响应时间P95应 < 500ms")
        print("   - 系统应支持至少10并发")
        
    except FileNotFoundError:
        print("❌ 未找到性能测试结果文件")
    except Exception as e:
        print(f"❌ 生成报告时出错: {e}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="IAM系统性能测试工具")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API基础URL")
    parser.add_argument("--test-type", choices=["performance", "load", "stress", "all", "report"], 
                       default="performance", help="测试类型")
    parser.add_argument("--iterations", type=int, default=100, help="请求迭代次数")
    parser.add_argument("--concurrency", type=int, default=10, help="并发数")
    parser.add_argument("--save-results", action="store_true", help="保存测试结果")
    
    args = parser.parse_args()
    
    async def run_tests():
        if args.test_type == "performance":
            async with PerformanceTester(args.base_url) as tester:
                await tester.test_endpoint("/health", "GET", iterations=args.iterations, concurrency=args.concurrency)
                if args.save_results:
                    tester.save_results()
        
        elif args.test_type == "load":
            await run_load_test()
        
        elif args.test_type == "stress":
            await run_stress_test()
        
        elif args.test_type == "all":
            await run_performance_tests()
            await run_load_test()
            await run_stress_test()
        
        elif args.test_type == "report":
            generate_report()
    
    # 运行异步测试
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\n❌ 测试被用户中断")
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()