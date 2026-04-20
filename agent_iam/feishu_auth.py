"""
飞书认证服务：处理OAuth2授权、用户认证和单点登录
"""
import os
import json
import time
import logging
import secrets
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlencode, urljoin

from .feishu_client import FeishuClient, FeishuConfig
from .models import Actor, ActorType

logger = logging.getLogger(__name__)


@dataclass
class OAuth2Config:
    """OAuth2配置"""
    redirect_uri: str
    state_secret: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    scopes: list = field(default_factory=lambda: ["user:base", "user:avatar", "user:email"])
    
    @classmethod
    def from_env(cls) -> "OAuth2Config":
        """从环境变量创建配置"""
        redirect_uri = os.environ.get("FEISHU_OAUTH_REDIRECT_URI", "")
        scopes_str = os.environ.get("FEISHU_OAUTH_SCOPES", "user:base,user:avatar,user:email")
        scopes = [s.strip() for s in scopes_str.split(",")]
        
        return cls(
            redirect_uri=redirect_uri,
            scopes=scopes
        )


@dataclass
class SSOSession:
    """SSO会话"""
    session_id: str
    user_id: str
    user_access_token: str
    refresh_token: str
    expires_at: float
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    attributes: Dict[str, Any] = field(default_factory=dict)


class FeishuAuthService:
    """飞书认证服务"""
    
    def __init__(self, feishu_client: Optional[FeishuClient] = None,
                 oauth_config: Optional[OAuth2Config] = None):
        self.feishu_client = feishu_client or FeishuClient()
        self.oauth_config = oauth_config or OAuth2Config.from_env()
        self.sessions: Dict[str, SSOSession] = {}
        
        # 验证配置
        if not self.oauth_config.redirect_uri:
            logger.warning("FEISHU_OAUTH_REDIRECT_URI未设置，SSO功能可能受限")
    
    def generate_authorization_url(self, state: Optional[str] = None, 
                                  redirect_uri: Optional[str] = None) -> str:
        """生成OAuth2授权URL"""
        if not state:
            state = secrets.token_urlsafe(16)
        
        redirect_uri = redirect_uri or self.oauth_config.redirect_uri
        if not redirect_uri:
            raise ValueError("重定向URI未配置")
        
        # 飞书OAuth2授权端点
        base_url = "https://open.feishu.cn/open-apis/authen/v1/index"
        
        params = {
            "app_id": self.feishu_client.config.app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": " ".join(self.oauth_config.scopes)
        }
        
        return f"{base_url}?{urlencode(params)}"
    
    def handle_oauth_callback(self, code: str, state: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """处理OAuth2回调，返回用户信息和会话ID"""
        try:
            # 1. 使用授权码获取访问令牌
            token_response = self.feishu_client.get_user_access_token(code)
            
            user_access_token = token_response["access_token"]
            refresh_token = token_response["refresh_token"]
            expires_in = token_response["expires_in"]
            
            # 2. 获取用户信息
            user_info = self.feishu_client.get_user_info(user_access_token)
            
            # 3. 创建SSO会话
            session_id = secrets.token_urlsafe(32)
            session = SSOSession(
                session_id=session_id,
                user_id=user_info["user_id"],
                user_access_token=user_access_token,
                refresh_token=refresh_token,
                expires_at=time.time() + expires_in,
                attributes={
                    "feishu_user_info": user_info,
                    "state": state
                }
            )
            
            self.sessions[session_id] = session
            
            # 4. 返回用户信息和会话ID
            return user_info, session_id
            
        except Exception as e:
            logger.error(f"处理OAuth2回调失败: {e}")
            raise Exception(f"认证失败: {str(e)}")
    
    def validate_session(self, session_id: str) -> Optional[SSOSession]:
        """验证会话有效性"""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # 检查会话是否过期
        if time.time() > session.expires_at:
            # 尝试刷新令牌
            try:
                self._refresh_session_token(session)
            except Exception as e:
                logger.error(f"刷新会话令牌失败: {e}")
                del self.sessions[session_id]
                return None
        
        # 更新最后活动时间
        session.last_activity = time.time()
        return session
    
    def _refresh_session_token(self, session: SSOSession) -> None:
        """刷新会话令牌"""
        try:
            token_response = self.feishu_client.refresh_user_access_token(session.refresh_token)
            
            session.user_access_token = token_response["access_token"]
            session.refresh_token = token_response["refresh_token"]
            session.expires_at = time.time() + token_response["expires_in"]
            session.attributes["last_refresh"] = time.time()
            
            logger.info(f"会话 {session.session_id} 令牌刷新成功")
            
        except Exception as e:
            logger.error(f"刷新令牌失败: {e}")
            raise
    
    def logout(self, session_id: str) -> bool:
        """注销会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    def cleanup_expired_sessions(self, max_age: int = 86400) -> int:
        """清理过期会话，返回清理的会话数"""
        current_time = time.time()
        expired_keys = [
            session_id for session_id, session in self.sessions.items()
            if current_time - session.last_activity > max_age or current_time > session.expires_at
        ]
        
        for session_id in expired_keys:
            del self.sessions[session_id]
        
        return len(expired_keys)
    
    def map_to_iam_actor(self, user_info: Dict[str, Any], 
                         actor_type: ActorType = ActorType.USER) -> Actor:
        """将飞书用户映射到IAM Actor"""
        # 使用飞书user_id作为Actor ID的一部分
        actor_id = f"feishu_{user_info['user_id']}"
        
        attributes = {
            "feishu_user_id": user_info["user_id"],
            "feishu_name": user_info.get("name"),
            "feishu_email": user_info.get("email"),
            "feishu_mobile": user_info.get("mobile"),
            "feishu_employee_id": user_info.get("employee_id"),
            "source": "feishu",
            "auth_method": "oauth2"
        }
        
        # 合并其他用户信息
        for key, value in user_info.items():
            if key not in ["user_id", "name", "email", "mobile", "employee_id"]:
                attributes[f"feishu_{key}"] = value
        
        return Actor(
            id=actor_id,
            name=user_info.get("name", "飞书用户"),
            type=actor_type,
            attributes=attributes
        )
    
    def get_session_user_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话对应用户信息"""
        session = self.validate_session(session_id)
        if not session:
            return None
        
        return session.attributes.get("feishu_user_info")
    
    def create_login_url(self, return_url: str) -> Dict[str, str]:
        """创建登录URL，包含状态和安全校验"""
        state = secrets.token_urlsafe(16)
        redirect_uri = self.oauth_config.redirect_uri
        
        # 如果提供了自定义返回URL，可以将其编码到state中
        state_data = {
            "state": state,
            "return_url": return_url,
            "timestamp": int(time.time())
        }
        
        encoded_state = json.dumps(state_data)
        
        auth_url = self.generate_authorization_url(
            state=encoded_state,
            redirect_uri=redirect_uri
        )
        
        return {
            "auth_url": auth_url,
            "state": state
        }
    
    def verify_state(self, received_state: str, original_state: str) -> bool:
        """验证state参数，防止CSRF攻击"""
        try:
            # 尝试解析state数据
            state_data = json.loads(received_state)
            return state_data.get("state") == original_state
        except:
            # 如果无法解析，直接比较
            return received_state == original_state