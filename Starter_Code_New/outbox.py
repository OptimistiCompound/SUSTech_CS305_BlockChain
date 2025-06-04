import socket
import threading
import time
import json
import random
from collections import defaultdict, deque
from threading import Lock

# === Per-peer Rate Limiting ===
RATE_LIMIT = 10  # max messages
TIME_WINDOW = 10  # per seconds
peer_send_timestamps = defaultdict(list) # the timestamps of sending messages to each peer

MAX_RETRIES = 3
RETRY_INTERVAL = 5  # seconds
QUEUE_LIMIT = 50

# Priority levels
PRIORITY_HIGH = {"PING", "PONG", "BLOCK", "INV", "GET_BLOCK_HEADERS", "GETBLOCK", "BLOCK_HEADERS"}
PRIORITY_MEDIUM = {"TX", "HELLO"}
PRIORITY_LOW = {"RELAY"}

DROP_PROB = 0.05
LATENCY_MS = (20, 100)
SEND_RATE_LIMIT = 5  # messages per second

drop_stats = {
    "BLOCK": 0,
    "TX": 0,
    "HELLO": 0,
    "PING": 0,
    "PONG": 0,
    "INV": 0,
    "RELAY": 0,
    "GET_BLOCK_HEADERS": 0,
    "GETBLOCK": 0,
    "BLOCK_HEADERS": 0
}

# Queues per peer and priority
queues = defaultdict(lambda: defaultdict(deque))
retries = defaultdict(int)
lock = threading.Lock()

