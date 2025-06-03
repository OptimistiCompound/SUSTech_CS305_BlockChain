import threading
import time
import json
from collections import defaultdict


peer_status = {} # {peer_id: 'ALIVE', 'UNREACHABLE' or 'UNKNOWN'}
last_ping_time = {} # {peer_id: timestamp}
rtt_tracker = {} # {peer_id: transmission latency}

# === Check if peers are alive ===

def start_ping_loop(self_id, peer_table, interval=5):
    from outbox import enqueue_message
    def loop():
       while True:
            cur_time = time.time()
            for peer_id, (ip, port) in peer_table.items():
                if peer_id == self_id:
                    continue
                msg = {
                    "type": "PING",
                    "sender": self_id,
                    "timestamp": cur_time
                }
                enqueue_message(peer_id, ip, port, msg)
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True).start()

def create_pong(sender, recv_ts):
    return {
        "type": "PONG",
        "sender": sender,
        "timestamp": recv_ts
    }

def handle_pong(msg):
    sender = msg.get("sender")
    sent_ts = msg.get("timestamp")
    now = time.time()
    if sender is not None and sent_ts is not None:
        rtt = now - sent_ts
        rtt_tracker[sender] = rtt
        update_peer_heartbeat(sender)

def start_peer_monitor(timeout  = 10, check_interval = 2):
    import threading
    def loop():
        while True:
            now = time.time()
            for peer_id in list(last_ping_time.keys()):
                last_time = last_ping_time.get(peer_id, 0)
                if now - last_time > timeout:
                    peer_status[peer_id] = "UNREACHABLE"
                else:
                    peer_status[peer_id] = "ALIVE"
            time.sleep(check_interval)
    threading.Thread(target=loop, daemon=True).start()

def update_peer_heartbeat(peer_id):
    last_ping_time[peer_id] = time.time()


# === Blacklist Logic ===

blacklist = set() # The set of banned peers

peer_offense_counts = defaultdict(int) # The offence times of peers

def record_offense(peer_id):
    peer_offense_counts[peer_id] += 1
    # Add a peer to `blacklist` if its offence times exceed 3.
    if peer_offense_counts[peer_id] > 3:
        blacklist.add(peer_id)