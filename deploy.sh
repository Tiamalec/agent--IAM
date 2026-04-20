#!/bin/bash
# AI Agent IAM 部署脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🎯 AI Agent IAM 系统部署脚本${NC}"
echo "========================================"

# 检查参数
COMMAND=${1:-"help"}

case $COMMAND in
    "help")
        echo "用法: ./deploy.sh [command]"
        echo ""
        echo "命令:"
        echo "  help      - 显示帮助信息"
        echo "  install   - 安装依赖和配置"
        echo "  build     - 构建Docker镜像"
        echo "  start     - 启动服务"
        echo "  stop      - 停止服务"
        echo "  restart   - 重启服务"
        echo "  status    - 查看服务状态"
        echo "  demo      - 运行演示"
        echo "  test      - 运行测试"
        echo "  clean     - 清理临时文件"
        ;;
    
    "install")
        echo -e "${YELLOW}安装Python依赖...${NC}"
        pip install -r requirements.txt
        
        echo -e "${YELLOW}设置环境变量...${NC}"
        if [ ! -f .env ]; then
            cp .env.example .env
            echo -e "${GREEN}已创建.env文件，请编辑配置${NC}"
        else
            echo -e "${YELLOW}.env文件已存在${NC}"
        fi
        
        echo -e "${GREEN}✅ 安装完成${NC}"
        ;;
    
    "build")
        echo -e "${YELLOW}构建Docker镜像...${NC}"
        docker-compose build
        
        echo -e "${GREEN}✅ 镜像构建完成${NC}"
        ;;
    
    "start")
        echo -e "${YELLOW}启动服务...${NC}"
        docker-compose up -d
        
        echo -e "${GREEN}✅ 服务已启动${NC}"
        echo ""
        echo "服务访问:"
        echo "  - API文档: http://localhost:8000/docs"
        echo "  - 监控面板: http://localhost:8501"
        echo ""
        echo "查看日志: docker-compose logs -f"
        ;;
    
    "stop")
        echo -e "${YELLOW}停止服务...${NC}"
        docker-compose down
        
        echo -e "${GREEN}✅ 服务已停止${NC}"
        ;;
    
    "restart")
        echo -e "${YELLOW}重启服务...${NC}"
        docker-compose restart
        
        echo -e "${GREEN}✅ 服务已重启${NC}"
        ;;
    
    "status")
        echo -e "${YELLOW}服务状态:${NC}"
        docker-compose ps
        
        echo ""
        echo -e "${YELLOW}容器日志:${NC}"
        docker-compose logs --tail=10
        ;;
    
    "demo")
        echo -e "${YELLOW}运行演示...${NC}"
        
        # 检查是否安装依赖
        if ! command -v python &> /dev/null; then
            echo -e "${RED}错误: Python未安装${NC}"
            exit 1
        fi
        
        echo "选择演示类型:"
        echo "1. 基础演示"
        echo "2. 高级演示 (财务报告生成流水线)"
        echo "3. 比赛演示 (推荐)"
        echo "4. 安全演示"
        read -p "请输入选项 [1-4]: " choice
        
        case $choice in
            1)
                python -c "from agent_iam.demo import IAMDemo; demo = IAMDemo(); demo.run_full_demo()"
                ;;
            2)
                python -c "from agent_iam.advanced_demo import FinancialReportDemo; demo = FinancialReportDemo(); demo.run_full_demo()"
                ;;
            3)
                python competition_demo.py
                ;;
            4)
                echo -e "${YELLOW}运行安全演示...${NC}"
                python -c "
from agent_iam.advanced_demo import FinancialReportDemo
demo = FinancialReportDemo()
demo.demo_unauthorized_access_attempt()
demo.demo_token_expiration()
print('安全演示完成！')
"
                ;;
            *)
                echo -e "${RED}无效选项${NC}"
                ;;
        esac
        
        echo -e "${GREEN}✅ 演示完成${NC}"
        ;;
    
    "test")
        echo -e "${YELLOW}运行测试...${NC}"
        
        if ! command -v pytest &> /dev/null; then
            echo -e "${YELLOW}安装pytest...${NC}"
            pip install pytest
        fi
        
        python -m pytest tests/ -v
        
        echo -e "${GREEN}✅ 测试完成${NC}"
        ;;
    
    "clean")
        echo -e "${YELLOW}清理临时文件...${NC}"
        
        # 清理Python缓存
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -delete
        find . -type f -name "*.pyo" -delete
        find . -type f -name ".coverage" -delete
        find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
        
        # 清理审计日志
        rm -f *.jsonl 2>/dev/null || true
        
        echo -e "${GREEN}✅ 清理完成${NC}"
        ;;
    
    *)
        echo -e "${RED}未知命令: $COMMAND${NC}"
        echo "使用: ./deploy.sh help 查看可用命令"
        exit 1
        ;;
esac

echo ""