# === Sending Rate Limiter ===
class RateLimiter:
    def __init__(self, rate=SEND_RATE_LIMIT):
        self.capacity = rate               # Max burst size
        self.tokens = rate                # Start full
        self.refill_rate = rate           # Tokens added per second
        self.last_check = time.time()
        self.lock = Lock()

    def allow(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_check
            self.tokens += elapsed * self.refill_rate
            self.tokens = min(self.tokens, self.capacity)
            self.last_check = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

rate_limiter = RateLimiter()

def enqueue_message(target_id, ip, port, message):
    from peer_manager import blacklist, rtt_tracker

    '''Why rtt_tracker is not used?'''

    # Check if the peer sends message to the receiver too frequently using the function `is_rate_limited`. If yes, drop the message.
    # Check if the receiver exists in the `blacklist`. If yes, drop the message.
    # Classify the priority of the sending messages based on the message type using the function `classify_priority`.
    # Add the message to the queue (`queues`) if the length of the queue is within the limit `QUEUE_LIMIT`, or otherwise, drop the message.
    if is_rate_limited(target_id):
        return
    if target_id in blacklist:
        return
    priority = classify_priority(message)

    if message["type"] == "HELLO":
        print(f"🟢 Hello from {target_id}")

    with lock:
        if len(queues[target_id][priority]) < QUEUE_LIMIT:
            queues[target_id][priority].append((ip, port, message))
        else:
            print(f"[{target_id}]🈲 Drop due to queue limit")
            drop_stats[message["type"]] += 1
            return

def is_rate_limited(peer_id):
    # Check how many messages were sent from the peer to a target peer during the `TIME_WINDOW` that ends now.
    # If the sending frequency exceeds the sending rate limit `RATE_LIMIT`, return `TRUE`; otherwise, record the current sending time into `peer_send_timestamps`.
    
    # cur_time = time.time()
    # msg_cnt = 0
    # for timestamp in peer_send_timestamps[peer_id]:
    #     if (cur_time <= timestamp + TIME_WINDOW):
    #         msg_cnt += 1
    #     if (msg_cnt >= RATE_LIMIT):
    #         return True
    # peer_send_timestamps[peer_id].append(cur_time)
    # return False
    cur_time = time.time()
    peer_send_timestamps[peer_id] = [
        t for t in peer_send_timestamps[peer_id] if t >= cur_time - TIME_WINDOW
    ]
    if len(peer_send_timestamps[peer_id]) >= RATE_LIMIT:
        return True
    peer_send_timestamps[peer_id].append(cur_time)
    return False

def classify_priority(message):
    # Classify the priority of a message based on the message type.
    msg_type = message["type"]
    if msg_type in PRIORITY_HIGH:
        return "HIGH"
    elif msg_type in PRIORITY_MEDIUM:
        return "MEDIUM"
    else:
        return "LOW"
    
def send_from_queue(self_id):
    def worker():
        while True:  # 持续轮询
            # Read the message in the queue. 
            # Each time, read one message with the highest priority of a target peer. 
            # After sending the message, read the message of the next target peer. 
            # This ensures the fairness of sending messages to different target peers.
            for target_id in list(queues.keys()):
                with lock:
                    if (queues[target_id]["HIGH"] or queues[target_id]["MEDIUM"] or queues[target_id]["LOW"]):
                        ip, port, message = None, None, None
                        if queues[target_id]["HIGH"]:
                            ip, port, message = queues[target_id]["HIGH"].popleft()
                        elif queues[target_id]["MEDIUM"]:
                            ip, port, message = queues[target_id]["MEDIUM"].popleft()
                        elif queues[target_id]["LOW"]:
                            ip, port, message = queues[target_id]["LOW"].popleft()
                        else:
                            continue
                        retries[target_id] = 0
                    else:
                        continue
                
                # Send the message using the function `relay_or_direct_send`, 
                # which will decide whether to send the message to target peer directly or through a relaying peer.
                success = relay_or_direct_send(self_id, target_id, message)

                # Retry a message if it is sent unsuccessfully and drop the message if the retry times exceed the limit `MAX_RETRIES`.
                if not success:
                    if retries[target_id] < MAX_RETRIES:
                        retries[target_id] += 1
                        time.sleep(RETRY_INTERVAL)
                        enqueue_message(target_id, ip, port, message)
                    else:
                        drop_stats[message["type"]] += 1
                        retries[target_id] = 0
                else:
                    retries[target_id] = 0
            time.sleep(0.01)  # 防止空转占用CPU

    threading.Thread(target=worker, daemon=True).start()

def relay_or_direct_send(self_id, dst_id, message):
    from peer_discovery import known_peers, peer_flags
    from utils import generate_message_id

    if message["type"] == "HELLO":
        print(f"🟢 Sending HELLO to {dst_id}")

    # Check if the target peer is NATed. 
    nat = peer_flags.get(dst_id, {}).get("nat", False)

    # If the target peer is NATed, use the function `get_relay_peer` to find the best relaying peer. 
    # Define the JSON format of a `RELAY` message, which should include `{message type, sender's ID, target peer's ID, `payload`}`. 
    # `payload` is the sending message. 
    # Send the `RELAY` message to the best relaying peer using the function `send_message`.
    if nat:
        relay_peer = get_relay_peer(self_id, dst_id)
        if relay_peer:
            # print(f"🟡 Sending RELAY to {relay_peer[0]}")
            relay_msg = {
                "type": "RELAY",
                "sender": self_id,
                "target": dst_id,
                "payload": message,
                "message_id": generate_message_id()
            }
            return send_message(relay_peer[1], relay_peer[2], relay_msg)
        else:
            return False
    # If the target peer is non-NATed, send the message to the target peer using the function `send_message`.
    else:
        return send_message(known_peers[dst_id][0], known_peers[dst_id][1], message)

def get_relay_peer(self_id, dst_id):
    from peer_manager import  rtt_tracker
    from peer_discovery import known_peers, reachable_by

    # Find the set of relay candidates reachable from the target peer in `reachable_by` of `peer_discovery.py`.
    # Read the transmission latency between the sender and other peers in `rtt_tracker` in `peer_manager.py`.
    # Select and return the best relaying peer with the smallest transmission latency.
    relay_candidates = reachable_by.get(dst_id, set())
    best_peer = None
    for relay_id in relay_candidates:
        if relay_id != self_id:
            if best_peer is None or rtt_tracker[relay_id] < rtt_tracker[best_peer[0]]:
                best_peer = (relay_id, known_peers[relay_id][0], known_peers[relay_id][1])
    return best_peer  # (peer_id, ip, port) or None

# wrapper for send_message，模拟真实网络状况
def apply_network_conditions(send_func):
    def wrapper(ip, port, message):

        # Use the function `rate_limiter.allow` to check if the peer's sending rate is out of limit. 
        # If yes, drop the message and update the drop states (`drop_stats`).
        if rate_limiter.allow() == False:
            drop_stats[message["type"]] += 1
            return False

        # Generate a random number. If it is smaller than `DROP_PROB`, drop the message to simulate the random message drop in the channel. 
        # Update the drop states (`drop_stats`).
        if random.random() < DROP_PROB:
            drop_stats[message["type"]] += 1
            return False

        # Add a random latency before sending the message to simulate message transmission delay.
        # Send the message using the function `send_func`.
        time.sleep(random.uniform(*LATENCY_MS) / 1000)
        return send_func(ip, port, message)

    return wrapper

def send_message(ip, port, message):

    # Send the message to the target peer. 
    # Wrap the function `send_message` with the dynamic network condition in the function `apply_network_condition` of `link_simulator.py`.
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, port))
        sock.sendall(json.dumps(message).encode())
        print(f"Sent message to {ip}:{port}: {message}")
        sock.close()
        return True
    except Exception as e:
        print(f"🔴 Failed to send message to {ip}:{port}: {e}")
        return False
send_message = apply_network_conditions(send_message)


def start_dynamic_capacity_adjustment():
    def adjust_loop():
        # Peridically change the peer's sending capacity in `rate_limiter` within the range [2, 10].
        UPDATE_INTERVAL = 10 # 源代码没给
        while True:
            rate_limiter.capacity = random.randint(2, 10)
            time.sleep(UPDATE_INTERVAL)

    threading.Thread(target=adjust_loop, daemon=True).start()


def gossip_message(self_id, message, fanout=3):

    from peer_discovery import known_peers, peer_config, peer_flags

    # Read the configuration `fanout` of the peer in `peer_config` of `peer_discovery.py`.
    # Randomly select the number of target peer from `known_peers`, which is equal to `fanout`. If the gossip message is a transaction, skip the lightweight peers in the `know_peers`.
    # Send the message to the selected target peer and put them in the outbox queue.
    selected_peers = set()
    for peer in peer_config:
        if peer == self_id:
            continue
        light = peer_flags[peer].get("light", False)
        if light and message["type"] == "TX":
            continue
        selected_peers.add(peer)
        if len(selected_peers) == fanout:
            break
    for peer in selected_peers:
        enqueue_message(peer, known_peers[peer][0], known_peers[peer][1], message)

def get_outbox_status():
    # Return the message in the outbox queue.
    return queues


def get_drop_stats():
    # Return the drop states (`drop_stats`).
    return drop_stats