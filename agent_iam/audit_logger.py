"""
审计日志系统：hash-chain防篡改
"""
import hashlib
import json
import time
from typing import List, Optional, Dict, Any

from .models import AuditEvent


class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self, log_file: str = "audit_log.jsonl"):
        self.log_file = log_file
        self.last_hash: Optional[str] = None
        
        # 如果日志文件已存在，恢复last_hash
        self._recover_last_hash()
        
    def _calculate_hash(self, event: AuditEvent) -> str:
        """计算事件的哈希值"""
        # 创建一个不包含哈希字段的字典
        hash_dict = {
            "id": event.id,
            "timestamp": event.timestamp,
            "actor_id": event.actor_id,
            "action": event.action,
            "resource": event.resource,
            "result": event.result,
            "details": event.details,
            "previous_hash": event.previous_hash  # 包含previous_hash，因为它是链的一部分
        }
        
        event_str = json.dumps(hash_dict, sort_keys=True)
        return hashlib.sha256(event_str.encode('utf-8')).hexdigest()
    
    def log_event(self, actor_id: str, action: str, resource: str, 
                 result: str, details: Dict[str, Any] = None) -> AuditEvent:
        """记录审计事件"""
        if details is None:
            details = {}
        
        # 创建事件
        event = AuditEvent(
            actor_id=actor_id,
            action=action,
            resource=resource,
            result=result,
            details=details,
            previous_hash=self.last_hash
        )
        
        # 计算当前哈希
        event.current_hash = self._calculate_hash(event)
        
        # 更新最后哈希
        self.last_hash = event.current_hash
        
        # 写入文件
        self._write_to_file(event)
        
        return event
    
    def _write_to_file(self, event: AuditEvent) -> None:
        """将事件写入文件"""
        event_dict = event.to_dict()
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(event_dict) + '\n')
    
    def verify_integrity(self) -> bool:
        """验证审计日志的完整性（hash-chain）"""
        events = self.load_events()
        
        if not events:
            return True
        
        previous_hash = None
        for event in events:
            # 重新计算哈希
            calculated_hash = self._calculate_hash(event)
            
            # 检查存储的哈希是否匹配
            if event.current_hash != calculated_hash:
                return False
            
            # 检查与前一个事件的链接
            if event.previous_hash != previous_hash:
                return False
            
            previous_hash = event.current_hash
        
        return True
    
    def load_events(self) -> List[AuditEvent]:
        """从文件加载审计事件"""
        events = []
        
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    event_dict = json.loads(line)
                    
                    # 转换为AuditEvent对象
                    event = AuditEvent(
                        id=event_dict['id'],
                        timestamp=event_dict['timestamp'],
                        actor_id=event_dict['actor_id'],
                        action=event_dict['action'],
                        resource=event_dict['resource'],
                        result=event_dict['result'],
                        details=event_dict['details'],
                        previous_hash=event_dict.get('previous_hash'),
                        current_hash=event_dict.get('current_hash')
                    )
                    
                    events.append(event)
        except FileNotFoundError:
            pass
        
        return events
    
    def get_events_by_actor(self, actor_id: str) -> List[AuditEvent]:
        """根据参与者ID获取事件"""
        events = self.load_events()
        return [e for e in events if e.actor_id == actor_id]
    
    def get_events_by_resource(self, resource: str) -> List[AuditEvent]:
        """根据资源获取事件"""
        events = self.load_events()
        return [e for e in events if e.resource == resource]
    
    def get_events_by_action(self, action: str) -> List[AuditEvent]:
        """根据操作获取事件"""
        events = self.load_events()
        return [e for e in events if e.action == action]
    
    def _recover_last_hash(self) -> None:
        """从现有日志恢复last_hash"""
        events = self.load_events()
        if events:
            self.last_hash = events[-1].current_hash
    
    def clear_logs(self) -> None:
        """清空审计日志"""
        with open(self.log_file, 'w') as f:
            pass
        self.last_hash = None