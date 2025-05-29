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

priority_order = {
    "BLOCK": 1,
    "TX": 2,
    "PING": 3,
    "PONG": 4,
    "HELLO": 5
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

    # TODO: Check if the peer sends message to the receiver too frequently using the function `is_rate_limited`. If yes, drop the message.
  
    # TODO: Check if the receiver exists in the `blacklist`. If yes, drop the message.
  
    # TODO: Classify the priority of the sending messages based on the message type using the function `classify_priority`.
  
    # TODO: Add the message to the queue (`queues`) if the length of the queue is within the limit `QUEUE_LIMIT`, or otherwise, drop the message.
    pass


def is_rate_limited(peer_id):
    # TODO:Check how many messages were sent from the peer to a target peer during the `TIME_WINDOW` that ends now.
  
    # TODO: If the sending frequency exceeds the sending rate limit `RATE_LIMIT`, return `TRUE`; otherwise, record the current sending time into `peer_send_timestamps`.
    pass

def classify_priority(message):
    # TODO: Classify the priority of a message based on the message type.
    pass
    

def send_from_queue(self_id):
    def worker():
        
        # TODO: Read the message in the queue. Each time, read one message with the highest priority of a target peer. After sending the message, read the message of the next target peer. This ensures the fairness of sending messages to different target peers.

        # TODO: Send the message using the function `relay_or_direct_send`, which will decide whether to send the message to target peer directly or through a relaying peer.

        # TODO: Retry a message if it is sent unsuccessfully and drop the message if the retry times exceed the limit `MAX_RETRIES`.

        pass
    threading.Thread(target=worker, daemon=True).start()

def relay_or_direct_send(self_id, dst_id, message):
    from peer_discovery import known_peers, peer_flags

    # TODO: Check if the target peer is NATed. 

    # TODO: If the target peer is NATed, use the function `get_relay_peer` to find the best relaying peer. 
    # Define the JSON format of a `RELAY` message, which should include `{message type, sender's ID, target peer's ID, `payload`}`. 
    # `payload` is the sending message. 
    # Send the `RELAY` message to the best relaying peer using the function `send_message`.
  
    # TODO: If the target peer is non-NATed, send the message to the target peer using the function `send_message`.

    pass

def get_relay_peer(self_id, dst_id):
    from peer_manager import  rtt_tracker
    from peer_discovery import known_peers, reachable_by

    # TODO: Find the set of relay candidates reachable from the target peer in `reachable_by` of `peer_discovery.py`.
    
    # TODO: Read the transmission latency between the sender and other peers in `rtt_tracker` in `peer_manager.py`.
  
    # TODO: Select and return the best relaying peer with the smallest transmission latency.
    pass

    return best_peer  # (peer_id, ip, port) or None

def send_message(ip, port, message):

    # TODO: Send the message to the target peer. 
    # Wrap the function `send_message` with the dynamic network condition in the function `apply_network_condition` of `link_simulator.py`.
    pass

send_message = apply_network_conditions(send_message)

def apply_network_conditions(send_func):
    def wrapper(ip, port, message):

        # TODO: Use the function `rate_limiter.allow` to check if the peer's sending rate is out of limit. 
        # If yes, drop the message and update the drop states (`drop_stats`).

        # TODO: Generate a random number. If it is smaller than `DROP_PROB`, drop the message to simulate the random message drop in the channel. 
        # Update the drop states (`drop_stats`).

        # TODO: Add a random latency before sending the message to simulate message transmission delay.

        # TODO: Send the message using the function `send_func`.
        pass
    return wrapper

def start_dynamic_capacity_adjustment():
    def adjust_loop():
        # TODO: Peridically change the peer's sending capacity in `rate_limiter` within the range [2, 10].
        pass
    threading.Thread(target=adjust_loop, daemon=True).start()


def gossip_message(self_id, message, fanout=3):

    from peer_discovery import known_peers, peer_config

    # TODO: Read the configuration `fanout` of the peer in `peer_config` of `peer_discovery.py`.

    # TODO: Randomly select the number of target peer from `known_peers`, which is equal to `fanout`. If the gossip message is a transaction, skip the lightweight peers in the `know_peers`.

    # TODO: Send the message to the selected target peer and put them in the outbox queue.
    pass

def get_outbox_status():
    # TODO: Return the message in the outbox queue.
    pass


def get_drop_stats():
    # TODO: Return the drop states (`drop_stats`).
    pass

