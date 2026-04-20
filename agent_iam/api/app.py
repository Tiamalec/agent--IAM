"""
FastAPI应用主文件
"""
from fastapi import FastAPI, HTTPException, Depends, Header, status, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import time
import os

from ..models import Actor, ActorType, ActionType, ResourceType, TokenClaims
from ..token_service import TokenService
from ..auth_engine import AuthorizationEngine
from ..delegation import DelegationService
from ..audit_logger import AuditLogger
from ..monitoring import MetricsCollector, metrics_collector, start_metrics_collection_interval
from ..feishu_integration import (
    FeishuOAuth2Client,
    FeishuSSOManager,
    FeishuOrgSync,
    FeishuPermissionMapper,
    FeishuWebhookHandler,
    FeishuSkill,
    FeishuAction,
    FeishuResource
)


# 安全配置
security = HTTPBearer()

# Pydantic模型定义
class ActorCreateRequest(BaseModel):
    """创建参与者请求"""
    name: str
    type: ActorType
    attributes: Dict[str, Any] = Field(default_factory=dict)

class ActorResponse(BaseModel):
    """参与者响应"""
    id: str
    name: str
    type: ActorType
    attributes: Dict[str, Any]
    created_at: float

class TokenIssueRequest(BaseModel):
    """签发Token请求"""
    subject: str  # 接收者ID
    scopes: List[str]  # 权限范围，如 ["read:financial_data", "write:user_data"]
    expires_in: Optional[int] = 3600  # 过期时间（秒）
    max_uses: Optional[int] = None  # 最大使用次数
    context: Dict[str, Any] = Field(default_factory=dict)  # 上下文属性

class TokenResponse(BaseModel):
    """Token响应"""
    token: str
    claims: Dict[str, Any]

class TokenVerifyRequest(BaseModel):
    """验证Token请求"""
    token: str

class TokenVerifyResponse(BaseModel):
    """验证Token响应"""
    valid: bool
    claims: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class DelegateTokenRequest(BaseModel):
    """委托Token请求"""
    parent_token: str
    child_subject: str
    scopes: List[str]
    expires_in: Optional[int] = 1800  # 较短的过期时间
    max_uses: Optional[int] = None
    context: Dict[str, Any] = Field(default_factory=dict)

class DelegateTokenResponse(BaseModel):
    """委托Token响应"""
    token: str
    claims: Dict[str, Any]

class AuthorizationRequest(BaseModel):
    """授权检查请求"""
    token: str
    action: ActionType
    resource: ResourceType
    context: Dict[str, Any] = Field(default_factory=dict)

class AuthorizationResponse(BaseModel):
    """授权检查响应"""
    authorized: bool
    error: Optional[str] = None
    token_claims: Optional[Dict[str, Any]] = None

class AuditQueryParams(BaseModel):
    """审计日志查询参数"""
    actor_id: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    limit: int = 100
    offset: int = 0

class AuditEventResponse(BaseModel):
    """审计事件响应"""
    id: str
    timestamp: float
    actor_id: str
    action: str
    resource: str
    result: str
    details: Dict[str, Any]


# 飞书集成相关模型
class FeishuSSOLoginRequest(BaseModel):
    """飞书SSO登录请求"""
    code: str
    state: Optional[str] = None

class FeishuSSOLoginResponse(BaseModel):
    """飞书SSO登录响应"""
    success: bool
    actor: Optional[Dict[str, Any]] = None
    iam_token: Optional[str] = None
    feishu_user_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class FeishuAuthorizationUrlResponse(BaseModel):
    """飞书授权URL响应"""
    authorization_url: str
    state: str

class FeishuOrgSyncResponse(BaseModel):
    """飞书组织架构同步响应"""
    success: bool
    department_count: int
    user_count: int
    org_structure: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class FeishuPermissionMappingRequest(BaseModel):
    """飞书权限映射请求"""
    skill: str
    action: str
    resource: str

class FeishuPermissionMappingResponse(BaseModel):
    """飞书权限映射响应"""
    iam_scopes: List[str]
    validation_result: Optional[Dict[str, Any]] = None


# 飞书Webhook相关模型
class FeishuWebhookVerificationRequest(BaseModel):
    """飞书Webhook验证请求"""
    challenge: str
    token: str
    type: str = "url_verification"
    encrypt: Optional[str] = None

class FeishuWebhookVerificationResponse(BaseModel):
    """飞书Webhook验证响应"""
    challenge: str

