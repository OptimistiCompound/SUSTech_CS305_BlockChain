import threading
import time
import json
from collections import defaultdict


peer_status = {} # {peer_id: 'ALIVE', 'UNREACHABLE' or 'UNKNOWN'}
last_ping_time = {} # {peer_id: timestamp}
rtt_tracker = {} # {peer_id: transmission latency}

# === Check if peers are alive ===

def start_ping_loop(self_id, peer_table):
    from outbox import enqueue_message
    def loop():
       # TODO: Define the JSON format of a `ping` message, which should include `{message typy, sender's ID, timestamp}`.

       # TODO: Send a `ping` message to each known peer periodically.
       pass
    threading.Thread(target=loop, daemon=True).start()

def create_pong(sender, recv_ts):
    # TODO: Create the JSON format of a `pong` message, which should include `{message type, sender's ID, timestamp in the received ping message}`.
    pass

def handle_pong(msg):
    # TODO: Read the information in the received `pong` message.

    # TODO: Update the transmission latenty between the peer and the sender (`rtt_tracker`).
    pass


def start_peer_monitor():
    import threading
    def loop():
        # TODO: Check the latest time to receive `ping` or `pong` message from each peer in `last_ping_time`.

        # TODO: If the latest time is earlier than the limit, mark the peer's status in `peer_status` as `UNREACHABLE` or otherwise `ALIVE`.

        pass
    threading.Thread(target=loop, daemon=True).start()

def update_peer_heartbeat(peer_id):
    # TODO: Update the `last_ping_time` of a peer when receiving its `ping` or `pong` message.
    pass


# === Blacklist Logic ===

blacklist = set() # The set of banned peers

peer_offense_counts = {} # The offence times of peers

def record_offense(peer_id):
    # TODO: Record the offence times of a peer when malicious behaviors are detected.

    # TODO: Add a peer to `blacklist` if its offence times exceed 3. 

    pass

