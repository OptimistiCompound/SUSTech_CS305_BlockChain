from flask import Flask, jsonify
from threading import Thread
from peer_manager import peer_status, rtt_tracker
from transaction import get_recent_transactions
from link_simulator import rate_limiter
from message_handler import get_redundancy_stats
from peer_discovery import known_peers
import json
from block_handler import received_blocks

app = Flask(__name__)
blockchain_data_ref = None
known_peers_ref = None

def start_dashboard(peer_id, port):
    global blockchain_data_ref, known_peers_ref
    blockchain_data_ref = received_blocks
    known_peers_ref = known_peers
    def run():
        app.run(host="0.0.0.0", port=port)
    Thread(target=run, daemon=True).start()

@app.route('/')
def home():
    return "Block P2P Network Simulation"

@app.route('/blocks')
def blocks():
    # TODO: display the blocks in the local blockchain.
    pass

@app.route('/peers')
def peers():
    # TODO: display the information of known peers, including `{peer's ID, IP address, port, status, NATed or non-NATed, lightweight or full}`.
    pass

@app.route('/transactions')
def transactions():
    # TODO: display the transactions in the local pool `tx_pool`.
    pass

@app.route('/latency')
def latency():
    # TODO: display the transmission latency between peers.
    pass

@app.route('/capacity')
def capacity():
    # TODO: display the sending capacity of the peer.
    pass

@app.route('/orphans')
def orphan_blocks():
    # TODO: display the orphaned blocks.
    pass

@app.route('/redundancy')
def redundancy_stats():
    # TODO: display the number of redundant messages received.
    pass


