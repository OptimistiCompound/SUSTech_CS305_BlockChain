import json, time, threading
from utils import generate_message_id


known_peers = {}        # { peer_id: (ip, port) }
peer_flags = {}         # { peer_id: { 'nat': True/False, 'light': True/False } }
reachable_by = {}       # { peer_id: { set of peer_ids who can reach this peer }}
peer_config={}

def start_peer_discovery(self_id, self_info):
    from outbox import enqueue_message
    def loop():
        # TODO: Define the JSON format of a `hello` message, which should include: `{message type, sender’s ID, IP address, port, flags, and message ID}`. 
        # A `sender’s ID` can be `peer_port`. 
        # The `flags` should indicate whether the peer is `NATed or non-NATed`, and `full or lightweight`. 
        # The `message ID` can be a random number.

        # TODO: Send a `hello` message to all known peers and put the messages into the outbox queue.
        pass
    threading.Thread(target=loop, daemon=True).start()

def handle_hello_message(msg, self_id):
    new_peers = []
    
    # TODO: Read information in the received `hello` message.
     
    # TODO: If the sender is unknown, add it to the list of known peers (`known_peer`) and record their flags (`peer_flags`).
     
    # TODO: Update the set of reachable peers (`reachable_by`).

    pass

    return new_peers 


