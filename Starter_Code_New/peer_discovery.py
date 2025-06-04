import json, time, threading
from utils import generate_message_id


known_peers = {}        # { peer_id: (ip, port) }
peer_flags = {}         # { peer_id: { 'nat': True/False, 'light': True/False } }
reachable_by = {}       # { peer_id: { set of peer_ids who can reach this peer }}
peer_config={}

def start_peer_discovery(self_id, self_info):
    from outbox import enqueue_message
    def loop():
        # Define the JSON format of a `hello` message, which should include: `{message type, sender’s ID, IP address, port, flags, and message ID}`. 
        # A `sender’s ID` can be `peer_port`. 
        # The `flags` should indicate whether the peer is `NATed or non-NATed`, and `full or lightweight`. 
        # The `message ID` can be a random number.
        self_ip = self_info["ip"]
        self_port = self_info["port"]
        nat_status = self_info.get("nat", False)
        light_status = self_info.get("light", False)
        localnetworkid = self_info.get("localnetworkid", -1)
        hello_msg = {
            "message_type": "HELLO",
            "sender_id": self_id,
            "ip": self_ip,
            "port": self_port,
            "flags": {
                "nat": nat_status,
                "light": light_status
            },
            "localnetworkid": localnetworkid,
            "message_id": generate_message_id()
        }

        # Send a `hello` message to all reachable peers and put the messages into the outbox queue.
        # Tips: A NATed peer can only say hello to peers in the same local network. 
        #       If a peer and a NATed peer are not in the same local network, they cannot say hello to each other.
        # 不完整的实现，尚不清楚localnetworkid的作用，以及如何判断rechable_by
    
        for peer_id in peer_config:
            reachable_by[peer_id] = set()

        for target_id, target_info in peer_config.items():
            for candidate_id, candidate_info in peer_config.items():
                if candidate_id == target_id:
                    continue
                target_nat = target_info.get("nat", False)
                candidate_nat = candidate_info.get("nat", False)
                target_localnet = target_info.get("localnetworkid", -1)
                candidate_localnet = candidate_info.get("localnetworkid", -1)
                # 非NAT peer
                if not target_nat:
                    if not candidate_nat:
                        reachable_by[target_id].add(candidate_id)
                    else:
                        if target_localnet == candidate_localnet:
                            reachable_by[target_id].add(candidate_id)
                # NAT peer只能被同局域网peer到达
                else:
                    if target_localnet == candidate_localnet:
                        reachable_by[target_id].add(candidate_id)

        # 添加到消息队列
        for target_id in reachable_by[self_id]:
            if target_id == self_id:
                continue
            print(f"🤗 Sending hello message to {target_id}")
            enqueue_message(target_id, peer_config[target_id]["ip"], peer_config[target_id]["port"], hello_msg)

    threading.Thread(target=loop, daemon=True).start()

def handle_hello_message(msg, self_id):
    print(f"🤗 Received hello message from {msg['sender_id']}")

    new_peers = []
    
    # Read information in the received `hello` message.
    sender_id = msg["sender_id"]
    sender_ip = msg["ip"]
    sender_port = msg["port"]
    sender_nat, sender_light = msg["flags"]["nat"], msg["flags"]["light"]

    # If the sender is unknown, add it to the list of known peers (`known_peer`) and record their flags (`peer_flags`).
    if sender_id not in known_peers:
        known_peers[sender_id] = (sender_ip, sender_port)
        peer_flags[sender_id] = {
            "nat": sender_nat,
            "light": sender_light
        }
        new_peers.append(sender_id)

    # Update the set of reachable peers (`reachable_by`).
    if sender_id not in reachable_by:
        reachable_by[sender_id] = set()
    if self_id not in reachable_by:
        reachable_by[self_id] = set()
    reachable_by[sender_id].add(self_id)
    reachable_by[self_id].add(sender_id)    

    return new_peers 


