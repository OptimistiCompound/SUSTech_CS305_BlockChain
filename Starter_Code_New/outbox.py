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
PRIORITY_HIGH = {"PING", "PONG", "BLOCK", "INV", "GETDATA"}
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
    "OTHER": 0
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
    # 1. Rate limit
    if is_rate_limited(target_id):
        drop_stats[message.get("type", "OTHER")] += 1
        return
    # 2. Blacklist
    if target_id in blacklist:
        drop_stats[message.get("type", "OTHER")] += 1
        return
    # 3. Classify priority
    priority = classify_priority(message)
    # 4. Enqueue or drop
    with lock:
        q = queues[target_id][priority]
        if len(q) >= QUEUE_LIMIT:
            drop_stats[message.get("type", "OTHER")] += 1
            return
        q.append((ip, port, message))


def is_rate_limited(peer_id):
    now = time.time()
    timestamps = peer_send_timestamps[peer_id]
    timestamps = [ts for ts in timestamps if now - ts < TIME_WINDOW]
    peer_send_timestamps[peer_id] = timestamps
    if len(timestamps) >= RATE_LIMIT:
        return True
    peer_send_timestamps[peer_id].append(now)
    return False

def classify_priority(message):
    t = message.get("type", "OTHER")
    if t in PRIORITY_HIGH:
        return "HIGH"
    elif t in PRIORITY_MEDIUM:
        return "MEDIUM"
    elif t in PRIORITY_LOW:
        return "LOW"
    else:
        return "LOW"
    

def send_from_queue(self_id):
    def worker():
        while True:
            with lock:
                peer_ids = list(queues.keys())
            for peer_id in peer_ids:
                for priority in ["HIGH", "MEDIUM", "LOW"]:
                    with lock:
                        q = queues[peer_id][priority]
                        if not q:
                            continue
                        ip, port, message = q.popleft()
                    # Send message
                    ok = relay_or_direct_send(self_id, peer_id, message)
                    if not ok:
                        key = (peer_id, id(message))
                        retries[key] += 1
                        if retries[key] < MAX_RETRIES:
                            with lock:
                                q.append((ip, port, message))
                            time.sleep(RETRY_INTERVAL)
                        else:
                            drop_stats[message.get("type", "OTHER")] += 1
                            retries.pop(key, None)
            time.sleep(0.01)
    threading.Thread(target=worker, daemon=True).start()

def relay_or_direct_send(self_id, dst_id, message):
    from peer_discovery import known_peers, peer_flags
    # NAT check
    if peer_flags.get(dst_id) == "NAT":
        relay_peer = get_relay_peer(self_id, dst_id)
        if relay_peer:
            relay_id, relay_ip, relay_port = relay_peer
            relay_msg = {
                "type": "RELAY",
                "sender": self_id,
                "target_peer": dst_id,
                "payload": message
            }
            return send_message(relay_ip, relay_port, relay_msg)
        else:
            return False
    else:
        ip, port = known_peers[dst_id]
        return send_message(ip, port, message)

def get_relay_peer(self_id, dst_id):
    from peer_manager import  rtt_tracker
    from peer_discovery import known_peers, reachable_by
    candidates = reachable_by.get(dst_id, set())
    best_peer = None
    best_rtt = float("inf")
    for peer in candidates:
        if peer == self_id:
            continue
        rtt = rtt_tracker.get(peer, float("inf"))
        if rtt < best_rtt:
            best_rtt = rtt
            best_peer = peer
    if best_peer and best_peer in known_peers:
        ip, port = known_peers[best_peer]
        return (best_peer, ip, port)
    return None

def apply_network_conditions(send_func):
    def wrapper(ip, port, message):
        if not rate_limiter.allow():
            drop_stats[message.get("type", "OTHER")] += 1
            return False
        if random.random() < DROP_PROB:
            drop_stats[message.get("type", "OTHER")] += 1
            return False
        latency = random.randint(*LATENCY_MS) / 1000
        time.sleep(latency)
        return send_func(ip, port, message)
    return wrapper

def send_message(ip, port, message):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(json.dumps(message).encode(), (ip, port))
        s.close()
        return True
    except Exception:
        return False

send_message = apply_network_conditions(send_message)


def start_dynamic_capacity_adjustment():
    def adjust_loop():
        while True:
            new_cap = random.randint(2, 10)
            rate_limiter.capacity = new_cap
            rate_limiter.refill_rate = new_cap
            time.sleep(3)
    threading.Thread(target=adjust_loop, daemon=True).start()


def gossip_message(self_id, message, fanout=3):

    from peer_discovery import known_peers, peer_config

    msg_type = message.get("type", "")
    if "fanout" in peer_config:
        fanout = peer_config["fanout"]
    peer_ids = list(known_peers.keys())
    if msg_type == "TX":
        peer_ids = [pid for pid in peer_ids if peer_config.get(pid, {}).get("type") != "light"]
    peer_ids = [pid for pid in peer_ids if pid != self_id]
    if not peer_ids:
        return
    targets = random.sample(peer_ids, min(fanout, len(peer_ids)))
    for pid in targets:
        ip, port = known_peers[pid]
        enqueue_message(pid, ip, port, message)

def get_outbox_status():
    with lock:
        return {peer_id: {pri: list(q) for pri, q in queues[peer_id].items()} for peer_id in queues}



def get_drop_stats():
    return dict(drop_stats)