#!/usr/bin/env python
"""
API服务器启动脚本 - 生产环境就绪版
"""
import uvicorn
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 生产环境配置
def setup_environment():
    """设置生产环境配置"""
    # 加载环境变量
    from dotenv import load_dotenv
    env_file = os.environ.get("ENV_FILE", ".env")
    load_dotenv(env_file)
    
    # 设置默认配置
    os.environ.setdefault("PRODUCTION_MODE", "false")
    os.environ.setdefault("LOG_LEVEL", "INFO")
    
    # 检查必要环境变量
    required_vars = ["SECRET_KEY"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    if missing_vars and os.environ.get("PRODUCTION_MODE", "false").lower() == "true":
        print(f"错误: 生产环境缺少必要环境变量: {missing_vars}")
        sys.exit(1)


def setup_logging():
    """初始化日志系统"""
    try:
        from agent_iam.logger import setup_logging as setup_app_logging
        setup_app_logging()
    except ImportError as e:
        print(f"警告: 无法初始化日志系统: {e}")


def get_uvicorn_config():
    """获取Uvicorn配置"""
    # 生产环境配置
    production_mode = os.environ.get("PRODUCTION_MODE", "false").lower() == "true"
    
    if production_mode:
        return {
            "host": os.environ.get("API_HOST", "0.0.0.0"),
            "port": int(os.environ.get("API_PORT", 8000)),
            "reload": False,
            "log_level": os.environ.get("LOG_LEVEL", "info").lower(),
            "workers": int(os.environ.get("API_WORKERS", 4)),
            "access_log": True,
            "proxy_headers": True,
            "forwarded_allow_ips": "*"
        }
    else:
        # 开发环境配置
        return {
            "host": "0.0.0.0",
            "port": 8000,
            "reload": True,
            "log_level": "info",
            "workers": 1
        }


if __name__ == "__main__":
    # 环境设置
    setup_environment()
    
    # 日志初始化
    setup_logging()
    
    print("=" * 60)
    print("启动 AI Agent IAM API 服务器")
    print(f"环境: {'生产环境' if os.environ.get('PRODUCTION_MODE') == 'true' else '开发环境'}")
    print(f"主机: {os.environ.get('API_HOST', '0.0.0.0')}")
    print(f"端口: {os.environ.get('API_PORT', '8000')}")
    print(f"日志级别: {os.environ.get('LOG_LEVEL', 'INFO')}")
    print("=" * 60)
    print("文档地址: http://localhost:8000/docs")
    print("ReDoc地址: http://localhost:8000/redoc")
    print("健康检查: http://localhost:8000/health")
    print("按 Ctrl+C 停止服务器")
    
    # 获取配置并启动
    config = get_uvicorn_config()
    uvicorn.run(
        "agent_iam.api.app:app",
        **config
    )