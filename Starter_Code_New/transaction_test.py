import unittest
import time

from transaction import (
    TransactionMessage,
    tx_pool,
    tx_ids,
    add_transaction,
    get_recent_transactions,
    clear_pool,
)

class TestTransaction(unittest.TestCase):
    def setUp(self):
        clear_pool()

    def test_add_transaction_once(self):
        tx = TransactionMessage("peerA", "peerB", 10)
        add_transaction(tx)
        self.assertIn(tx, tx_pool)
        self.assertIn(tx.id, tx_ids)

    def test_add_transaction_duplicate(self):
        tx = TransactionMessage("peerA", "peerB", 10)
        add_transaction(tx)
        add_transaction(tx)
        # 只会有一条
        self.assertEqual(tx_pool.count(tx), 1)
        self.assertEqual(len(tx_ids), 1)

    def test_get_recent_transactions(self):
        tx1 = TransactionMessage("peerA", "peerB", 5)
        tx2 = TransactionMessage("peerA", "peerC", 12)
        add_transaction(tx1)
        add_transaction(tx2)
        recents = get_recent_transactions()
        self.assertTrue(any(tx["id"] == tx1.id for tx in recents))
        self.assertTrue(any(tx["id"] == tx2.id for tx in recents))

    def test_clear_pool(self):
        tx = TransactionMessage("peerX", "peerY", 25)
        add_transaction(tx)
        clear_pool()
        self.assertEqual(len(tx_pool), 0)
        self.assertEqual(len(tx_ids), 0)

    def test_transaction_message_hash_unique(self):
        tx1 = TransactionMessage("peerA", "peerB", 10)
        time.sleep(0.001)  # 确保时间戳不同
        tx2 = TransactionMessage("peerA", "peerB", 10)
        self.assertNotEqual(tx1.id, tx2.id)

    def test_to_dict_and_from_dict(self):
        tx = TransactionMessage("peerA", "peerB", 13)
        tx_dict = tx.to_dict()
        tx2 = TransactionMessage.from_dict(tx_dict)
        self.assertEqual(tx.id, tx2.id)
        self.assertEqual(tx.from_peer, tx2.from_peer)
        self.assertEqual(tx.to_peer, tx2.to_peer)
        self.assertEqual(tx.amount, tx2.amount)
        self.assertEqual(tx.timestamp, tx2.timestamp)

if __name__ == '__main__':
    unittest.main()