#!/bin/bash
# AI Agent IAM 生产环境部署脚本
# 用于生产环境部署和运维

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
PROJECT_NAME="agent-iam"
ENV_FILE=".env.production"
DOCKER_COMPOSE_FILE="docker-compose.production.yml"
BACKUP_DIR="./backups"

# 显示标题
function print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}   AI Agent IAM 生产环境部署系统   ${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# 检查命令是否存在
function check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}错误: 未找到命令 '$1'${NC}"
        echo -e "请安装 $1 后再运行此脚本"
        exit 1
    fi
}

# 初始化生产环境
function init_production() {
    echo -e "${YELLOW}初始化生产环境...${NC}"
    
    # 检查Docker和Docker Compose
    check_command docker
    check_command docker-compose
    
    # 创建生产环境配置文件
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example "$ENV_FILE"
            echo -e "${GREEN}已创建生产环境配置文件: $ENV_FILE${NC}"
            echo -e "${YELLOW}请编辑 $ENV_FILE 配置生产环境参数${NC}"
        else
            echo -e "${RED}错误: 找不到 .env.example 文件${NC}"
            exit 1
        fi
    fi
    
    # 创建备份目录
    mkdir -p "$BACKUP_DIR"
    
    # 创建生产环境docker-compose文件
    if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
        create_production_compose
    fi
    
    echo -e "${GREEN}✅ 生产环境初始化完成${NC}"
}

# 创建生产环境docker-compose文件
function create_production_compose() {
    cat > "$DOCKER_COMPOSE_FILE" << 'EOF'
# AI Agent IAM 生产环境配置
version: '3.8'

services:
  # Redis缓存服务
  redis:
    image: redis:7-alpine
    container_name: ${PROJECT_NAME}-redis
    restart: always
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:-ChangeMe123}
    volumes:
      - redis_data:/data
    networks:
      - agent-iam-network
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD:-ChangeMe123}", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # PostgreSQL数据库（可选）
  postgres:
    image: postgres:15-alpine
    container_name: ${PROJECT_NAME}-postgres
    restart: always
    environment:
      POSTGRES_DB: ${DB_NAME:-agent_iam}
      POSTGRES_USER: ${DB_USER:-agent_iam}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-ChangeMe123}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./initdb:/docker-entrypoint-initdb.d
    networks:
      - agent-iam-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-agent_iam}"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # AI Agent IAM API服务
  api:
    build:
      context: .
      dockerfile: Dockerfile.production
    container_name: ${PROJECT_NAME}-api
    restart: always
    depends_on:
      redis:
        condition: service_healthy
    environment:
      - PRODUCTION_MODE=true
      - SECRET_KEY=${SECRET_KEY}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - DB_URL=postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
      - FEISHU_APP_ID=${FEISHU_APP_ID}
      - FEISHU_APP_SECRET=${FEISHU_APP_SECRET}
      - SENTRY_DSN=${SENTRY_DSN}
    volumes:
      - audit_logs:/data/audit_logs
      - ./logs:/app/logs
    ports:
      - "${API_PORT:-8000}:8000"
    networks:
      - agent-iam-network
      - agent-iam-frontend
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health', timeout=2)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.${PROJECT_NAME}-api.rule=Host(`${API_DOMAIN:-api.agent-iam.example.com}`)"
      - "traefik.http.services.${PROJECT_NAME}-api.loadbalancer.server.port=8000"

  # Nginx反向代理（可选）
  nginx:
    image: nginx:alpine
    container_name: ${PROJECT_NAME}-nginx
    restart: always
    depends_on:
      - api
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    ports:
      - "80:80"
      - "443:443"
    networks:
      - agent-iam-frontend

  # 监控服务（Prometheus + Grafana）
  monitoring:
    image: prom/prometheus:latest
    container_name: ${PROJECT_NAME}-monitoring
    restart: always
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - agent-iam-network

  # 日志收集（Fluentd + ELK可选）
  # logstash:
  #   image: docker.elastic.co/logstash/logstash:8.11.0
  #   container_name: ${PROJECT_NAME}-logstash
  #   restart: always
  #   volumes:
  #     - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
  #     - ./logs:/logs
  #   networks:
  #     - agent-iam-network

volumes:
  redis_data:
    driver: local
  postgres_data:
    driver: local
  audit_logs:
    driver: local
  prometheus_data:
    driver: local

