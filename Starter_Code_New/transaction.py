import time
import json
import hashlib
import random
import threading
from peer_discovery import known_peers
from outbox import gossip_message

class TransactionMessage:
    def __init__(self, sender, receiver, amount, timestamp=None):
        self.type = "TX"
        self.from_peer = sender
        self.to_peer = receiver
        self.amount = amount
        self.timestamp = timestamp if timestamp else time.time()
        self.id = self.compute_hash()

    def compute_hash(self):
        tx_data = {
            "type": self.type,
            "from": self.from_peer,
            "to": self.to_peer,
            "amount": self.amount,
            "timestamp": self.timestamp
        }
        return hashlib.sha256(json.dumps(tx_data, sort_keys=True).encode()).hexdigest()

    def to_dict(self):
        return {
            "type": self.type,
            "tx_id": self.id,
            "from": self.from_peer,
            "to": self.to_peer,
            "amount": self.amount,
            "timestamp": self.timestamp
        }

    @staticmethod
    def from_dict(data):
        return TransactionMessage(
            sender=data["from"],
            receiver=data["to"],
            amount=data["amount"],
            timestamp=data["timestamp"]
        )

# 本地交易池及其ID集合
tx_pool = []
tx_ids = set()

def transaction_generation(self_id, interval=60):
    def loop():
        while True:
            # 随机选择一个已知节点（排除自己）
            candidates = [peer for peer in known_peers if peer != self_id]
            if not candidates:
                time.sleep(interval)
                continue
            to_peer = random.choice(candidates)
            amount = random.randint(1, 100)  # 随机金额
            tx = TransactionMessage(self_id, to_peer, amount)
            add_transaction(tx)  # 加入本地交易池
            # 广播交易到所有已知节点
            gossip_message([peer for peer in known_peers if peer != self_id], tx.to_dict())
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True).start()

def add_transaction(tx):
    # 检查是否已存在
    if tx.id not in tx_ids:
        tx_pool.append(tx)
        tx_ids.add(tx.id)

def get_recent_transactions():
    # 返回所有交易（字典形式便于序列化和展示）
    return [tx.to_dict() for tx in tx_pool]

def clear_pool():
    # 清空交易池和ID集合
    tx_pool.clear()
    tx_ids.clear()