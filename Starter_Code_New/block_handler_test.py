import unittest
import time
import hashlib
from unittest.mock import patch

import block_handler

class TestBlockHandler(unittest.TestCase):
    def setUp(self):
        # 重置全局变量
        block_handler.received_blocks.clear()
        block_handler.header_store.clear()
        block_handler.orphan_blocks.clear()
        # 模拟 full 节点
        block_handler.peer_config.clear()
        block_handler.peer_config.update({"type": "full"})

    def test_create_dummy_block_normal(self):
        # 模拟有交易
        with patch("block_handler.get_recent_transactions", return_value=[{"id": "tx1"}, {"id": "tx2"}]):
            with patch("block_handler.clear_pool") as mock_clear_pool:
                block = block_handler.create_dummy_block("peer1", MALICIOUS_MODE=False)
                self.assertIsNotNone(block)
                self.assertEqual(block["peer_id"], "peer1")
                self.assertIn("block_id", block)
                self.assertEqual(block_handler.received_blocks[-1], block)
                mock_clear_pool.assert_called()

    def test_create_dummy_block_malicious(self):
        # 恶意模式生成区块ID不等于正常哈希
        with patch("block_handler.get_recent_transactions", return_value=[{"id": "tx1"}]):
            block = block_handler.create_dummy_block("peerX", MALICIOUS_MODE=True)
            expected_hash = block_handler.compute_block_hash(block)
            self.assertNotEqual(block["block_id"], expected_hash)
            self.assertEqual(block_handler.received_blocks[-1], block)

    def test_compute_block_hash_different(self):
        block1 = {
            "peer_id": "peer1",
            "timestamp": 1234567890,
            "previous_block_id": "GENESIS",
            "transactions": [{"id": "x"}],
            "message_id": "m1"
        }
        block2 = dict(block1)
        block2["timestamp"] = 1234567891
        hash1 = block_handler.compute_block_hash(block1)
        hash2 = block_handler.compute_block_hash(block2)
        self.assertNotEqual(hash1, hash2)

    def test_receive_block_full_vs_light(self):
        block = {
            "peer_id": "peer2",
            "timestamp": time.time(),
            "previous_block_id": "GENESIS",
            "block_id": "b1"
        }
        # full
        block_handler.peer_config["type"] = "full"
        block_handler.receive_block(block)
        self.assertIn(block, block_handler.received_blocks)
        # light
        block_handler.peer_config["type"] = "light"
        block_handler.receive_block(block)
        self.assertIn(
            {"peer_id": block["peer_id"], "timestamp": block["timestamp"], "block_id": block["block_id"], "previous_block_id": block["previous_block_id"]},
            block_handler.header_store
        )

    def test_get_block_by_id(self):
        block = {
            "peer_id": "peer3",
            "timestamp": time.time(),
            "previous_block_id": "GENESIS",
            "block_id": "findme"
        }
        block_handler.received_blocks.append(block)
        found = block_handler.get_block_by_id("findme")
        self.assertEqual(found, block)
        not_found = block_handler.get_block_by_id("unknown")
        self.assertIsNone(not_found)

    def test_handle_block_valid_and_orphan(self):
        # 首先准备一个创世区块
        genesis = {
            "peer_id": "p0",
            "timestamp": 1,
            "previous_block_id": "GENESIS",
            "block_id": "genesis_hash",
            "transactions": [],
            "message_id": "m0"
        }
        block_handler.received_blocks.append(genesis)
        # 生成一个有效区块
        next_block = {
            "peer_id": "p1",
            "timestamp": 2,
            "previous_block_id": "genesis_hash",
            "transactions": [],
            "message_id": "m1"
        }
        next_block["block_id"] = block_handler.compute_block_hash(next_block)
        # 应能被正常接收
        block_handler.handle_block(next_block, "p1")
        self.assertIn(next_block, block_handler.received_blocks)
        # 生成一个孤块（前置不存在）
        orphan = {
            "peer_id": "p2",
            "timestamp": 3,
            "previous_block_id": "not_exist",
            "transactions": [],
            "message_id": "m2"
        }
        orphan["block_id"] = block_handler.compute_block_hash(orphan)
        block_handler.handle_block(orphan, "p2")
        self.assertIn(orphan["block_id"], block_handler.orphan_blocks)

    def test_create_getblock(self):
        msg = block_handler.create_getblock("sender_id", ["id1", "id2"])
        self.assertEqual(msg["type"], "GETBLOCK")
        self.assertEqual(msg["sender"], "sender_id")
        self.assertEqual(msg["block_ids"], ["id1", "id2"])

    def test_request_block_sync(self):
        # 检查是否向所有 known_peers（非自己）发送了请求
        with patch("block_handler.known_peers", ["self", "peerA", "peerB"]):
            with patch("block_handler.enqueue_message") as mock_enqueue:
                with patch("block_handler.generate_message_id", return_value="mid"):
                    block_handler.request_block_sync("self")
                    # 应对 peerA, peerB 各发一次
                    targets = [call[0][1] for call in mock_enqueue.call_args_list]
                    self.assertIn("peerA", targets)
                    self.assertIn("peerB", targets)
                    self.assertNotIn("self", targets)

if __name__ == "__main__":
    unittest.main()