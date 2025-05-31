import unittest
import time
from unittest.mock import patch

from peer_discovery import start_peer_discovery, known_peers, peer_flags, peer_config, reachable_by

class TestPeerDiscovery(unittest.TestCase):
    def setUp(self):
        # 清空全局状态
        known_peers.clear()
        peer_flags.clear()
        peer_config.clear()
        reachable_by.clear()

        # 构造测试网络
        self.config = {
            "peers": {
                "5000": {"ip": "10.0.0.1", "port": 5000, "localnetworkid": 1},
                "5001": {"ip": "10.0.0.2", "port": 5001, "localnetworkid": 1},
                "5002": {"ip": "10.0.0.3", "port": 5002, "nat": True, "localnetworkid": 1},
                "5003": {"ip": "10.0.1.1", "port": 5003, "nat": True, "localnetworkid": 2},
                "5004": {"ip": "10.0.2.1", "port": 5004}  # 无localnetworkid
            }
        }
        self.self_id = "5000"
        self.self_info = self.config["peers"][self.self_id]
        for peer_id, peer_info in self.config["peers"].items():
            known_peers[peer_id] = (peer_info["ip"], peer_info["port"])
            peer_config[peer_id] = peer_info
            peer_flags[peer_id] = {
                "nat": peer_info.get("nat", False),
                "light": peer_info.get("light", False)
            }

    @patch('outbox.enqueue_message')
    @patch('peer_discovery.generate_message_id')
    def test_start_peer_discovery(self, mock_generate_message_id, mock_enqueue_message):
        mock_generate_message_id.return_value = "msg_abc"

        start_peer_discovery(self.self_id, self.self_info)
        time.sleep(0.1)  # 等待线程执行

        expected_hello_msg = {
            "message_type": "HELLO",
            "sender_id": "5000",
            "ip": "10.0.0.1",
            "port": 5000,
            "flags": {"nat": False, "light": False},
            "localnetworkid": 1,
            "message_id": "msg_abc"
        }

        # 5000应能reach 5001和5002（同localnetworkid），不能reach 5003（不同localnetworkid且有NAT），5004（无localnetworkid，视为主网）
        called_ids = [call[0][0] for call in mock_enqueue_message.call_args_list]
        self.assertIn("5001", called_ids)
        self.assertIn("5002", called_ids)
        self.assertNotIn("5003", called_ids)
        self.assertIn("5004", called_ids)  # 5004无localnetworkid，非NAT，主网peer，能被reach

        # 检查消息内容
        mock_enqueue_message.assert_any_call("5001", "10.0.0.1", 5000, expected_hello_msg)
        mock_enqueue_message.assert_any_call("5002", "10.0.0.1", 5000, expected_hello_msg)

        # 检查reachable_by结构
        self.assertIn("5001", reachable_by[self.self_id])
        self.assertIn("5002", reachable_by[self.self_id])
        self.assertNotIn("5003", reachable_by[self.self_id])

if __name__ == '__main__':
    unittest.main()
