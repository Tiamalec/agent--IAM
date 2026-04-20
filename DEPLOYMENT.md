# AI Agent IAM 系统 - 部署和配置指南

## 📋 目录
1. [系统概述](#系统概述)
2. [快速开始](#快速开始)
3. [环境配置](#环境配置)
4. [飞书集成配置](#飞书集成配置)
5. [数据库配置](#数据库配置)
6. [部署方式](#部署方式)
7. [监控和维护](#监控和维护)
8. [故障排除](#故障排除)

## 🎯 系统概述

AI Agent IAM（身份与访问管理）系统是一个企业级的身份认证和权限管理平台，专门为AI Agent和人类用户设计。系统与飞书平台深度集成，提供：

- 🔐 **单点登录（SSO）**：通过飞书OAuth2.0登录
- 🏢 **组织架构同步**：自动同步飞书部门和用户信息
- 🔧 **权限映射**：将飞书Skills映射到IAM Scopes
- 📊 **审计日志**：完整记录所有操作
- 🚀 **API接口**：RESTful API供其他系统调用

## 🚀 快速开始

### 1. 克隆代码库
```bash
git clone <repository-url>
cd xinzijie
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，配置必要的参数
```

### 4. 启动开发服务器
```bash
# 启动FastAPI服务器
uvicorn agent_iam.api.app:app --reload --host 0.0.0.0 --port 8000
```

### 5. 访问API文档
打开浏览器访问：http://localhost:8000/docs

## ⚙️ 环境配置

详细的环境变量说明请参考 [.env.example](.env.example) 文件。

### 必需配置
```bash
# IAM系统密钥（生产环境必须修改）
IAM_SECRET_KEY=your_super_secret_key_change_in_production

# 飞书应用凭证
FEISHU_APP_ID=cli_xxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_REDIRECT_URI=https://your-domain.com/api/feishu/callback
```

### 可选配置
- **数据库**：支持SQLite（开发）、PostgreSQL、MySQL
- **缓存**：Redis（推荐生产环境使用）
- **监控**：健康检查、指标收集
- **告警**：Slack、钉钉Webhook

## 🔗 飞书集成配置

### 1. 创建飞书应用
1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 `App ID` 和 `App Secret`

### 2. 配置应用权限
在飞书应用后台添加以下权限：

| 权限范围 | 权限说明 | 是否必需 |
|---------|---------|---------|
| `contact:user.base:readonly` | 读取用户基本信息 | ✅ |
| `contact:user.avatar:readonly` | 读取用户头像 | ⚠️ |
| `contact:department.base:readonly` | 读取部门信息 | ✅ |
| `contact:department.manage:readonly` | 管理部门信息 | ⚠️ |

### 3. 配置事件订阅（Webhook）
1. 在应用后台启用事件订阅
2. 设置请求地址：`https://your-domain.com/api/feishu/webhook`
3. 配置验证令牌（Verification Token）
4. 订阅以下事件：
   - 用户创建 `contact.user.created_v3`
   - 用户更新 `contact.user.updated_v3`
   - 用户删除 `contact.user.deleted_v3`
   - 部门创建 `contact.department.created_v3`
   - 部门更新 `contact.department.updated_v3`
   - 部门删除 `contact.department.deleted_v3`

### 4. 配置OAuth2.0
1. 设置重定向URL：`https://your-domain.com/api/feishu/callback`
2. 启用网页应用能力

## 🗄️ 数据库配置

### SQLite（开发环境）
默认配置，无需额外设置：
```bash
DATABASE_TYPE=sqlite
DATABASE_URL=sqlite:///iam_database.db
```

### PostgreSQL（生产环境推荐）
```bash
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://username:password@host:5432/iam_database
```

### MySQL
```bash
DATABASE_TYPE=mysql
DATABASE_URL=mysql://username:password@host:3306/iam_database
```

## 🚢 部署方式

### Docker部署（推荐）
1. 构建Docker镜像：
```bash
docker build -t agent-iam .
```

2. 运行容器：
```bash
docker run -d \
  --name agent-iam \
  -p 8000:8000 \
  --env-file .env \
  agent-iam
```

### Kubernetes部署
参考 `k8s/` 目录下的部署文件：
```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

### 传统服务器部署
1. 安装Python 3.8+
2. 配置反向代理（Nginx/Apache）
3. 使用进程管理工具（Systemd/Supervisor）

**Nginx配置示例**：
```nginx
server {
    listen 80;
    server_name iam.your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 📊 监控和维护

### 健康检查端点
- `GET /health` - 系统健康状态
- `GET /metrics` - 系统指标（如果启用）

### 日志管理
系统日志分为：
1. **应用日志**：程序运行日志，按级别过滤
2. **审计日志**：所有操作记录，存储在 `audit_logs.jsonl`
3. **访问日志**：HTTP请求日志

### 备份策略
1. **数据库备份**：定期备份用户和权限数据
2. **日志备份**：定期轮转和归档审计日志
3. **配置文件备份**：备份所有配置文件

## 🔧 故障排除

### 常见问题

#### 1. 飞书OAuth2.0登录失败
- 检查 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 是否正确
- 验证重定向URL是否与飞书应用配置一致
- 检查网络连接，确保能访问飞书API

#### 2. Webhook验证失败
- 检查 `FEISHU_WEBHOOK_VERIFICATION_TOKEN` 是否与飞书配置一致
- 验证服务器时间是否准确
- 检查防火墙设置，确保能接收外部请求

#### 3. 组织架构同步失败
- 检查飞书应用是否有足够的权限
- 验证网络连接
- 检查日志中的具体错误信息

#### 4. API访问失败
- 检查IAM_SECRET_KEY是否正确
- 验证Token是否过期
- 检查用户是否有相应权限

### 日志查看
```bash
# 查看应用日志
tail -f logs/app.log

# 查看错误日志
tail -f logs/error.log

# 查看审计日志
tail -f audit_logs.jsonl | jq .
```

### 性能调优
1. **启用缓存**：配置Redis提高性能
2. **数据库优化**：添加索引、优化查询
3. **连接池**：配置数据库连接池
4. **负载均衡**：多实例部署

## 📚 相关文档

- [API文档](http://localhost:8000/docs) - 完整的API接口文档
- [飞书集成示例](feishu_integration_example.py) - 飞书集成使用示例
- [权限映射配置](feishu_permission_mappings.json) - 权限映射规则配置
- [单元测试](tests/) - 单元测试用例

## 📞 支持与反馈

如有问题或建议，请：
1. 查看 [FAQ](#故障排除) 部分
2. 检查系统日志
3. 提交Issue或联系技术支持

---

**版本**: 1.0.0  
**最后更新**: 2024-01-01  
**维护团队**: IAM System Team