class FeishuWebhookEventRequest(BaseModel):
    """飞书Webhook事件请求"""
    schema: Optional[str] = None
    header: Dict[str, Any]
    event: Dict[str, Any]
    encrypt: Optional[str] = None

class FeishuWebhookEventResponse(BaseModel):
    """飞书Webhook事件响应"""
    success: bool
    message: str
    event_type: Optional[str] = None
    handled: bool = False
    details: Optional[Dict[str, Any]] = None


# 监控相关模型
class SystemMetricsResponse(BaseModel):
    """系统指标响应"""
    time_range_hours: int
    metric_count: int
    cpu_percent: Dict[str, Any]
    memory_percent: Dict[str, Any]
    process_cpu_percent: Dict[str, Any]
    recent_metrics: List[Dict[str, Any]]

class BusinessMetricsResponse(BaseModel):
    """业务指标响应"""
    time_range_hours: int
    metric_count: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate_percent: float
    feishu_api_calls: int
    feishu_api_errors: int
    feishu_success_rate_percent: float
    org_sync_count: int
    user_login_count: int
    current_active_sessions: int
    current_active_tokens: int
    request_distribution: Dict[str, int]
    recent_errors: Dict[str, str]

class HealthStatusResponse(BaseModel):
    """健康状态响应"""
    status: str
    issues: List[str]
    timestamp: float
    metrics: Optional[Dict[str, Any]] = None


