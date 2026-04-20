"""
飞书集成服务（主入口点）
提供统一的企业级IAM与飞书平台集成接口
"""
import time
import logging
from typing import Dict, Any, Optional, List

from .feishu_client import FeishuClient, FeishuConfig
from .feishu_auth import FeishuAuthService, OAuth2Config, SSOSession
from .feishu_org_sync import FeishuOrgSyncService, SyncConfig, SyncStats
from .feishu_permission import FeishuPermissionMapper, FeishuSkill
from .models import Actor, ActorType, Policy

logger = logging.getLogger(__name__)


class FeishuIntegrationService:
    """飞书集成服务（主类）"""
    
    def __init__(self, 
                 feishu_config: Optional[FeishuConfig] = None,
                 oauth_config: Optional[OAuth2Config] = None,
                 sync_config: Optional[SyncConfig] = None):
        """初始化飞书集成服务"""
        
        # 初始化配置
        self.feishu_config = feishu_config or FeishuConfig.from_env()
        self.oauth_config = oauth_config or OAuth2Config.from_env()
        self.sync_config = sync_config or SyncConfig.from_env()
        
        # 初始化各服务组件
        self.client = FeishuClient(self.feishu_config)
        self.auth_service = FeishuAuthService(self.client, self.oauth_config)
        self.sync_service = FeishuOrgSyncService(self.client, None, self.sync_config)
        self.permission_mapper = FeishuPermissionMapper(self.client)
        
        logger.info("飞书集成服务初始化完成")
    
    # ==================== 认证和SSO相关方法 ====================
    
    def get_authorization_url(self, return_url: str = "/") -> Dict[str, str]:
        """获取OAuth2授权URL（用于SSO登录）"""
        return self.auth_service.create_login_url(return_url)
    
    def handle_oauth_callback(self, code: str, state: str) -> Dict[str, Any]:
        """处理OAuth2回调，返回用户信息和会话"""
        user_info, session_id = self.auth_service.handle_oauth_callback(code, state)
        
        # 将飞书用户映射为IAM Actor
        actor = self.auth_service.map_to_iam_actor(user_info)
        
        return {
            "user_info": user_info,
            "actor": actor.to_dict(),
            "session_id": session_id,
            "success": True
        }
    
    def validate_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """验证会话有效性"""
        session = self.auth_service.validate_session(session_id)
        if not session:
            return None
        
        user_info = self.auth_service.get_session_user_info(session_id)
        actor = self.auth_service.map_to_iam_actor(user_info) if user_info else None
        
        return {
            "session": {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "expires_at": session.expires_at,
                "last_activity": session.last_activity
            },
            "user_info": user_info,
            "actor": actor.to_dict() if actor else None
        }
    
    def logout(self, session_id: str) -> bool:
        """注销会话"""
        return self.auth_service.logout(session_id)
    
    # ==================== 组织架构同步相关方法 ====================
    
    def sync_organization(self, incremental: bool = True) -> Dict[str, Any]:
        """同步组织架构"""
        if incremental:
            stats = self.sync_service.sync_incremental()
        else:
            stats = self.sync_service.sync_full_organization()
        
        return {
            "stats": stats.to_dict(),
            "incremental": incremental,
            "success": stats.success_rate > 0.9  # 成功率超过90%视为成功
        }
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        return self.sync_service.get_sync_status()
    
    def find_user_by_feishu_id(self, feishu_user_id: str) -> Optional[Dict[str, Any]]:
        """通过飞书用户ID查找用户"""
        return self.sync_service.find_user_by_feishu_id(feishu_user_id)
    
    def find_department_by_feishu_id(self, feishu_dept_id: str) -> Optional[Dict[str, Any]]:
        """通过飞书部门ID查找部门"""
        return self.sync_service.find_department_by_feishu_id(feishu_dept_id)
    
    # ==================== 权限映射相关方法 ====================
    
    def create_policy_from_feishu_skills(self, feishu_skills: List[str], 
                                        role_mapping_id: str = None) -> Dict[str, Any]:
        """根据飞书Skills创建IAM策略"""
        try:
            # 将字符串转换为FeishuSkill枚举
            skills = [FeishuSkill(skill) for skill in feishu_skills]
            
            # 映射为IAM策略
            policy = self.permission_mapper.map_feishu_skills_to_policy(skills, role_mapping_id)
            
            return {
                "policy": policy.to_dict(),
                "skills": [skill.value for skill in skills],
                "success": True
            }
        except Exception as e:
            logger.error(f"创建策略失败: {e}")
            return {
                "error": str(e),
                "success": False
            }
    
    def get_feishu_skills_from_iam_scopes(self, iam_scopes: List[str]) -> Dict[str, Any]:
        """从IAM权限范围推断飞书Skills"""
        try:
            skills = self.permission_mapper.get_feishu_skills_from_iam_scopes(set(iam_scopes))
            
            return {
                "skills": [skill.value for skill in skills],
                "scopes": iam_scopes,
                "success": True
            }
        except Exception as e:
            logger.error(f"获取Skills失败: {e}")
            return {
                "error": str(e),
                "success": False
            }
    
    def list_available_skills(self) -> Dict[str, Any]:
        """列出所有可用的飞书Skills"""
        try:
            skills = self.permission_mapper.list_available_skills()
            
            return {
                "skills": skills,
                "count": len(skills),
                "success": True
            }
        except Exception as e:
            logger.error(f"列出Skills失败: {e}")
            return {
                "error": str(e),
                "success": False
            }
    
    # ==================== 系统健康检查 ====================
    
    def health_check(self) -> Dict[str, Any]:
        """系统健康检查"""
        checks = {}
        
        # 检查飞书API连接
        try:
            checks["feishu_api"] = self.client.check_health()
        except Exception as e:
            checks["feishu_api"] = False
            checks["feishu_api_error"] = str(e)
        
        # 检查同步服务状态
        sync_status = self.get_sync_status()
        checks["sync_service"] = not sync_status.get("is_syncing", False)
        
        # 检查认证服务
        checks["auth_service"] = True  # 简单检查
        
        # 检查权限映射
        checks["permission_mapper"] = len(self.permission_mapper.permission_mappings) > 0
        
        # 总体健康状态
        all_healthy = all(checks.values())
        
        return {
            "healthy": all_healthy,
            "checks": checks,
            "timestamp": time.time()
        }
    
    # ==================== 配置管理 ====================
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            "feishu_config": {
                "app_id": self.feishu_config.app_id[:10] + "..." if self.feishu_config.app_id else None,
                "app_type": self.feishu_config.app_type.value,
                "domain": self.feishu_config.domain
            },
            "oauth_config": {
                "redirect_uri": self.oauth_config.redirect_uri,
                "scopes": self.oauth_config.scopes
            },
            "sync_config": {
                "sync_departments": self.sync_config.sync_departments,
                "sync_users": self.sync_config.sync_users,
                "incremental_sync": self.sync_config.incremental_sync,
                "batch_size": self.sync_config.batch_size,
                "sync_interval": self.sync_config.sync_interval
            },
            "permission_mappings": len(self.permission_mapper.permission_mappings),
            "role_mappings": len(self.permission_mapper.role_mappings)
        }
    
    def reload_config(self) -> bool:
        """重新加载配置"""
        try:
            # 重新创建各服务组件
            self.client = FeishuClient(FeishuConfig.from_env())
            self.auth_service = FeishuAuthService(self.client, OAuth2Config.from_env())
            self.sync_service = FeishuOrgSyncService(self.client, None, SyncConfig.from_env())
            
            logger.info("配置重新加载成功")
            return True
        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
            return False


# 全局单例实例（可选）
_feishu_integration_service: Optional[FeishuIntegrationService] = None

def get_feishu_integration_service() -> FeishuIntegrationService:
    """获取飞书集成服务单例实例"""
    global _feishu_integration_service
    if _feishu_integration_service is None:
        _feishu_integration_service = FeishuIntegrationService()
    return _feishu_integration_service