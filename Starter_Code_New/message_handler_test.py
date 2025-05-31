# message_handler_test.py
import unittest
import time
from collections import defaultdict

# from message_handler import is_inbound_limited
# from message_handler import INBOUND_TIME_WINDOW
# from message_handler import INBOUND_RATE_LIMIT

INBOUND_TIME_WINDOW = 10
INBOUND_RATE_LIMIT  = 10

'''检查是否超出入站消息速率限制'''
def is_inbound_limited(peer_id):
    # Record the timestamp when receiving message from a sender.
    cur_time = time.time()
    peer_inbound_timestamps[peer_id].append(time.time())
    # Check if the number of messages sent by the sender exceeds `INBOUND_RATE_LIMIT` during the `INBOUND_TIME_WINDOW`. If yes, return `TRUE`. If not, return `FALSE`.
    limit_cnt = 0
    for timestamp in peer_inbound_timestamps[peer_id]:
        if (cur_time <= timestamp + INBOUND_TIME_WINDOW):
            limit_cnt += 1
        if (limit_cnt >= INBOUND_RATE_LIMIT):
            return True
    return False

class TestIsInboundLimited(unittest.TestCase):
    def setUp(self):
        """在每个测试用例前重置时间戳记录"""
        global peer_inbound_timestamps
        peer_inbound_timestamps = defaultdict(list)
    
    def test_no_messages(self):
        """测试没有消息时返回False"""
        self.assertFalse(is_inbound_limited("peer1"))
    
    def test_below_limit(self):
        """测试消息数量低于限制时返回False"""
        for _ in range(INBOUND_RATE_LIMIT - 1):
            self.assertFalse(is_inbound_limited("peer1"))
    
    def test_at_limit(self):
        """测试消息数量等于限制时返回True"""
        for _ in range(INBOUND_RATE_LIMIT - 1):
            self.assertFalse(is_inbound_limited("peer1"))
        self.assertTrue(is_inbound_limited("peer1"))
    
    def test_above_limit(self):
        """测试消息数量超过限制时返回True"""
        for _ in range(INBOUND_RATE_LIMIT + 1):
            is_inbound_limited("peer1")
        self.assertTrue(is_inbound_limited("peer1"))
    
    def test_time_window_expired(self):
        """测试时间窗口过期后消息不计入限制"""
        # 发送刚好达到限制的消息
        for _ in range(INBOUND_RATE_LIMIT):
            is_inbound_limited("peer1")
        
        # 等待时间窗口过期
        time.sleep(INBOUND_TIME_WINDOW + 1)
        
        # 新消息不应触发限制
        self.assertFalse(is_inbound_limited("peer1"))
    
    def test_multiple_peers(self):
        """测试多个peer的消息计数相互独立"""
        # peer1达到限制
        for _ in range(INBOUND_RATE_LIMIT):
            is_inbound_limited("peer1")
        self.assertTrue(is_inbound_limited("peer1"))
        
        # peer2未达到限制
        self.assertFalse(is_inbound_limited("peer2"))
    
    def test_mixed_timestamps(self):
        """测试混合新旧时间戳的情况"""
        # 添加一些过期的时间戳
        old_time = time.time() - INBOUND_TIME_WINDOW - 1
        peer_inbound_timestamps["peer1"].extend([old_time] * (INBOUND_RATE_LIMIT - 2))
        
        # 添加一些有效的时间戳
        for _ in range(INBOUND_RATE_LIMIT - 1):
            is_inbound_limited("peer1")
        
        # 应该刚好达到限制
        self.assertTrue(is_inbound_limited("peer1"))

if __name__ == '__main__':
    unittest.main()