class IAMAPI:
    """IAM API核心类"""
    
    def __init__(self, secret_key: str = "api_secret_key_change_in_production"):
        self.app = FastAPI(
            title="AI Agent IAM API",
            description="AI Agent身份与访问控制系统的REST API",
            version="0.1.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # 初始化核心服务
        self.token_service = TokenService(secret_key=secret_key)
        self.auth_engine = AuthorizationEngine()
        self.delegation_service = DelegationService(self.token_service)
        self.audit_logger = AuditLogger("api_audit_log.jsonl")
        
        # 初始化监控服务
        self.metrics_collector = metrics_collector
        # 启动定期指标收集（每分钟收集一次）
        start_metrics_collection_interval(interval_seconds=60)
        
        # 初始化飞书集成服务
        self.feishu_app_id = os.environ.get("FEISHU_APP_ID")
        self.feishu_app_secret = os.environ.get("FEISHU_APP_SECRET")
        self.feishu_redirect_uri = os.environ.get("FEISHU_REDIRECT_URI")
        
        if self.feishu_app_id and self.feishu_app_secret:
            self.feishu_oauth_client = FeishuOAuth2Client(
                app_id=self.feishu_app_id,
                app_secret=self.feishu_app_secret,
                redirect_uri=self.feishu_redirect_uri
            )
            self.feishu_sso_manager = FeishuSSOManager(
                self.feishu_oauth_client,
                self.token_service,
                self.auth_engine
            )
            self.feishu_org_sync = FeishuOrgSync(
                app_id=self.feishu_app_id,
                app_secret=self.feishu_app_secret
            )
            self.feishu_permission_mapper = FeishuPermissionMapper()
            
            # 初始化Webhook处理器
            self.feishu_webhook_handler = FeishuWebhookHandler(
                verification_token=os.environ.get("FEISHU_WEBHOOK_VERIFICATION_TOKEN"),
                encrypt_key=os.environ.get("FEISHU_WEBHOOK_ENCRYPT_KEY")
            )
        else:
            self.feishu_oauth_client = None
            self.feishu_sso_manager = None
            self.feishu_org_sync = None
            self.feishu_permission_mapper = None
            self.feishu_webhook_handler = None
        
        # 存储参与者
        self.actors: Dict[str, Actor] = {}
        
        # 注册路由
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """设置API路由"""
        
        @self.app.get("/")
        async def root():
            """根端点"""
            return {
                "service": "AI Agent IAM API",
                "version": "0.1.0",
                "endpoints": [
                    "/actors",
                    "/tokens",
                    "/tokens/verify",
                    "/tokens/delegate",
                    "/authorize",
                    "/audit"
                ]
            }
        
        @self.app.post("/actors", response_model=ActorResponse, status_code=status.HTTP_201_CREATED)
        async def create_actor(request: ActorCreateRequest):
            """创建新参与者（用户或Agent）"""
            actor = Actor(
                name=request.name,
                type=request.type,
                attributes=request.attributes
            )
            
            self.actors[actor.id] = actor
            
            # 记录审计事件
            self.audit_logger.log_event(
                actor_id="system",
                action="create_actor",
                resource=f"actor:{actor.id}",
                result="success",
                details={"actor_type": request.type.value, "name": request.name}
            )
            
            return ActorResponse(
                id=actor.id,
                name=actor.name,
                type=actor.type,
                attributes=actor.attributes,
                created_at=actor.created_at
            )
        
        @self.app.get("/actors/{actor_id}", response_model=ActorResponse)
        async def get_actor(actor_id: str):
            """获取参与者信息"""
            if actor_id not in self.actors:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Actor not found: {actor_id}"
                )
            
            actor = self.actors[actor_id]
            return ActorResponse(
                id=actor.id,
                name=actor.name,
                type=actor.type,
                attributes=actor.attributes,
                created_at=actor.created_at
            )
        
        @self.app.post("/tokens", response_model=TokenResponse)
        async def issue_token(request: TokenIssueRequest, authorization: HTTPAuthorizationCredentials = Depends(security)):
            """签发Token"""
            # 验证签发者（从Bearer Token获取）
            issuer_claims = self._verify_bearer_token(authorization.credentials)
            if not issuer_claims:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid issuer token"
                )
            
            # 检查签发者是否有权限签发Token
            # 需要 token:issue 权限或通配符 *
            if "token:issue" not in issuer_claims.scopes and "*" not in issuer_claims.scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Issuer does not have permission to issue tokens"
                )
            
            # 创建Token声明
            claims = TokenClaims(
                sub=request.subject,
                iss=issuer_claims.sub,
                iat=time.time(),
                exp=time.time() + request.expires_in if request.expires_in else None,
                scopes=set(request.scopes),
                max_uses=request.max_uses,
                context=request.context
            )
            
            # 编码Token
            token = self.token_service.encode(claims)
            
            # 记录审计事件
            self.audit_logger.log_event(
                actor_id=issuer_claims.sub,
                action="issue_token",
                resource=f"actor:{request.subject}",
                result="success",
                details={"scopes": request.scopes, "expires_in": request.expires_in}
            )
            
            return TokenResponse(
                token=token,
                claims=claims.to_dict()
            )
        
        @self.app.post("/tokens/verify", response_model=TokenVerifyResponse)
        async def verify_token(request: TokenVerifyRequest):
            """验证Token"""
            claims = self.token_service.decode(request.token)
            
            if not claims:
                return TokenVerifyResponse(
                    valid=False,
                    error="Invalid token format or signature"
                )
            
            # 验证Token有效性
            is_valid = self.token_service.validate_token(request.token)
            
            if not is_valid:
                return TokenVerifyResponse(
                    valid=False,
                    error="Token expired or exceeded usage limit"
                )
            
            return TokenVerifyResponse(
                valid=True,
                claims=claims.to_dict()
            )
        
        @self.app.post("/tokens/delegate", response_model=DelegateTokenResponse)
        async def delegate_token(request: DelegateTokenRequest, authorization: HTTPAuthorizationCredentials = Depends(security)):
            """委托Token"""
            # 验证父Token
            parent_claims = self._verify_bearer_token(authorization.credentials)
            if not parent_claims:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid parent token"
                )
            
            # 检查委托权限
            requested_scopes = set(request.scopes)
            can_delegate = self.delegation_service.can_delegate(
                authorization.credentials, requested_scopes
            )
            
            if not can_delegate:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot delegate requested scopes"
                )
            
            # 创建委托Token
            delegated_token = self.delegation_service.create_delegated_token(
                parent_token=authorization.credentials,
                child_sub=request.child_subject,
                scopes=requested_scopes,
                expires_in=request.expires_in,
                max_uses=request.max_uses,
                context=request.context
            )
            
            if not delegated_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to create delegated token"
                )
            
            # 解码委托Token以获取声明
            delegated_claims = self.token_service.decode(delegated_token)
            
            # 记录审计事件
            self.audit_logger.log_event(
                actor_id=parent_claims.sub,
                action="delegate_token",
                resource=f"actor:{request.child_subject}",
                result="success",
                details={"scopes": request.scopes, "expires_in": request.expires_in}
            )
            
            return DelegateTokenResponse(
                token=delegated_token,
                claims=delegated_claims.to_dict() if delegated_claims else {}
            )
        
        @self.app.post("/authorize", response_model=AuthorizationResponse)
        async def authorize(request: AuthorizationRequest):
            """授权检查"""
            # 解码Token
            claims = self.token_service.decode(request.token)
            
            if not claims:
                return AuthorizationResponse(
                    authorized=False,
                    error="Invalid token"
                )
            
            # 验证Token有效性
            if not self.token_service.validate_token(request.token):
                return AuthorizationResponse(
                    authorized=False,
                    error="Token expired or invalid"
                )
            
            # 检查授权
            is_authorized = self.auth_engine.evaluate_token_authorization(
                claims, request.action, request.resource, request.context
            )
            
            # 记录审计事件
            self.audit_logger.log_event(
                actor_id=claims.sub,
                action=f"authorize_{request.action.value}",
                resource=request.resource.value,
                result="allow" if is_authorized else "deny",
                details={
                    "context": request.context,
                    "token_scopes": list(claims.scopes)
                }
            )
            
            if is_authorized:
                # 增加Token使用次数
                self.token_service.increment_use_count(request.token)
                
                return AuthorizationResponse(
                    authorized=True,
                    token_claims=claims.to_dict()
                )
            else:
                return AuthorizationResponse(
                    authorized=False,
                    error="Insufficient permissions",
                    token_claims=claims.to_dict()
                )
        
        @self.app.get("/audit", response_model=List[AuditEventResponse])
        async def get_audit_logs(
            actor_id: Optional[str] = None,
            resource: Optional[str] = None,
            action: Optional[str] = None,
            limit: int = 100,
            offset: int = 0,
            authorization: HTTPAuthorizationCredentials = Depends(security)
        ):
            """查询审计日志"""
            # 验证查询权限
            claims = self._verify_bearer_token(authorization.credentials)
            if not claims:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            
            # 检查是否有审计查询权限
            if "audit:read" not in claims.scopes and "*" not in claims.scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to view audit logs"
                )
            
            # 加载所有事件
            events = self.audit_logger.load_events()
            
            # 应用过滤
            filtered_events = events
            
            if actor_id:
                filtered_events = [e for e in filtered_events if e.actor_id == actor_id]
            
            if resource:
                filtered_events = [e for e in filtered_events if e.resource == resource]
            
            if action:
                filtered_events = [e for e in filtered_events if e.action == action]
            
            # 应用分页
            paginated_events = filtered_events[offset:offset + limit]
            
            # 转换为响应模型
            return [
                AuditEventResponse(
                    id=event.id,
                    timestamp=event.timestamp,
                    actor_id=event.actor_id,
                    action=event.action,
                    resource=event.resource,
                    result=event.result,
                    details=event.details
                )
                for event in paginated_events
            ]
        
        # ==================== 飞书集成路由 ====================
        
        @self.app.get("/feishu/auth/url", response_model=FeishuAuthorizationUrlResponse)
        async def get_feishu_authorization_url(state: Optional[str] = None):
            """获取飞书OAuth2.0授权URL"""
            if not self.feishu_oauth_client:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="飞书集成未配置，请设置FEISHU_APP_ID和FEISHU_APP_SECRET环境变量"
                )
            
            # 生成随机state（如果未提供）
            import secrets
            state_value = state or secrets.token_urlsafe(16)
            
            # 获取授权URL
            auth_url = self.feishu_oauth_client.get_authorization_url(
                state=state_value,
                scope="contact:user.base:readonly"
            )
            
            return FeishuAuthorizationUrlResponse(
                authorization_url=auth_url,
                state=state_value
            )
        
        @self.app.post("/feishu/sso/login", response_model=FeishuSSOLoginResponse)
        async def feishu_sso_login(request: FeishuSSOLoginRequest):
            """飞书SSO登录（使用OAuth2.0授权码）"""
            if not self.feishu_sso_manager:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="飞书SSO服务未配置"
                )
            
            # 验证用户并获取IAM令牌
            actor, iam_token, user_info = self.feishu_sso_manager.authenticate_user(request.code)
            
            if actor and iam_token:
                # 存储Actor到内存（实际部署中应该存储到数据库）
                self.actors[actor.id] = actor
                
                # 记录审计事件
                self.audit_logger.log_event(
                    actor_id=actor.id,
                    action="feishu_sso_login",
                    resource="feishu:user",
                    result="success",
                    details={
                        "feishu_user_id": user_info.get("user_id"),
                        "feishu_open_id": user_info.get("open_id"),
                        "source": "feishu"
                    }
                )
                
                return FeishuSSOLoginResponse(
                    success=True,
                    actor=actor.to_dict(),
                    iam_token=iam_token,
                    feishu_user_info=user_info
                )
            else:
                # 记录失败的审计事件
                self.audit_logger.log_event(
                    actor_id="unknown",
                    action="feishu_sso_login",
                    resource="feishu:user",
                    result="failure",
                    details={"error": "认证失败", "code": request.code[:10] + "..." if request.code else "empty"}
                )
                
                return FeishuSSOLoginResponse(
                    success=False,
                    error="飞书用户认证失败，请检查授权码是否正确"
                )
        
        @self.app.post("/feishu/org/sync", response_model=FeishuOrgSyncResponse)
        async def sync_feishu_organization(authorization: HTTPAuthorizationCredentials = Depends(security)):
            """同步飞书组织架构（需要管理员权限）"""
            if not self.feishu_org_sync:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="飞书组织架构同步服务未配置"
                )
            
            # 验证管理员权限
            claims = self._verify_bearer_token(authorization.credentials)
            if not claims:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="无效的令牌"
                )
            
            # 检查管理员权限
            if "admin:iam" not in claims.scopes and "*" not in claims.scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="需要管理员权限"
                )
            
            # 同步组织架构
            result = self.feishu_org_sync.sync_full_organization()
            
            if result.get("success"):
                # 记录审计事件
                self.audit_logger.log_event(
                    actor_id=claims.sub,
                    action="sync_feishu_organization",
                    resource="feishu:organization",
                    result="success",
                    details={
                        "department_count": result.get("department_count", 0),
                        "user_count": result.get("user_count", 0)
                    }
                )
                
                return FeishuOrgSyncResponse(
                    success=True,
                    department_count=result.get("department_count", 0),
                    user_count=result.get("user_count", 0),
                    org_structure=result.get("org_structure")
                )
            else:
                # 记录失败的审计事件
                self.audit_logger.log_event(
                    actor_id=claims.sub,
                    action="sync_feishu_organization",
                    resource="feishu:organization",
                    result="failure",
                    details={"error": result.get("error", "未知错误")}
                )
                
                return FeishuOrgSyncResponse(
                    success=False,
                    department_count=0,
                    user_count=0,
                    error=result.get("error", "同步失败")
                )
        
        @self.app.post("/feishu/permissions/map", response_model=FeishuPermissionMappingResponse)
        async def map_feishu_permission(
            request: FeishuPermissionMappingRequest,
            authorization: HTTPAuthorizationCredentials = Depends(security)
        ):
            """映射飞书权限到IAM Scopes"""
            if not self.feishu_permission_mapper:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="飞书权限映射服务未配置"
                )
            
            # 验证令牌
            claims = self._verify_bearer_token(authorization.credentials)
            if not claims:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="无效的令牌"
                )
            
            try:
                # 解析枚举值
                skill = FeishuSkill(request.skill)
                action = FeishuAction(request.action)
                resource = FeishuResource(request.resource)
                
                # 映射到IAM Scopes
                iam_scopes = self.feishu_permission_mapper.map_feishu_to_iam(skill, action, resource)
                
                # 验证用户是否有这些权限
                has_permission = self.feishu_permission_mapper.validate_iam_scopes_for_feishu(
                    skill, action, claims.scopes
                )
                
                # 记录审计事件
                self.audit_logger.log_event(
                    actor_id=claims.sub,
                    action="map_feishu_permission",
                    resource="feishu:permission",
                    result="success" if has_permission else "failure",
                    details={
                        "skill": request.skill,
                        "action": request.action,
                        "resource": request.resource,
                        "mapped_scopes": list(iam_scopes),
                        "user_has_permission": has_permission
                    }
                )
                
                return FeishuPermissionMappingResponse(
                    iam_scopes=list(iam_scopes),
                    validation_result={
                        "has_permission": has_permission,
                        "user_scopes": list(claims.scopes)
                    }
                )
                
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的权限参数: {str(e)}"
                )
        
        @self.app.post("/feishu/webhook", response_model=Union[FeishuWebhookVerificationResponse, FeishuWebhookEventResponse])
        async def handle_feishu_webhook(request: FeishuWebhookEventRequest):
            """处理飞书Webhook事件（包括验证和事件处理）"""
            if not self.feishu_webhook_handler:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="飞书Webhook服务未配置"
                )
            
            # 检查是否是URL验证请求
            if request.header.get("event_type") == "url_verification":
                # URL验证逻辑
                challenge = request.event.get("challenge")
                token = request.event.get("token")
                
                verification_result = self.feishu_webhook_handler.verify_webhook(
                    challenge=challenge,
                    token=token,
                    timestamp=request.header.get("timestamp", ""),
                    nonce=request.header.get("nonce", ""),
                    encrypted=request.encrypt,
                    signature=request.header.get("signature")
                )
                
                if verification_result.get("success"):
                    return FeishuWebhookVerificationResponse(
                        challenge=verification_result["challenge"]
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Webhook验证失败: {verification_result.get('error')}"
                    )
            else:
                # 处理事件
                event_data = {
                    "type": request.header.get("event_type"),
                    "event": request.event,
                    "schema": request.schema,
                    "header": request.header
                }
                
                # 处理事件
                result = self.feishu_webhook_handler.handle_event(event_data)
                
                # 记录审计事件
                self.audit_logger.log_event(
                    actor_id="system",
                    action="feishu_webhook_event",
                    resource="feishu:webhook",
                    result="success" if result.get("success") else "failure",
                    details={
                        "event_type": request.header.get("event_type"),
                        "handled": result.get("handled", False),
                        "success": result.get("success", False)
                    }
                )
                
                return FeishuWebhookEventResponse(
                    success=result.get("success", False),
                    message=result.get("message", ""),
                    event_type=result.get("event_type"),
                    handled=result.get("handled", False),
                    details=result
                )
        
        # ==================== 飞书集成路由结束 ====================
        
        @self.app.get("/metrics/system", response_model=SystemMetricsResponse)
        async def get_system_metrics(hours: int = 1):
            """
            获取系统指标
            
            Args:
                hours: 时间范围（小时），默认过去1小时
            """
            if hours < 1 or hours > 24:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="时间范围必须在1到24小时之间"
                )
            
            metrics = self.metrics_collector.get_system_metrics_summary(hours)
            return metrics
        
        @self.app.get("/metrics/business", response_model=BusinessMetricsResponse)
        async def get_business_metrics(hours: int = 1):
            """
            获取业务指标
            
            Args:
                hours: 时间范围（小时），默认过去1小时
            """
            if hours < 1 or hours > 24:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="时间范围必须在1到24小时之间"
                )
            
            metrics = self.metrics_collector.get_business_metrics_summary(hours)
            return metrics
        
        @self.app.get("/metrics/health", response_model=HealthStatusResponse)
        async def get_health_status():
            """获取系统健康状态"""
            health_status = self.metrics_collector.get_health_status()
            return health_status
        
        @self.app.post("/metrics/export")
        async def export_metrics():
            """导出所有指标数据"""
            filename = f"metrics_export_{int(time.time())}.json"
            success = self.metrics_collector.export_metrics(filename)
            
            if success:
                return {
                    "success": True,
                    "message": "指标数据导出成功",
                    "filename": filename,
                    "download_url": f"/metrics/download/{filename}"
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="指标数据导出失败"
                )
        
        @self.app.get("/metrics/download/{filename}")
        async def download_metrics(filename: str):
            """下载导出的指标数据"""
            file_path = f"./{filename}"
            
            if not os.path.exists(file_path):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="文件不存在"
                )
            
            # 检查文件名是否合法（防止路径遍历攻击）
            if not filename.startswith("metrics_export_") or not filename.endswith(".json"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="无效的文件名"
                )
            
            return FileResponse(
                path=file_path,
                filename=filename,
                media_type="application/json"
            )
        
        @self.app.get("/health")
        async def health_check():
            """健康检查端点"""
            # 增强健康检查：包含监控数据
            health_status = self.metrics_collector.get_health_status()
            
            return {
                "status": health_status.get("status", "healthy"),
                "timestamp": time.time(),
                "monitoring": {
                    "system_metrics": len(self.metrics_collector.system_metrics),
                    "business_metrics": len(self.metrics_collector.business_metrics)
                },
                "issues": health_status.get("issues", [])
            }
    
    def _verify_bearer_token(self, token: str) -> Optional[TokenClaims]:
        """验证Bearer Token"""
        return self.token_service.decode(token)


# 创建应用实例
app = IAMAPI().app