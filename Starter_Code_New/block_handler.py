import time
import hashlib
import json
import threading
import random
from transaction import get_recent_transactions, clear_pool
from peer_discovery import known_peers, peer_config
from outbox import enqueue_message, gossip_message
from utils import generate_message_id
from peer_manager import record_offense

received_blocks = []  # 本地区块链
header_store = []     # 轻节点区块头
orphan_blocks = {}    # 孤块池

def request_block_sync(self_id):
    # 构建GET_BLOCK_HEADERS消息
    msg = {
        "type": "GET_BLOCK_HEADERS",
        "sender": self_id,
        "message_id": generate_message_id(),
    }
    # 发送到所有已知节点
    for peer in known_peers:
        if peer != self_id:
            enqueue_message(peer, known_peers[peer][0], known_peers[peer][1], msg)

def block_generation(self_id, MALICIOUS_MODE, interval=20):
    from inv_message import create_inv
    def mine():
        while True:
            # 创建新区块
            block = create_dummy_block(self_id, MALICIOUS_MODE)
            if block is not None:
                # 生成INV消息并广播
                inv_msg = create_inv([block["block_id"]], self_id)
                gossip_message([peer for peer in known_peers if peer != self_id], inv_msg)
            time.sleep(interval)
    threading.Thread(target=mine, daemon=True).start()

def create_dummy_block(peer_id, MALICIOUS_MODE):
    # 获取交易
    txs = get_recent_transactions()
    if not txs:
        return None
    # 上一个区块ID
    prev_block_id = received_blocks[-1]["block_id"] if received_blocks else "GENESIS"
    block = {
        "type": "BLOCK",
        "peer_id": peer_id,
        "timestamp": time.time(),
        "previous_block_id": prev_block_id,
        "transactions": txs
    }
    # 计算区块ID
    if MALICIOUS_MODE:
        block["block_id"] = hashlib.sha256(str(time.time() + random.random()).encode()).hexdigest()
    else:
        block["block_id"] = compute_block_hash(block)
    # 清空交易池并存储区块
    clear_pool()
    receive_block(block)
    return block

def compute_block_hash(block):
    # 计算区块哈希（不含block_id）
    block_copy = dict(block)
    block_copy.pop("block_id", None)
    block_str = json.dumps(block_copy, sort_keys=True)
    return hashlib.sha256(block_str.encode()).hexdigest()

def handle_block(msg, self_id):
    # 校验区块ID
    block_id = msg.get("block_id")
    msg_without_id = msg.copy()
    msg_without_id.pop("block_id", None)
    expected_hash = compute_block_hash(msg_without_id)
    if block_id != expected_hash:
        record_offense(msg.get("peer_id"))
        print(f"[{msg.get('peer_id')}] recorded in blacklist of {self_id}.")
        return
    # 是否已存在
    if any(b["block_id"] == block_id for b in received_blocks):
        return
    # 上一个区块是否存在
    prev_id = msg.get("previous_block_id")
    if prev_id != "GENESIS" and not any(b["block_id"] == prev_id for b in received_blocks):
        orphan_blocks[block_id] = msg
        return
    # 添加区块
    receive_block(msg)
    # 检查能否接回孤块
    to_remove = []
    for orphan_id, orphan_block in orphan_blocks.items():
        if orphan_block["previous_block_id"] == block_id:
            receive_block(orphan_block)
            to_remove.append(orphan_id)
    for oid in to_remove:
        orphan_blocks.pop(oid, None)

def receive_block(block):
    # 存储区块或区块头
    if peer_config.get("type", "full") == "full":
        received_blocks.append(block)
    else:
        header = {
            "peer_id": block["peer_id"],
            "timestamp": block["timestamp"],
            "block_id": block["block_id"],
            "previous_block_id": block["previous_block_id"]
        }
        header_store.append(header)

def create_getblock(sender_id, requested_ids):
    # 构建GETBLOCK消息
    return {
        "type": "GETBLOCK",
        "sender": sender_id,
        "block_ids": requested_ids
    }

def get_block_by_id(block_id):
    # 根据ID查找区块
    for block in received_blocks:
        if block["block_id"] == block_id:
            return block
    return None