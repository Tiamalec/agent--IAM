"""
测试审计日志系统
"""
import json
import os
import tempfile
import pytest

from agent_iam.audit_logger import AuditLogger


class TestAuditLogger:
    """测试AuditLogger"""
    
    @pytest.fixture
    def temp_log_file(self):
        """创建临时日志文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            log_file = f.name
        
        yield log_file
        
        # 清理
        if os.path.exists(log_file):
            os.unlink(log_file)
    
    @pytest.fixture
    def audit_logger(self, temp_log_file):
        """创建AuditLogger实例"""
        return AuditLogger(log_file=temp_log_file)
    
    def test_log_event(self, audit_logger):
        """测试记录事件"""
        # 记录事件
        event = audit_logger.log_event(
            actor_id="user123",
            action="read",
            resource="data.txt",
            result="allow",
            details={"ip": "192.168.1.1"}
        )
        
        assert event.actor_id == "user123"
        assert event.action == "read"
        assert event.resource == "data.txt"
        assert event.result == "allow"
        assert event.details == {"ip": "192.168.1.1"}
        assert event.previous_hash is None  # 第一个事件
        assert event.current_hash is not None
        
        # 记录第二个事件
        event2 = audit_logger.log_event(
            actor_id="user456",
            action="write",
            resource="data.txt",
            result="deny"
        )
        
        assert event2.previous_hash == event.current_hash
    
    def test_load_events(self, audit_logger, temp_log_file):
        """测试加载事件"""
        # 记录一些事件
        events_to_log = [
            ("user1", "login", "system", "allow"),
            ("user2", "read", "doc1", "allow"),
            ("user1", "write", "doc2", "deny"),
        ]
        
        logged_events = []
        for actor_id, action, resource, result in events_to_log:
            event = audit_logger.log_event(actor_id, action, resource, result)
            logged_events.append(event)
        
        # 加载事件
        loaded_events = audit_logger.load_events()
        
        assert len(loaded_events) == len(logged_events)
        
        for i, (loaded, logged) in enumerate(zip(loaded_events, logged_events)):
            assert loaded.actor_id == logged.actor_id
            assert loaded.action == logged.action
            assert loaded.resource == logged.resource
            assert loaded.result == logged.result
    
    def test_verify_integrity(self, audit_logger):
        """测试完整性验证"""
        # 记录一些事件
        audit_logger.log_event("user1", "action1", "res1", "allow")
        audit_logger.log_event("user2", "action2", "res2", "deny")
        audit_logger.log_event("user3", "action3", "res3", "allow")
        
        # 完整性应该通过
        assert audit_logger.verify_integrity() is True
        
        # 篡改日志文件
        events = audit_logger.load_events()
        if events:
            # 修改第一个事件的资源字段
            with open(audit_logger.log_file, 'r') as f:
                lines = f.readlines()
            
            if lines:
                first_event = json.loads(lines[0])
                first_event['resource'] = "tampered_resource"
                lines[0] = json.dumps(first_event) + '\n'
                
                with open(audit_logger.log_file, 'w') as f:
                    f.writelines(lines)
                
                # 完整性应该失败
                assert audit_logger.verify_integrity() is False
    
    def test_get_events_by_actor(self, audit_logger):
        """测试按参与者获取事件"""
        # 记录事件
        audit_logger.log_event("user1", "read", "doc1", "allow")
        audit_logger.log_event("user2", "write", "doc2", "deny")
        audit_logger.log_event("user1", "delete", "doc3", "allow")
        audit_logger.log_event("user3", "read", "doc1", "allow")
        
        # 获取user1的事件
        user1_events = audit_logger.get_events_by_actor("user1")
        assert len(user1_events) == 2
        
        for event in user1_events:
            assert event.actor_id == "user1"
        
        # 获取user2的事件
        user2_events = audit_logger.get_events_by_actor("user2")
        assert len(user2_events) == 1
        assert user2_events[0].action == "write"
    
    def test_get_events_by_resource(self, audit_logger):
        """测试按资源获取事件"""
        # 记录事件
        audit_logger.log_event("user1", "read", "doc1", "allow")
        audit_logger.log_event("user2", "write", "doc2", "deny")
        audit_logger.log_event("user1", "read", "doc1", "allow")  # 再次读取
        
        # 获取doc1的事件
        doc1_events = audit_logger.get_events_by_resource("doc1")
        assert len(doc1_events) == 2
        
        for event in doc1_events:
            assert event.resource == "doc1"
    
    def test_get_events_by_action(self, audit_logger):
        """测试按操作获取事件"""
        # 记录事件
        audit_logger.log_event("user1", "read", "doc1", "allow")
        audit_logger.log_event("user2", "write", "doc2", "deny")
        audit_logger.log_event("user3", "read", "doc3", "allow")
        
        # 获取read操作的事件
        read_events = audit_logger.get_events_by_action("read")
        assert len(read_events) == 2
        
        for event in read_events:
            assert event.action == "read"
    
    def test_clear_logs(self, audit_logger):
        """测试清空日志"""
        # 记录一些事件
        audit_logger.log_event("user1", "action1", "res1", "allow")
        audit_logger.log_event("user2", "action2", "res2", "deny")
        
        # 清空日志
        audit_logger.clear_logs()
        
        # 验证日志为空
        events = audit_logger.load_events()
        assert len(events) == 0
        
        # 验证last_hash被重置
        assert audit_logger.last_hash is None