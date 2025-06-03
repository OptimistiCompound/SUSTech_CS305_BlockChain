import json
import threading
import time
import hashlib
import random
from collections import defaultdict
from peer_discovery import handle_hello_message, known_peers, peer_config
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
            return True
    return False

# ===  Redundancy Tracking ===

def get_redundancy_stats():
    # Return the times of receiving duplicated messages (`message_redundancy`).
    return message_redundancy

# === Main Message Dispatcher ===
def dispatch_message(msg, self_id, self_ip):
    
    msg_type = msg.get("type")
    message_id = msg.get("message_id")

    ''' Read the message. '''

    # Check if the message has been seen in `seen_message_ids` to prevent replay attacks. If yes, drop the message and add one to `message_redundancy`. If not, add the message ID to `seen_message_ids`.
    if message_id in seen_message_ids:
        message_redundancy += 1
        return
    else:
        seen_message_ids[message_id] = time.time()
    # Check if the sender sends message too frequently using the function `is_inbound_limited`. If yes, drop the message.
    if is_inbound_limited(msg["sender"]):
        return
    # Check if the sender exists in the `blacklist` of `peer_manager.py`. If yes, drop the message.
    if msg["sender"] in blacklist:
        return

    #format in outbox.relay_or_direct_send
    if msg_type == "RELAY":

        # TODO: Check if the peer is the target peer.
        # If yes, extract the payload and recall the function `dispatch_message` to process the payload.
        # If not, forward the message to target peer using the function `enqueue_message` in `outbox.py`.
        pass

    #format in peer_discovery.start_peer_discovery
    elif msg_type == "HELLO":
        # Call the function `handle_hello_message` in `peer_discovery.py` to process the message.
        handle_hello_message(msg, self_id)

    #format in block_handler.block_generation
    elif msg_type == "BLOCK":
        # TODO: Check the correctness of block ID. If incorrect, record the sender's offence using the function `record_offence` in `peer_manager.py`.
        block_id = msg["block_id"]

        # TODO: Call the function `handle_block` in `block_handler.py` to process the block.
        
        # TODO: Call the function `create_inv` to create an `INV` message for the block.
        
        # TODO: Broadcast the `INV` message to known peers using the function `gossip_message` in `outbox.py`.

        pass

    #format in transaction.start_transaction_generation
    elif msg_type == "TX":
        
        # TODO: Check the correctness of transaction ID. If incorrect, record the sender's offence using the function `record_offence` in `peer_manager.py`.
        
        # TODO: Add the transaction to `tx_pool` using the function `add_transaction` in `transaction.py`.
        
        # TODO: Broadcast the transaction to known peers using the function `gossip_message` in `outbox.py`.

        pass

    #format in peer_manager.start_ping_loop
    elif msg_type == "PING":
        
        # TODO: Update the last ping time using the function `update_peer_heartbeat` in `peer_manager.py`.
        
        # TODO: Create a `pong` message using the function `create_pong` in `peer_manager.py`.
        
        # TODO: Send the `pong` message to the sender using the function `enqueue_message` in `outbox.py`.

        pass

    #format in peer_manager.create_pong
    elif msg_type == "PONG":
        
        # TODO: Update the last ping time using the function `update_peer_heartbeat` in `peer_manager.py`.
        
        # TODO: Call the function `handle_pong` in `peer_manager.py` to handle the message.

        pass

    #format in inv_message.create_inv
    elif msg_type == "INV":
        
        # TODO: Read all blocks IDs in the local blockchain using the function `get_inventory` in `block_handler.py`.
        
        # TODO: Compare the local block IDs with those in the message.
        
        # TODO: If there are missing blocks, create a `GETBLOCK` message to request the missing blocks from the sender.
        
        # TODO: Send the `GETBLOCK` message to the sender using the function `enqueue_message` in `outbox.py`.

        pass

    #format in block_handler.create_getblock
    elif msg_type == "GETBLOCK":
        
        # TODO: Extract the block IDs from the message.
        
        # TODO: Get the blocks from the local blockchain according to the block IDs using the function `get_block_by_id` in `block_handler.py`.
        
        # TODO: If the blocks are not in the local blockchain, create a `GETBLOCK` message to request the missing blocks from known peers.
        
        # TODO: Send the `GETBLOCK` message to known peers using the function `enqueue_message` in `outbox.py`.
        
        # TODO: Retry getting the blocks from the local blockchain. If the retry times exceed 3, drop the message.
        
        # TODO: If the blocks exist in the local blockchain, send the blocks one by one to the requester using the function `enqueue_message` in `outbox.py`.

        pass

    #format in block_handler.request_block_sync
    elif msg_type == "GET_BLOCK_HEADERS":
        
        # TODO: Read all block header in the local blockchain and store them in `headers`.
        
        # TODO: Create a `BLOCK_HEADERS` message, which should include `{message type, sender's ID, headers}`.
        
        # TODO: Send the `BLOCK_HEADERS` message to the requester using the function `enqueue_message` in `outbox.py`.

        pass
    
    #format in this.dispatch_message
    elif msg_type == "BLOCK_HEADERS":
        
        # TODO: Check if the previous block of each block exists in the local blockchain or the received block headers.
        
        # TODO: If yes and the peer is lightweight, add the block headers to the local blockchain.
        
        # TODO: If yes and the peer is full, check if there are missing blocks in the local blockchain. If there are missing blocks, create a `GET_BLOCK` message and send it to the sender.
        
        # TODO: If not, drop the message since there are orphaned blocks in the received message and, thus, the message is invalid.

        pass


    else:
        print(f"[{self_id}] Unknown message type: {msg_type}", flush=True)