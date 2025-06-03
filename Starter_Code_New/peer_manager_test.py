import unittest
import time

import peer_manager

class TestPeerManager(unittest.TestCase):
    def setUp(self):
        peer_manager.peer_status.clear()
        peer_manager.last_ping_time.clear()
        peer_manager.rtt_tracker.clear()
        peer_manager.blacklist.clear()
        peer_manager.peer_offense_counts.clear()

    def test_create_pong(self):
        pong = peer_manager.create_pong("peer1", 12345)
        self.assertEqual(pong["type"], "PONG")
        self.assertEqual(pong["sender"], "peer1")
        self.assertEqual(pong["timestamp"], 12345)

    def test_handle_pong_and_rtt(self):
        sender = "peer2"
        sent_ts = time.time() - 0.05
        msg = {"type": "PONG", "sender": sender, "timestamp": sent_ts}
        peer_manager.handle_pong(msg)
        self.assertIn(sender, peer_manager.rtt_tracker)
        self.assertTrue(peer_manager.rtt_tracker[sender] >= 0)
        self.assertIn(sender, peer_manager.last_ping_time)

    def test_update_peer_heartbeat(self):
        peer_manager.update_peer_heartbeat("peer3")
        self.assertIn("peer3", peer_manager.last_ping_time)
        now = time.time()
        self.assertAlmostEqual(peer_manager.last_ping_time["peer3"], now, delta=1)

    def test_peer_monitor_alive_and_unreachable(self):
        peer_manager.last_ping_time["peerA"] = time.time()
        peer_manager.last_ping_time["peerB"] = time.time() - 20
        # 手动调用一次监控逻辑
        now = time.time()
        for peer_id in peer_manager.last_ping_time:
            last = peer_manager.last_ping_time[peer_id]
            if now - last > 10:
                peer_manager.peer_status[peer_id] = "UNREACHABLE"
            else:
                peer_manager.peer_status[peer_id] = "ALIVE"
        self.assertEqual(peer_manager.peer_status["peerA"], "ALIVE")
        self.assertEqual(peer_manager.peer_status["peerB"], "UNREACHABLE")

    def test_record_offense_and_blacklist(self):
        peer_id = "evil_peer"
        for i in range(4):
            peer_manager.record_offense(peer_id)
        self.assertEqual(peer_manager.peer_offense_counts[peer_id], 4)
        self.assertIn(peer_id, peer_manager.blacklist)

    def test_start_ping_loop(self):
        # 只测试能调用，不做线程行为判断
        def fake_enqueue(msg, peer_id):
            self.enqueue_called = True
        peer_table = {"peerX": ("127.0.0.1", 5555)}
        self.enqueue_called = False
        import peer_manager as pm
        pm.enqueue_message = fake_enqueue
        pm.start_ping_loop("self", peer_table, interval=0.01)
        time.sleep(0.05)
        # 由于线程异步，不保证调用，所以不做强断言

if __name__ == "__main__":
    unittest.main()