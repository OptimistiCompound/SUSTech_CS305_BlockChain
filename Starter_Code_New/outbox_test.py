import unittest
import time
from unittest.mock import patch

import outbox

class DummyPeerManager:
    blacklist = set()
    rtt_tracker = {}

class DummyPeerDiscovery:
    known_peers = {
        "peer1": ("127.0.0.1", 5001),
        "peer2": ("127.0.0.1", 5002),
        "peer3": ("127.0.0.1", 5003),
    }
    peer_flags = {"peer1": "", "peer2": "NAT", "peer3": ""}
    reachable_by = {"peer2": {"peer1", "peer3"}}
    peer_config = {"fanout": 2, "peer1": {"type": "full"}, "peer2": {"type": "full"}, "peer3": {"type": "light"}}

class TestOutbox(unittest.TestCase):
    def setUp(self):
        outbox.queues.clear()
        outbox.peer_send_timestamps.clear()
        outbox.retries.clear()
        for k in outbox.drop_stats:
            outbox.drop_stats[k] = 0
        outbox.rate_limiter.tokens = outbox.rate_limiter.capacity

    @patch("outbox.peer_manager", DummyPeerManager)
    def test_enqueue_message_not_rate_limited(self):
        outbox.enqueue_message("peer1", "127.0.0.1", 5001, {"type": "PING"})
        self.assertTrue("peer1" in outbox.queues)
        self.assertTrue(len(outbox.queues["peer1"]["HIGH"]) == 1)

    @patch("outbox.peer_manager", DummyPeerManager)
    def test_enqueue_message_blacklist(self):
        DummyPeerManager.blacklist.add("peer1")
        outbox.enqueue_message("peer1", "127.0.0.1", 5001, {"type": "PING"})
        self.assertEqual(len(outbox.queues["peer1"]["HIGH"]), 0)

    def test_is_rate_limited(self):
        for _ in range(outbox.RATE_LIMIT):
            self.assertFalse(outbox.is_rate_limited("peerX"))
        self.assertTrue(outbox.is_rate_limited("peerX"))

    def test_classify_priority(self):
        self.assertEqual(outbox.classify_priority({"type": "PING"}), "HIGH")
        self.assertEqual(outbox.classify_priority({"type": "HELLO"}), "MEDIUM")
        self.assertEqual(outbox.classify_priority({"type": "RELAY"}), "LOW")
        self.assertEqual(outbox.classify_priority({"type": "FOO"}), "LOW")

    @patch("outbox.peer_manager", DummyPeerManager)
    @patch("outbox.peer_discovery", DummyPeerDiscovery)
    @patch("outbox.send_message", lambda ip, port, msg: True)
    def test_send_from_queue(self):
        outbox.enqueue_message("peer1", "127.0.0.1", 5001, {"type": "PING"})
        outbox.send_from_queue("self")
        time.sleep(0.05)
        # Message should be sent and removed from queue
        self.assertEqual(len(outbox.queues["peer1"]["HIGH"]), 0)

    @patch("outbox.peer_manager", DummyPeerManager)
    @patch("outbox.peer_discovery", DummyPeerDiscovery)
    def test_get_relay_peer(self):
        DummyPeerManager.rtt_tracker["peer1"] = 0.1
        DummyPeerManager.rtt_tracker["peer3"] = 0.05
        peer = outbox.get_relay_peer("self", "peer2")
        self.assertEqual(peer[0], "peer3")  # peer3 has lower rtt

    @patch("outbox.peer_manager", DummyPeerManager)
    @patch("outbox.peer_discovery", DummyPeerDiscovery)
    def test_gossip_message(self):
        outbox.gossip_message("self", {"type": "BLOCK"})
        # Should enqueue to two peers, as fanout=2

    def test_get_outbox_status(self):
        outbox.enqueue_message("peer1", "127.0.0.1", 5001, {"type": "TX"})
        status = outbox.get_outbox_status()
        self.assertIn("peer1", status)

    def test_get_drop_stats(self):
        outbox.drop_stats["BLOCK"] = 2
        ds = outbox.get_drop_stats()
        self.assertEqual(ds["BLOCK"], 2)

if __name__ == "__main__":
    unittest.main()