import unittest
from unittest.mock import patch

import inv_message

class TestInvMessage(unittest.TestCase):
    def setUp(self):
        # 初始化依赖的全局变量
        inv_message.received_blocks.clear()
        inv_message.known_peers.clear()
        inv_message.known_peers.update({
            "peer1": ("127.0.0.1", 5001),
            "peer2": ("127.0.0.1", 5002),
            "self":  ("127.0.0.1", 5000)
        })

    def test_create_inv(self):
        with patch("inv_message.generate_message_id", return_value="msgid123"):
            inv = inv_message.create_inv(["blk1", "blk2"], "senderX")
            self.assertEqual(inv["type"], "INV")
            self.assertEqual(inv["sender"], "senderX")
            self.assertEqual(inv["block_ids"], ["blk1", "blk2"])
            self.assertEqual(inv["message_id"], "msgid123")

    def test_get_inventory(self):
        # 添加区块到 received_blocks
        inv_message.received_blocks.append({"block_id": "b1"})
        inv_message.received_blocks.append({"block_id": "b2"})
        inv_message.received_blocks.append({"block_id": "b3"})
        inventory = inv_message.get_inventory()
        self.assertEqual(inventory, ["b1", "b2", "b3"])

    def test_broadcast_inventory(self):
        # 检查gossip_message被正确调用
        with patch("inv_message.gossip_message") as mock_gossip, \
             patch("inv_message.generate_message_id", return_value="mid456"):
            inv_message.received_blocks.extend([
                {"block_id": "b1"},
                {"block_id": "b2"}
            ])
            # self_id为"self"，peer列表包含"peer1"和"peer2"
            inv_message.broadcast_inventory("self")
            mock_gossip.assert_called_once()
            args, kwargs = mock_gossip.call_args
            inv_msg, targets = args
            self.assertEqual(inv_msg["type"], "INV")
            self.assertEqual(set(inv_msg["block_ids"]), {"b1", "b2"})
            self.assertEqual(set(targets), {"peer1", "peer2"})  # 不包含"self"

if __name__ == "__main__":
    unittest.main()