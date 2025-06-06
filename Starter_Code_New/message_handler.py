import json
import threading
import time
import hashlib
import random
from collections import defaultdict
from peer_discovery import handle_hello_message, known_peers, peer_config, peer_flags
from block_handler import handle_block, get_block_by_id, create_getblock, received_blocks, header_store
from inv_message import  create_inv, get_inventory
from block_handler import create_getblock
from peer_manager import  update_peer_heartbeat, record_offense, create_pong, handle_pong, blacklist
from transaction import add_transaction
from outbox import enqueue_message, gossip_message


# === Global State ===
SEEN_EXPIRY_SECONDS = 600  # 10 minutes
seen_message_ids = {}
seen_txs = set()
redundant_blocks = 0
redundant_txs = 0
message_redundancy = 0
peer_inbound_timestamps = defaultdict(list)


# === Inbound Rate Limiting ===
INBOUND_RATE_LIMIT = 10
INBOUND_TIME_WINDOW = 10  # seconds

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
            print(f"[⚠️] {peer_id} is inbound limited")
            return True
    return False

# ===  Redundancy Tracking ===

def get_redundancy_stats():
    # Return the times of receiving duplicated messages (`message_redundancy`).
    return message_redundancy

# === Main Message Dispatcher ===
def dispatch_message(msg, self_id, self_ip):
    global message_redundancy
    msg_type = msg.get("type")
    message_id = msg.get("message_id", msg.get("block_id", msg.get("tx_id", "UNKNOWN")))

    ''' Read the message. '''

    # Check if the message has been seen in `seen_message_ids` to prevent replay attacks. If yes, drop the message and add one to `message_redundancy`. If not, add the message ID to `seen_message_ids`.
    if message_id in seen_message_ids:
        message_redundancy += 1
        print(f"[{self_id}] Message {message_id} already seen, dropping message")
        return
    else:
        if message_id != "UNKNOWN": 
            seen_message_ids[message_id] = time.time()
    # Check if the sender sends message too frequently using the function `is_inbound_limited`. If yes, drop the message.
    if is_inbound_limited(msg.get("sender", msg.get("from"))):
        print(f"[⚠️] {msg.get('sender', msg.get('from'))} is inbound limited, dropping message")
        return
    # Check if the sender exists in the `blacklist` of `peer_manager.py`. If yes, drop the message.
    if msg.get("sender", msg.get("from")) in blacklist:
        print(f"[⚠️] {msg['sender']} is in the blacklist, dropping message")
        return

    #format in outbox.relay_or_direct_send
    if msg_type == "RELAY":

        # Check if the peer is the target peer.
        # If yes, extract the payload and recall the function `dispatch_message` to process the payload.
        # If not, forward the message to target peer using the function `enqueue_message` in `outbox.py`.
        target_id = msg["target"]
        if target_id == self_id:
            payload = msg["payload"]
            dispatch_message(payload, self_id, self_ip)
        else:
            target_ip, target_port = known_peers[target_id]
            enqueue_message(target_id, target_ip, target_port, msg)

    #format in peer_discovery.start_peer_discovery
    elif msg_type == "HELLO":
        # Call the function `handle_hello_message` in `peer_discovery.py` to process the message.
        handle_hello_message(msg, self_id)

    #format in block_handler.block_generation
    elif msg_type == "BLOCK":

        # Check the correctness of block ID. If incorrect, record the sender's offence using the function `record_offence` in `peer_manager.py`.
        # Call the function `handle_block` in `block_handler.py` to process the block.
        success = handle_block(msg, self_id)

        if not success:
            print(f"[{self_id}] block message drop.")
            return

        # Call the function `create_inv` to create an `INV` message for the block.
        inv_msg = create_inv([msg["block_id"]], self_id)

        # Broadcast the `INV` message to known peers using the function `gossip_message` in `outbox.py`.
        gossip_message(self_id, inv_msg)

    #format in transaction.start_transaction_generation
    elif msg_type == "TX":
        from transaction import TransactionMessage
        # Check the correctness of transaction ID. If incorrect, record the sender's offence using the function `record_offence` in `peer_manager.py`.
        rcv_tx_id = msg["tx_id"]
        tx = TransactionMessage(msg["from"], msg["to"], msg["amount"], msg["timestamp"])
        calc_tx_id = tx.compute_hash()
        if rcv_tx_id!= calc_tx_id:
            record_offense(msg["from"])
            print(f"[{self_id}] Invalid transaction ID {rcv_tx_id}, expected {calc_tx_id}. Offense recorded.")
            return

        # Add the transaction to `tx_pool` using the function `add_transaction` in `transaction.py`.
        add_transaction(tx)

        # Broadcast the transaction to known peers using the function `gossip_message` in `outbox.py`.
        gossip_message(self_id, msg)

    #format in peer_manager.start_ping_loop
    elif msg_type == "PING":
        
        # Update the last ping time using the function `update_peer_heartbeat` in `peer_manager.py`.
        # Create a `pong` message using the function `create_pong` in `peer_manager.py`.
        # Send the `pong` message to the sender using the function `enqueue_message` in `outbox.py`.
        
        # if msg["sender"] == self_id:
        #     return
        update_peer_heartbeat(msg["sender"])
        pong_msg = create_pong(self_id, msg["timestamp"])
        target_ip, target_port = known_peers[msg["sender"]]
        enqueue_message(msg["sender"], target_ip, target_port, pong_msg)

    #format in peer_manager.create_pong
    elif msg_type == "PONG":
        
        # Update the last ping time using the function `update_peer_heartbeat` in `peer_manager.py`.
        # Call the function `handle_pong` in `peer_manager.py` to handle the message.
        
        #print(f"🫵 {self_id} received pong from {msg['sender']}")
        
        update_peer_heartbeat(msg["sender"])
        update_peer_heartbeat(self_id)
        handle_pong(msg)

    #format in inv_message.create_inv
    elif msg_type == "INV":
        
        # Read all blocks IDs in the local blockchain using the function `get_inventory` in `block_handler.py`.
        # Compare the local block IDs with those in the message.
        # If there are missing blocks, create a `GETBLOCK` message to request the missing blocks from the sender.
        # Send the `GETBLOCK` message to the sender using the function `enqueue_message` in `outbox.py`.
        self_light = peer_flags[self_id]["light"]
        local_block_ids = get_inventory() # list of block_id
        if self_light:
            local_block_ids = [header["block_id"] for header in header_store]  # 轻节点只需要区块头
        rcv_block_ids = msg.get("block_ids", [])
        missing_block_ids = [block_id for block_id in rcv_block_ids if block_id not in local_block_ids]
        if missing_block_ids:
            target_ip, target_port = known_peers[msg["sender"]]
            if self_light:
                get_header_msg = {
                    "type": "GET_BLOCK_HEADERS",
                    "sender": self_id,
                    "message_id": generate_message_id(),
                }
                enqueue_message(msg["sender"], target_ip, target_port, get_header_msg)
            else:
                getblock_msg = create_getblock(self_id, missing_block_ids)
                enqueue_message(msg["sender"], target_ip, target_port, getblock_msg)

    #format in block_handler.create_getblock
    elif msg_type == "GETBLOCK":
        print(f"[{self_id}] Received GETBLOCK from {msg['sender']}, requesting blocks: {msg.get('block_ids', [])}")

        rcv_block_ids = msg.get("block_ids", [])
        ret_blocks = []
        missing_block_ids = []

        # 1. 查找本地已有的区块
        for block_id in rcv_block_ids:
            block = get_block_by_id(block_id)
            if block:
                ret_blocks.append(block)
                print(f"{self_id} Found block: {block_id}")
            else:
                missing_block_ids.append(block_id)
                print(f"[{self_id}] Missing block: {block_id}")

        # 2. 发送本地已有区块
        for block in ret_blocks:
            try:
                # 检查序列化
                json.dumps(block)
            except Exception as e:
                print(f"[{self_id}] Block not serializable: {e}, block={block}")
                continue
            print(f"Sending BLOCK: {block['block_id']}")

            try:
                sender = msg["sender"]
            except Exception as e:
                print(f"🆘 Exception in Key")
            try:
                print(f"enqueue_message参数: sender={msg.get('sender')}, peer_config={peer_config.get(msg.get('sender'))}")
                enqueue_message(
                    sender,
                    peer_config.get(sender)["ip"],
                    peer_config.get(sender)["port"],
                    block
                )
            except Exception as e:
                print(f"🆘 Error calling enqueue_message: {e}, msg={msg}, peer_config_keys={list(peer_config.keys())}")
            

        # 3. 如果有缺失区块，向其他 peer 请求
        if missing_block_ids:
            for peer_id in known_peers:
                if peer_id == self_id:
                    continue
                get_block_msg = create_getblock(self_id, missing_block_ids)
                enqueue_message(peer_id, peer_config[peer_id]["ip"], peer_config[peer_id]["port"], get_block_msg)

            # 4. 最多重试3次，每次等待10秒
            retry_cnt = 0
            while missing_block_ids and retry_cnt < 3:
                retry_cnt += 1
                print(f"[{self_id}] get block retry {retry_cnt} times, missing: {missing_block_ids}")
                time.sleep(10)
                found_block_ids = []
                for block_id in missing_block_ids:
                    block = get_block_by_id(block_id)
                    if block:
                        try:
                            json.dumps(block)
                        except Exception as e:
                            print(f"[{self_id}] Block not serializable: {e}, block={block}")
                            continue
                        print(f"Sending BLOCK: {block['block_id']}")
                        enqueue_message(
                            msg["sender"],
                            peer_config[msg["sender"]]["ip"],
                            peer_config[msg["sender"]]["port"],
                            block
                        )
                        found_block_ids.append(block_id)
                # 移除已找到的区块
                for block_id in found_block_ids:
                    missing_block_ids.remove(block_id)
                # 继续向其他 peer 请求剩余的
                if missing_block_ids:
                    for peer_id in known_peers:
                        if peer_id == self_id:
                            continue
                        get_block_msg = create_getblock(self_id, missing_block_ids)
                        enqueue_message(peer_id, peer_config[peer_id]["ip"], peer_config[peer_id]["port"], get_block_msg)


    #format in block_handler.request_block_sync
    elif msg_type == "GET_BLOCK_HEADERS":
        from utils import generate_message_id
        
        # Read all block header in the local blockchain and store them in `headers`.
        headers = []
        for block in received_blocks:
            header = {
                "sender": block["sender"],
                "timestamp": block["timestamp"],
                "block_id": block["block_id"],
                "previous_block_id": block["previous_block_id"]
            }
            headers.append(header)

        # Create a `BLOCK_HEADERS` message, which should include `{message type, sender's ID, headers}`.
        block_headers_msg = {
            "type": "BLOCK_HEADERS",
            "sender": self_id,
            "headers": headers,
            "message_id": generate_message_id()
        }

        # Send the `BLOCK_HEADERS` message to the requester using the function `enqueue_message` in `outbox.py`.
        enqueue_message(msg["sender"], peer_config[msg["sender"]]["ip"], peer_config[msg["sender"]]["port"], block_headers_msg)
    
    #format in this.dispatch_message
    elif msg_type == "BLOCK_HEADERS":
        
        # Check if the previous block of each block exists in the local blockchain or the received block headers.
        prev_exist = True
        headers = msg.get("headers", [])
        for header in headers:
            if header["previous_block_id"] not in received_blocks:
                prev_exist = False

        # If yes and the peer is lightweight, add the block headers to the local blockchain.
        # If yes and the peer is full, check if there are missing blocks in the local blockchain. 
        # If there are missing blocks, create a `GET_BLOCK` message and send it to the sender.
        if prev_exist:
            light = peer_flags[msg["sender"]]["light"]
            if light:
                for header in headers:
                    header_store.append(header)
            else:
                missing_block_ids = []
                for header in headers:
                    if header["block_id"] not in received_blocks:
                        missing_block_ids.append(header["block_id"])
                
                for block_id in missing_block_ids:
                    get_block_msg = create_getblock(self_id, [block_id])
                    enqueue_message(msg["sender"], peer_config[msg["sender"]]["ip"], peer_config[msg["sender"]]["port"], get_block_msg)

        # If not, drop the message since there are orphaned blocks in the received message and, thus, the message is invalid.
        else:
            print(f"[{self_id}] Orphaned blocks in the received message, message dropped.")
            return


    else:
        print(f"[{self_id}] Unknown message type: {msg_type}", flush=True)