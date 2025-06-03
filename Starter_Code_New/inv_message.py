import time
import json
from utils import generate_message_id
from outbox import gossip_message
from block_handler import received_blocks
from peer_discovery import known_peers

def create_inv(block_ids, sender_id):
    # 构建INV消息
    return {
        "type": "INV",
        "sender": sender_id,
        "block_ids": block_ids,
        "message_id": generate_message_id()
    }

def get_inventory():
    # 返回本地区块链所有区块ID
    return [block["block_id"] for block in received_blocks]

def broadcast_inventory(self_id):
    # 构建INV消息并广播
    inv_msg = create_inv(get_inventory(), self_id)
    # known_peers是dict，取所有peer_id，排除自己
    peer_ids = [peer_id for peer_id in known_peers if peer_id != self_id]
    gossip_message(inv_msg, peer_ids)