networks:
  agent-iam-network:
    driver: bridge
  agent-iam-frontend:
    driver: bridge
EOF
    
    echo -e "${GREEN}已创建生产环境docker-compose文件: $DOCKER_COMPOSE_FILE${NC}"
    
    # 创建生产环境Dockerfile
    if [ ! -f "Dockerfile.production" ]; then
        create_production_dockerfile
    fi
}

# 创建生产环境Dockerfile
function create_production_dockerfile() {
    cat > "Dockerfile.production" << 'EOF'
# 生产环境多阶段构建
# 构建阶段
FROM python:3.11-slim as builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装依赖到虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 运行阶段
FROM python:3.11-slim

# 创建非root用户
RUN useradd -m -u 1000 appuser

# 设置工作目录
WORKDIR /app

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 复制应用代码
COPY --chown=appuser:appuser . .

# 设置环境变量
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PRODUCTION_MODE=true

# 切换到非root用户
USER appuser

# 创建数据目录
RUN mkdir -p /data/audit_logs /app/logs

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=2)" || exit 1

# 运行命令
CMD ["python", "run_api.py"]

# 标签
LABEL maintainer="AI Agent IAM Team" \
      description="AI Agent Identity and Access Management System - Production" \
      version="1.0.0" \
      license="MIT"
EOF
    
    echo -e "${GREEN}已创建生产环境Dockerfile: Dockerfile.production${NC}"
}

# 构建生产环境镜像
function build_production() {
    echo -e "${YELLOW}构建生产环境镜像...${NC}"
    
    # 加载环境变量
    if [ -f "$ENV_FILE" ]; then
        export $(grep -v '^#' "$ENV_FILE" | xargs)
    fi
    
    # 构建镜像
    docker-compose -f "$DOCKER_COMPOSE_FILE" build --no-cache
    
    echo -e "${GREEN}✅ 生产环境镜像构建完成${NC}"
}

# 部署生产环境
function deploy_production() {
    echo -e "${YELLOW}部署生产环境服务...${NC}"
    
    # 停止现有服务
    docker-compose -f "$DOCKER_COMPOSE_FILE" down || true
    
    # 启动服务
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
    
    # 等待服务启动
    echo -e "${YELLOW}等待服务启动...${NC}"
    sleep 30
    
    # 检查服务状态
    check_services
    
    echo -e "${GREEN}✅ 生产环境部署完成${NC}"
}

# 检查服务状态
function check_services() {
    echo -e "${YELLOW}检查服务状态...${NC}"
    
    # 检查API健康状态
    API_URL="http://localhost:${API_PORT:-8000}/health"
    echo -n "检查API服务 ($API_URL)... "
    if curl -s -f "$API_URL" > /dev/null; then
        echo -e "${GREEN}正常${NC}"
    else
        echo -e "${RED}异常${NC}"
        docker-compose -f "$DOCKER_COMPOSE_FILE" logs api
        exit 1
    fi
    
    # 检查Redis
    echo -n "检查Redis服务... "
    if docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T redis redis-cli -a "${REDIS_PASSWORD:-ChangeMe123}" ping | grep -q PONG; then
        echo -e "${GREEN}正常${NC}"
    else
        echo -e "${RED}异常${NC}"
    fi
    
    # 显示容器状态
    echo ""
    echo -e "${YELLOW}容器状态:${NC}"
    docker-compose -f "$DOCKER_COMPOSE_FILE" ps
}

