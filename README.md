# 🏆 AI Agent IAM 系统 - 飞书AI实战挑战赛

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Test Status](https://img.shields.io/badge/tests-41%20passed-brightgreen)

## 📖 项目简介

**AI Agent IAM（Identity and Access Management）系统**是一个专门为AI Agent设计的身份与访问控制平台。系统提供细粒度的权限控制、安全的信任委托链、防篡改的审计日志，支持多Agent安全协作。

### 🎯 核心创新点

1. **🔐 RBAC + ABAC融合授权** - 基于角色和属性的细粒度上下文感知权限控制
2. **🔗 多层信任委托链** - 安全的Agent间权限传递与验证
3. **📝 防篡改审计日志** - 基于哈希链的完整操作追踪
4. **🛡️ 多层安全防护** - 权限提升、过期、超限等攻击防护
5. **🤝 多Agent智能协作** - 安全的分布式任务执行框架

## 🚀 快速开始

### 环境要求
- Python 3.8+
- pip 包管理工具

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行完整演示
```bash
# 基础演示
python -c "from agent_iam.demo import IAMDemo; demo = IAMDemo(); demo.run_full_demo()"

# 高级演示（财务报告生成流水线）
python -c "from agent_iam.advanced_demo import FinancialReportDemo; demo = FinancialReportDemo(); demo.run_full_demo()"

# 飞书集成演示
python feishu_demo.py

# 比赛演示（推荐）
python competition_demo.py
```

### 启动REST API服务
```bash
python run_api.py
```
访问API文档：http://localhost:8000/docs

### 启动可视化监控面板
```bash
pip install streamlit plotly
streamlit run streamlit_app.py
```

## 📁 项目结构

```
agent_iam/
├── models.py          # 核心域模型（Actor, Policy, TokenClaims, AuditEvent）
├── token_service.py   # Token服务（HMAC签名的JWT-like Token）
├── auth_engine.py     # 授权引擎（RBAC + ABAC融合）
├── delegation.py      # 委托服务（信任链验证）
├── audit_logger.py    # 审计日志（哈希链防篡改）
├── demo.py           # 基础演示脚本
├── advanced_demo.py  # 高级演示脚本（财务报告流水线）
├── feishu_integration.py  # 飞书AI Agent集成核心模块
└── api/
    └── app.py        # FastAPI REST API

tests/                  # 41个单元测试
competition_demo.py    # 比赛演示脚本
streamlit_app.py       # Streamlit可视化界面
feishu_demo.py        # 飞书集成演示脚本
run_api.py            # API服务器启动脚本
requirements.txt      # Python依赖
```

## 🔧 核心功能

### 1. 身份管理
- **Actor模型**：支持用户、Master Agent、Worker Agent等多种角色
- **属性管理**：支持动态属性绑定和上下文感知
- **生命周期管理**：完整的注册、更新、注销流程

### 2. 访问控制
- **RBAC + ABAC融合**：基于角色和属性的双重验证
- **细粒度权限**：读、写、执行、删除、委托等操作控制
- **上下文感知**：环境、时间、资源属性等多维度验证

### 3. Token系统
- **HMAC签名**：安全的JWT-like Token
- **委托链支持**：父Token派生子Token
- **使用限制**：过期时间、最大使用次数、上下文绑定
- **完整性验证**：签名验证、过期检查、使用次数检查

### 4. 委托机制
- **信任链验证**：完整的委托路径追溯
- **权限继承**：子Token继承父Token的权限子集
- **安全限制**：防止权限提升和越权委托

### 5. 审计日志
- **哈希链技术**：防篡改的事件记录
- **完整性验证**：实时验证日志完整性
- **多维查询**：按参与者、资源、操作、结果筛选
- **时间序列分析**：操作趋势和异常检测

## 🎮 演示场景

### 场景1：基础授权演示
```
用户 → 授权 → Master Agent → 委托 → Worker Agent
```
演示基本的权限委托和访问控制流程。

### 场景2：财务报告生成流水线
```
财务总监 → 项目管理Agent → 数据采集Agent → 数据分析Agent → 报告生成Agent → 审批Agent
```
演示复杂的多Agent协作场景。

### 场景3：安全防护演示
- 权限提升尝试拦截
- Token过期防护
- 使用次数超限保护
- 上下文不匹配拒绝

### 场景4：审计追踪演示
- 完整操作记录
- 哈希链完整性验证
- 实时监控和告警

## 🚀 飞书AI Agent集成

### 集成架构
IAM系统与飞书lark-cli AI Agent的无缝集成，提供企业级的安全控制：

```
企业管理员 → IAM系统 → 飞书AI Agents → 飞书lark-cli → 飞书业务数据
```

### 核心集成特性
1. **Skill-based权限映射**：19个飞书Skills（日历、消息、文档、表格、任务等）与IAM权限的精细映射
2. **Token委托链**：管理员Token → Agent Token → Skill Token的安全委托
3. **统一审计**：所有飞书操作记录到IAM审计日志，支持完整性验证
4. **细粒度控制**：基于Skill、Action、Resource的三层权限控制

### 支持的飞书Skills
系统支持19个飞书lark-cli Skills，包括：
- **lark-calendar**：日历管理（查看日程、创建日程、邀请参会人、查询忙闲状态）
- **lark-im**：即时通讯（发送/回复消息、群聊管理、消息搜索、文件上传下载）
- **lark-doc**：文档管理（创建、读取、更新、搜索文档）
- **lark-base**：多维表格（表格、字段、记录、视图、仪表盘、数据聚合分析）
- **lark-task**：任务管理（任务、任务清单、子任务、提醒、成员分配）
- 以及14个其他Skills（会议、邮件、审批、通讯录等）

### 集成演示
运行完整飞书集成演示：
```bash
python feishu_demo.py
```

演示包含6个阶段：
1. **飞书Skill注册和授权**：企业管理员为AI Agent注册飞书Skills
2. **日历Agent智能工作流**：智能日程助手自动安排团队会议
3. **多Agent飞书协作**：多个AI Agent协作完成项目任务
4. **精细权限控制**：演示飞书Skills的细粒度权限控制
5. **审计和合规性**：展示飞书集成的完整审计追踪
6. **集成概览**：总结集成架构和价值

### 集成代码结构
```
agent_iam/
├── feishu_integration.py    # 飞书集成核心模块
│   ├── FeishuSkill           # 飞书Skill枚举（19个Skills）
│   ├── FeishuResource        # 飞书资源枚举
│   ├── FeishuAction          # 飞书操作枚举
│   ├── FeishuIntegration     # 飞书集成主类
│   └── FeishuAgent           # 飞书AI Agent扩展
└── ...

feishu_demo.py                # 飞书集成演示脚本
```

### 使用示例
```python
from agent_iam.feishu_integration import FeishuIntegration, FeishuSkill

# 初始化飞书集成
integration = FeishuIntegration()

# 注册飞书AI Agent
calendar_agent = Actor(name="智能日程助手", type=ActorType.MASTER_AGENT)
skill_tokens = integration.register_feishu_agent(
    calendar_agent, [FeishuSkill.CALENDAR]
)

# 执行飞书命令
calendar_token = skill_tokens[FeishuSkill.CALENDAR.value]
result = integration.execute_feishu_command(
    calendar_token, "calendar agenda", {"date": "today"}
)
```

### 业务价值
- **安全可控的AI Agent飞书操作**：防止未授权访问敏感业务数据
- **统一的权限管理和审计追踪**：符合企业安全合规要求
- **支持复杂的多Agent协作工作流**：提升工作效率
- **易于扩展的集成架构**：支持更多飞书Skills和企业应用

## 📊 API接口

系统提供完整的REST API接口：

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/` | GET | 服务状态 | 否 |
| `/actors` | POST | 创建参与者 | 是 |
| `/tokens` | POST | 签发Token | 是 |
| `/tokens/verify` | POST | 验证Token | 否 |
| `/tokens/delegate` | POST | 委托Token | 是 |
| `/authorize` | POST | 授权检查 | 是 |
| `/audit` | GET | 查询审计日志 | 是 |
| `/health` | GET | 健康检查 | 否 |

## 🧪 测试

运行完整测试套件：
```bash
# 运行所有测试（41个测试用例）
python -m pytest tests/ -v

# 运行API测试
python -m pytest tests/test_api.py -v

# 运行特定模块测试
python -m pytest tests/test_auth_engine.py -v
```

测试覆盖率：
- 单元测试：41个测试用例，100%通过率
- 集成测试：完整的API测试
- 演示测试：多个业务场景验证

## 🖥️ 可视化监控

系统提供Streamlit可视化监控面板：
```bash
streamlit run streamlit_app.py
```

监控功能：
- **Agent关系图**：可视化显示Agent关系和委托链
- **实时审计日志**：时间序列展示操作记录
- **Token状态监控**：实时查看Token使用情况
- **权限检查工具**：实时测试权限配置
- **系统状态面板**：演示结果和统计信息

## 🔐 安全特性

### 1. 防御深度
- **认证层**：HMAC签名的Token验证
- **授权层**：RBAC + ABAC融合控制
- **审计层**：防篡改的完整操作记录
- **监控层**：实时异常检测和告警

### 2. 攻击防护
- ✅ 权限提升攻击
- ✅ Token重放攻击
- ✅ 数据篡改攻击
- ✅ 拒绝服务攻击（通过使用次数限制）
- ✅ 上下文欺骗攻击

### 3. 隐私保护
- 最小权限原则
- 上下文感知的访问控制
- 完整的操作审计
- 数据脱敏和加密

## 📈 性能指标

- **响应时间**：< 10ms（权限检查）
- **并发支持**：支持高并发Token验证
- **扩展性**：模块化设计，易于扩展
- **可靠性**：完整的错误处理和恢复机制

## 🚀 部署

### 本地部署
```bash
# 1. 克隆项目
git clone <repository-url>
cd xinzijie

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行演示
python competition_demo.py

# 4. 启动服务
python run_api.py
```

### Docker部署
```bash
# 构建镜像
docker build -t agent-iam .

# 运行容器
docker run -p 8000:8000 agent-iam
```

## 📚 文档

- [需求文档](需求文档.md)
- [开发计划](开发计划.md)
- [项目背景](项目背景.md)
- [API文档](http://localhost:8000/docs)（启动服务后访问）

## 🏆 比赛价值

### 技术创新
1. **融合授权模型**：RBAC与ABAC的创新结合
2. **防篡改审计**：哈希链技术在IAM系统的应用
3. **多Agent安全协作**：解决AI Agent生态的安全挑战

### 商业价值
1. **企业级安全**：满足金融、医疗等敏感行业的合规要求
2. **可扩展架构**：支持大规模AI Agent部署
3. **易用性**：完整的API和可视化工具

### 社会价值
1. **AI安全**：推动AI技术的安全可信发展
2. **标准贡献**：为AI Agent安全协作提供参考实现
3. **开源生态**：促进AI安全技术的开源发展

## 🤝 贡献

欢迎提交Issue和Pull Request！

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 推送分支
5. 创建Pull Request

## 📄 许可证

本项目基于MIT许可证开源。

## 📞 联系

如有问题或建议，请通过以下方式联系：
- GitHub Issues
- 项目文档
- 演示脚本中的联系方式

---

**🏆 飞书AI实战挑战赛参赛项目 - 为AI Agent生态提供安全基石**
# agent--IAM