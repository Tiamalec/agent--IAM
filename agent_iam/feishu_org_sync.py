"""
飞书组织架构同步服务
将飞书部门和用户数据同步到IAM系统
"""
import os
import time
import json
import logging
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .feishu_client import FeishuClient
from .models import Actor, ActorType
from .auth_engine import AuthorizationEngine

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    """同步统计信息"""
    total_departments: int = 0
    synced_departments: int = 0
    failed_departments: int = 0
    total_users: int = 0
    synced_users: int = 0
    failed_users: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    @property
    def duration(self) -> float:
        """同步持续时间"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.total_departments + self.total_users
        if total == 0:
            return 0.0
        successful = self.synced_departments + self.synced_users
        return successful / total
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_departments": self.total_departments,
            "synced_departments": self.synced_departments,
            "failed_departments": self.failed_departments,
            "total_users": self.total_users,
            "synced_users": self.synced_users,
            "failed_users": self.failed_users,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "success_rate": self.success_rate
        }


@dataclass
class SyncConfig:
    """同步配置"""
    sync_departments: bool = True
    sync_users: bool = True
    incremental_sync: bool = True  # 增量同步
    batch_size: int = 100  # 每批处理数量
    max_retries: int = 3  # 最大重试次数
    retry_delay: int = 5  # 重试延迟（秒）
    sync_interval: int = 3600  # 同步间隔（秒）
    last_sync_time: Optional[float] = None
    
    @classmethod
    def from_env(cls) -> "SyncConfig":
        """从环境变量创建配置"""
        return cls(
            sync_departments=os.environ.get("FEISHU_SYNC_DEPARTMENTS", "true").lower() == "true",
            sync_users=os.environ.get("FEISHU_SYNC_USERS", "true").lower() == "true",
            incremental_sync=os.environ.get("FEISHU_INCREMENTAL_SYNC", "true").lower() == "true",
            batch_size=int(os.environ.get("FEISHU_SYNC_BATCH_SIZE", "100")),
            sync_interval=int(os.environ.get("FEISHU_SYNC_INTERVAL", "3600"))
        )


class FeishuOrgSyncService:
    """飞书组织架构同步服务"""
    
    def __init__(self, feishu_client: Optional[FeishuClient] = None,
                 auth_engine: Optional[AuthorizationEngine] = None,
                 sync_config: Optional[SyncConfig] = None):
        self.feishu_client = feishu_client or FeishuClient()
        self.auth_engine = auth_engine or AuthorizationEngine()
        self.sync_config = sync_config or SyncConfig.from_env()
        self.sync_stats = SyncStats()
        
        # 存储部门映射关系
        self.department_mapping: Dict[str, Dict[str, Any]] = {}
        self.user_mapping: Dict[str, Dict[str, Any]] = {}
        
        # 同步状态
        self.is_syncing = False
        self.last_sync_result: Optional[Dict[str, Any]] = None
    
    def sync_full_organization(self) -> SyncStats:
        """全量同步组织架构"""
        if self.is_syncing:
            logger.warning("同步已在运行中，跳过此次请求")
            return self.sync_stats
        
        self.is_syncing = True
        self.sync_stats = SyncStats()
        
        try:
            logger.info("开始全量同步飞书组织架构")
            
            # 同步部门
            if self.sync_config.sync_departments:
                self._sync_departments_full()
            
            # 同步用户
            if self.sync_config.sync_users:
                self._sync_users_full()
            
            # 更新同步时间
            self.sync_config.last_sync_time = time.time()
            
            logger.info(f"全量同步完成: {self.sync_stats.to_dict()}")
            
        except Exception as e:
            logger.error(f"全量同步失败: {e}")
            raise
        finally:
            self.is_syncing = False
            self.sync_stats.end_time = time.time()
        
        return self.sync_stats
    
    def sync_incremental(self) -> SyncStats:
        """增量同步组织架构"""
        if self.is_syncing:
            logger.warning("同步已在运行中，跳过此次请求")
            return self.sync_stats
        
        if not self.sync_config.incremental_sync:
            logger.info("增量同步已禁用，执行全量同步")
            return self.sync_full_organization()
        
        self.is_syncing = True
        self.sync_stats = SyncStats()
        
        try:
            logger.info("开始增量同步飞书组织架构")
            
            # 简单实现：如果从未同步过，执行全量同步
            if not self.sync_config.last_sync_time:
                logger.info("首次同步，执行全量同步")
                return self.sync_full_organization()
            
            # 实际项目中应该使用飞书的增量API
            # 这里实现一个基于时间戳的模拟增量同步
            logger.info("执行增量同步")
            
            # 1. 同步部门（增量）
            if self.sync_config.sync_departments:
                self._sync_departments_incremental()
            
            # 2. 同步用户（增量）
            if self.sync_config.sync_users:
                self._sync_users_incremental()
            
            # 3. 清理已删除的实体
            self._cleanup_deleted_entities()
            
            # 更新同步时间
            self.sync_config.last_sync_time = time.time()
            
            logger.info(f"增量同步完成: {self.sync_stats.to_dict()}")
            
        except Exception as e:
            logger.error(f"增量同步失败: {e}")
            raise
        finally:
            self.is_syncing = False
            self.sync_stats.end_time = time.time()
        
        return self.sync_stats
    
    def _sync_departments_incremental(self) -> None:
        """增量同步部门"""
        logger.info("开始增量同步部门")
        
        try:
            # 获取所有部门（实际项目中应该使用增量API）
            departments = self.feishu_client.list_departments(fetch_child=True)
            
            # 过滤出新增或更新的部门
            for dept in departments:
                dept_id = dept["department_id"]
                existing_dept = self.department_mapping.get(dept_id)
                
                # 检查是否需要更新
                if not existing_dept or self._should_update_department(dept, existing_dept):
                    try:
                        # 创建或更新部门Actor
                        department_actor = self._create_department_actor(dept)
                        
                        # 更新部门映射
                        self.department_mapping[dept_id] = {
                            "actor_id": department_actor.id,
                            "name": dept["name"],
                            "parent_id": dept["parent_department_id"],
                            "synced_at": time.time()
                        }
                        
                        self.sync_stats.synced_departments += 1
                        logger.debug(f"同步部门成功: {dept['name']} ({dept['department_id']})")
                        
                    except Exception as e:
                        self.sync_stats.failed_departments += 1
                        logger.error(f"同步部门失败 {dept.get('name', '未知')}: {e}")
            
            self.sync_stats.total_departments = len(departments)
            logger.info(f"部门增量同步完成: {self.sync_stats.synced_departments}/{self.sync_stats.total_departments}")
            
        except Exception as e:
            logger.error(f"获取部门列表失败: {e}")
            raise
    
    def _sync_users_incremental(self) -> None:
        """增量同步用户"""
        logger.info("开始增量同步用户")
        
        try:
            # 分页获取所有用户（实际项目中应该使用增量API）
            page_token = None
            total_users = 0
            
            while True:
                result = self.feishu_client.list_users(
                    department_id=None,  # 获取所有用户
                    page_size=self.sync_config.batch_size,
                    page_token=page_token
                )
                
                users = result["users"]
                
                for user in users:
                    user_id = user["user_id"]
                    existing_user = self.user_mapping.get(user_id)
                    
                    # 检查是否需要更新
                    if not existing_user or self._should_update_user(user):
                        try:
                            # 获取用户详情
                            user_detail = self.feishu_client.get_user_detail(user_id)
                            
                            # 创建或更新用户Actor
                            user_actor = self._create_user_actor(user_detail)
                            
                            # 更新用户映射
                            self.user_mapping[user_id] = {
                                "actor_id": user_actor.id,
                                "name": user["name"],
                                "email": user.get("email"),
                                "department_ids": user.get("department_ids", []),
                                "synced_at": time.time()
                            }
                            
                            # 记录部门-用户关系
                            self._link_user_to_departments(user_id, user.get("department_ids", []))
                            
                            self.sync_stats.synced_users += 1
                            logger.debug(f"同步用户成功: {user['name']} ({user['user_id']})")
                            
                        except Exception as e:
                            self.sync_stats.failed_users += 1
                            logger.error(f"同步用户失败 {user.get('name', '未知')}: {e}")
                
                total_users += len(users)
                
                if not result["has_more"]:
                    break
                
                page_token = result["page_token"]
                logger.info(f"已同步 {total_users} 个用户，继续下一页...")
            
            self.sync_stats.total_users = total_users
            logger.info(f"用户增量同步完成: {self.sync_stats.synced_users}/{self.sync_stats.total_users}")
            
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            raise
    
    def _cleanup_deleted_entities(self) -> None:
        """清理已删除的实体"""
        logger.info("开始清理已删除的实体")
        
        try:
            # 获取当前所有部门和用户
            current_departments = set()
            current_users = set()
            
            # 获取所有部门
            departments = self.feishu_client.list_departments(fetch_child=True)
            for dept in departments:
                current_departments.add(dept["department_id"])
            
            # 获取所有用户
            page_token = None
            while True:
                result = self.feishu_client.list_users(
                    department_id=None,
                    page_size=self.sync_config.batch_size,
                    page_token=page_token
                )
                for user in result["users"]:
                    current_users.add(user["user_id"])
                if not result["has_more"]:
                    break
                page_token = result["page_token"]
            
            # 清理已删除的部门
            deleted_departments = []
            for dept_id in list(self.department_mapping.keys()):
                if dept_id not in current_departments:
                    deleted_departments.append(dept_id)
                    del self.department_mapping[dept_id]
            
            # 清理已删除的用户
            deleted_users = []
            for user_id in list(self.user_mapping.keys()):
                if user_id not in current_users:
                    deleted_users.append(user_id)
                    del self.user_mapping[user_id]
            
            logger.info(f"清理完成: 删除了 {len(deleted_departments)} 个部门, {len(deleted_users)} 个用户")
            
        except Exception as e:
            logger.error(f"清理已删除实体失败: {e}")
    
    def _should_update_department(self, dept: Dict[str, Any], existing_dept: Dict[str, Any]) -> bool:
        """判断部门是否需要更新"""
        # 简单实现：基于同步时间
        synced_at = existing_dept.get("synced_at", 0)
        # 如果同步时间超过1小时，认为需要更新
        return time.time() - synced_at > 3600
    
    def _should_update_user(self, user: Dict[str, Any]) -> bool:
        """判断用户是否需要更新"""
        # 简单实现：基于用户ID检查
        user_id = user["user_id"]
        existing_user = self.user_mapping.get(user_id)
        if not existing_user:
            return True
        
        # 如果同步时间超过1小时，认为需要更新
        synced_at = existing_user.get("synced_at", 0)
        return time.time() - synced_at > 3600
    
    def _sync_departments_full(self) -> None:
        """全量同步部门"""
        logger.info("开始同步部门数据")
        
        try:
            # 获取所有部门
            departments = self.feishu_client.list_departments(fetch_child=True)
            
            self.sync_stats.total_departments = len(departments)
            
            for dept in departments:
                try:
                    # 将部门转换为IAM组织结构
                    department_actor = self._create_department_actor(dept)
                    
                    # 存储部门映射
                    self.department_mapping[dept["department_id"]] = {
                        "actor_id": department_actor.id,
                        "name": dept["name"],
                        "parent_id": dept["parent_department_id"],
                        "synced_at": time.time()
                    }
                    
                    self.sync_stats.synced_departments += 1
                    
                    logger.debug(f"同步部门成功: {dept['name']} ({dept['department_id']})")
                    
                except Exception as e:
                    self.sync_stats.failed_departments += 1
                    logger.error(f"同步部门失败 {dept.get('name', '未知')}: {e}")
            
            logger.info(f"部门同步完成: {self.sync_stats.synced_departments}/{self.sync_stats.total_departments}")
            
        except Exception as e:
            logger.error(f"获取部门列表失败: {e}")
            raise
    
    def _sync_users_full(self) -> None:
        """全量同步用户"""
        logger.info("开始同步用户数据")
        
        try:
            # 分页获取所有用户
            page_token = None
            total_users = 0
            
            while True:
                result = self.feishu_client.list_users(
                    department_id=None,  # 获取所有用户
                    page_size=self.sync_config.batch_size,
                    page_token=page_token
                )
                
                users = result["users"]
                self.sync_stats.total_users += len(users)
                
                for user in users:
                    try:
                        # 获取用户详情（包含更多信息）
                        user_detail = self.feishu_client.get_user_detail(user["user_id"])
                        
                        # 将用户转换为IAM Actor
                        user_actor = self._create_user_actor(user_detail)
                        
                        # 存储用户映射
                        self.user_mapping[user["user_id"]] = {
                            "actor_id": user_actor.id,
                            "name": user["name"],
                            "email": user.get("email"),
                            "department_ids": user.get("department_ids", []),
                            "synced_at": time.time()
                        }
                        
                        self.sync_stats.synced_users += 1
                        
                        # 记录部门-用户关系
                        self._link_user_to_departments(user["user_id"], user.get("department_ids", []))
                        
                        logger.debug(f"同步用户成功: {user['name']} ({user['user_id']})")
                        
                    except Exception as e:
                        self.sync_stats.failed_users += 1
                        logger.error(f"同步用户失败 {user.get('name', '未知')}: {e}")
                
                total_users += len(users)
                
                if not result["has_more"]:
                    break
                
                page_token = result["page_token"]
                logger.info(f"已同步 {total_users} 个用户，继续下一页...")
            
            logger.info(f"用户同步完成: {self.sync_stats.synced_users}/{self.sync_stats.total_users}")
            
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            raise
    
    def _create_department_actor(self, department: Dict[str, Any]) -> Actor:
        """创建部门Actor"""
        actor_id = f"feishu_dept_{department['department_id']}"
        
        attributes = {
            "feishu_department_id": department["department_id"],
            "feishu_department_name": department["name"],
            "parent_department_id": department["parent_department_id"],
            "leader_user_id": department.get("leader_user_id"),
            "member_count": department.get("member_count", 0),
            "department_status": department.get("status"),
            "source": "feishu",
            "sync_timestamp": time.time()
        }
        
        return Actor(
            id=actor_id,
            name=department["name"],
            type=ActorType.IAM_CONTROLLER,  # 部门作为IAM控制器
            attributes=attributes
        )
    
    def _create_user_actor(self, user_detail: Dict[str, Any]) -> Actor:
        """创建用户Actor"""
        actor_id = f"feishu_user_{user_detail['user_id']}"
        
        attributes = {
            "feishu_user_id": user_detail["user_id"],
            "feishu_name": user_detail["name"],
            "feishu_email": user_detail.get("email"),
            "feishu_mobile": user_detail.get("mobile"),
            "feishu_employee_id": user_detail.get("employee_id"),
            "department_ids": user_detail.get("department_ids", []),
            "leader_user_id": user_detail.get("leader_user_id"),
            "city": user_detail.get("city"),
            "country": user_detail.get("country"),
            "work_station": user_detail.get("work_station"),
            "join_time": user_detail.get("join_time"),
            "employee_type": user_detail.get("employee_type"),
            "source": "feishu",
            "sync_timestamp": time.time()
        }
        
        # 添加自定义属性
        custom_attrs = user_detail.get("custom_attrs", {})
        for key, value in custom_attrs.items():
            attributes[f"feishu_custom_{key}"] = value
        
        return Actor(
            id=actor_id,
            name=user_detail["name"],
            type=ActorType.USER,
            attributes=attributes
        )
    
    def _link_user_to_departments(self, user_id: str, department_ids: List[str]) -> None:
        """建立用户-部门关联"""
        for dept_id in department_ids:
            if dept_id in self.department_mapping:
                dept_info = self.department_mapping[dept_id]
                # 这里可以存储关联关系，用于后续权限分配
                logger.debug(f"关联用户 {user_id} 到部门 {dept_id}")
    
    def get_department_mapping(self) -> Dict[str, Dict[str, Any]]:
        """获取部门映射关系"""
        return self.department_mapping.copy()
    
    def get_user_mapping(self) -> Dict[str, Dict[str, Any]]:
        """获取用户映射关系"""
        return self.user_mapping.copy()
    
    def find_user_by_feishu_id(self, feishu_user_id: str) -> Optional[Dict[str, Any]]:
        """通过飞书用户ID查找用户映射"""
        return self.user_mapping.get(feishu_user_id)
    
    def find_department_by_feishu_id(self, feishu_dept_id: str) -> Optional[Dict[str, Any]]:
        """通过飞书部门ID查找部门映射"""
        return self.department_mapping.get(feishu_dept_id)
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        status = {
            "is_syncing": self.is_syncing,
            "last_sync_time": self.sync_config.last_sync_time,
            "department_count": len(self.department_mapping),
            "user_count": len(self.user_mapping),
            "sync_config": {
                "sync_departments": self.sync_config.sync_departments,
                "sync_users": self.sync_config.sync_users,
                "incremental_sync": self.sync_config.incremental_sync,
                "batch_size": self.sync_config.batch_size,
                "sync_interval": self.sync_config.sync_interval
            }
        }
        
        if self.last_sync_result:
            status["last_sync_result"] = self.last_sync_result
        
        return status
    
    def run_scheduled_sync(self) -> bool:
        """运行计划同步"""
        if not self.sync_config.last_sync_time:
            # 首次运行
            logger.info("执行首次同步")
            self.sync_full_organization()
            return True
        
        current_time = time.time()
        time_since_last_sync = current_time - self.sync_config.last_sync_time
        
        if time_since_last_sync >= self.sync_config.sync_interval:
            logger.info(f"距离上次同步已过去 {time_since_last_sync:.0f} 秒，执行同步")
            self.sync_incremental()
            return True
        
        logger.debug(f"距离上次同步 {time_since_last_sync:.0f} 秒，未达到间隔 {self.sync_config.sync_interval} 秒")
        return False