# 备份数据
function backup_data() {
    echo -e "${YELLOW}备份数据...${NC}"
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/backup_${TIMESTAMP}.tar.gz"
    
    # 备份审计日志
    mkdir -p "$BACKUP_DIR/temp"
    cp -r ./audit_logs/*.jsonl "$BACKUP_DIR/temp/" 2>/dev/null || true
    
    # 备份数据库（如果启用）
    if docker-compose -f "$DOCKER_COMPOSE_FILE" ps postgres | grep -q "Up"; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T postgres pg_dumpall -U "${DB_USER:-agent_iam}" > "$BACKUP_DIR/temp/database.sql"
    fi
    
    # 创建压缩包
    tar -czf "$BACKUP_FILE" -C "$BACKUP_DIR/temp" .
    rm -rf "$BACKUP_DIR/temp"
    
    echo -e "${GREEN}✅ 数据备份完成: $BACKUP_FILE${NC}"
}

# 恢复数据
function restore_data() {
    echo -e "${YELLOW}恢复数据...${NC}"
    
    if [ -z "$1" ]; then
        echo -e "${RED}请指定备份文件${NC}"
        echo "用法: ./deploy-prod.sh restore <备份文件>"
        exit 1
    fi
    
    BACKUP_FILE="$1"
    if [ ! -f "$BACKUP_FILE" ]; then
        echo -e "${RED}备份文件不存在: $BACKUP_FILE${NC}"
        exit 1
    fi
    
    # 创建临时目录
    TEMP_DIR="$BACKUP_DIR/temp_restore"
    mkdir -p "$TEMP_DIR"
    
    # 解压备份文件
    tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"
    
    # 恢复审计日志
    if [ -f "$TEMP_DIR"/*.jsonl ]; then
        cp "$TEMP_DIR"/*.jsonl ./audit_logs/ 2>/dev/null || true
    fi
    
    # 恢复数据库（如果启用）
    if [ -f "$TEMP_DIR/database.sql" ]; then
        if docker-compose -f "$DOCKER_COMPOSE_FILE" ps postgres | grep -q "Up"; then
            docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T postgres psql -U "${DB_USER:-agent_iam}" -f /tmp/database.sql
            docker-compose -f "$DOCKER_COMPOSE_FILE" cp "$TEMP_DIR/database.sql" postgres:/tmp/
        fi
    fi
    
    rm -rf "$TEMP_DIR"
    
    echo -e "${GREEN}✅ 数据恢复完成${NC}"
}

# 查看日志
function view_logs() {
    echo -e "${YELLOW}查看服务日志...${NC}"
    
    if [ -z "$1" ]; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=100 -f
    else
        docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=100 -f "$1"
    fi
}

# 显示帮助
function show_help() {
    print_header
    echo "用法: ./deploy-prod.sh [命令]"
    echo ""
    echo "生产环境部署命令:"
    echo "  init             初始化生产环境配置"
    echo "  build            构建生产环境镜像"
    echo "  deploy           部署生产环境服务"
    echo "  restart          重启生产环境服务"
    echo "  stop             停止生产环境服务"
    echo "  status           查看服务状态"
    echo "  logs [服务名]    查看服务日志"
    echo "  backup           备份数据"
    echo "  restore <文件>   恢复数据"
    echo "  monitor          监控服务状态"
    echo "  help             显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  ./deploy-prod.sh init     # 初始化生产环境"
    echo "  ./deploy-prod.sh build    # 构建镜像"
    echo "  ./deploy-prod.sh deploy   # 部署服务"
    echo ""
}

# 监控服务状态
function monitor_services() {
    echo -e "${YELLOW}监控服务状态...${NC}"
    
    while true; do
        clear
        print_header
        echo -e "${YELLOW}服务状态监控 (按Ctrl+C退出)${NC}"
        echo ""
        
        # 显示容器状态
        docker-compose -f "$DOCKER_COMPOSE_FILE" ps
        
        echo ""
        echo -e "${YELLOW}资源使用情况:${NC}"
        docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}" | head -10
        
        echo ""
        echo -e "${YELLOW}最近日志:${NC}"
        docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=5
        
        sleep 10
    done
}

# 主程序
print_header

COMMAND=${1:-"help"}

case $COMMAND in
    "init")
        init_production
        ;;
    "build")
        build_production
        ;;
    "deploy")
        deploy_production
        ;;
    "restart")
        docker-compose -f "$DOCKER_COMPOSE_FILE" restart
        echo -e "${GREEN}✅ 服务已重启${NC}"
        ;;
    "stop")
        docker-compose -f "$DOCKER_COMPOSE_FILE" down
        echo -e "${GREEN}✅ 服务已停止${NC}"
        ;;
    "status")
        check_services
        ;;
    "logs")
        view_logs "$2"
        ;;
    "backup")
        backup_data
        ;;
    "restore")
        restore_data "$2"
        ;;
    "monitor")
        monitor_services
        ;;
    "help")
        show_help
        ;;
    *)
        echo -e "${RED}未知命令: $COMMAND${NC}"
        show_help
        exit 1
        ;;
esac

echo ""