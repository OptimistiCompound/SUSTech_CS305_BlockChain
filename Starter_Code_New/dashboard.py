from flask import Flask, jsonify
from threading import Thread
from peer_manager import peer_status, rtt_tracker, blacklist
from transaction import get_recent_transactions
# from link_simulator import rate_limiter
from message_handler import get_redundancy_stats
from peer_discovery import known_peers, peer_config, peer_flags
import json
from block_handler import received_blocks, orphan_blocks
from outbox import queues

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
    # 展示本地区块链（received_blocks）
    return jsonify(received_blocks)

@app.route('/peers')
def peers():
    # 展示已知节点详细信息
    result = []
    for pid, (ip, port) in known_peers.items():
        flags = peer_flags.get(pid, {})
        cfg = peer_config.get(pid, {})
        info = {
            "peer_id": pid,
            "ip": ip,
            "port": port,
            "status": peer_status.get(pid, "UNKNOWN"),
            "nat": flags.get("nat", cfg.get("nat", False)),
            "light": flags.get("light", cfg.get("light", False))
        }
        result.append(info)
    return jsonify(result)

@app.route('/transactions')
def transactions():
    # 展示本地交易池
    txs = get_recent_transactions()
    return jsonify(txs)

@app.route('/latency')
def latency():
    # 展示与其他节点的 rtt（延迟）
    # rtt_tracker: {peer_id: float}
    return jsonify(rtt_tracker)

@app.route('/capacity')
def capacity():
    # 展示本节点发送能力
    # rate_limiter.capacity 当前允许的速率
    return jsonify({"capacity": getattr(rate_limiter, "capacity", None)})

@app.route('/orphans')
def orphan_blocks():
    # 展示孤块池 orphan_blocks: dict
    # 转为 list
    return jsonify(list(orphan_blocks.values()))

@app.route('/queue')
def message_queue():
    # 展示队列内容 queues: defaultdict(lambda: defaultdict(deque))
    # 转为 {peer_id: {priority: [msg, ...]}}
    out = {}
    for pid, prio_dict in queues.items():
        out[pid] = {}
        for prio, dq in prio_dict.items():
            # 转为简单列表
            out[pid][prio] = [str(item) for item in list(dq)]
    return jsonify(out)

@app.route('/redundancy')
def redundancy_stats():
    # 展示冗余消息统计
    return jsonify({"redundancy": get_redundancy_stats()})

@app.route('/blacklist')
def blacklist_display():
    # 展示黑名单
    # blacklist: set or dict
    return jsonify(list(blacklist))


# debug
@app.route('/reachable')
def disp_reachable():
    from peer_discovery import reachable_by
    out = {k: list(v) for k, v in reachable_by.items()}
    return jsonify(out)

@app.route('/peer_config')
def disp_peer_config():
    return jsonify(peer_config)

@app.route('/known_peers')
def disp_known_peers():
    return jsonify(known_peers)

@app.route('/peer_flags')
def disp_peer_flags():
    return jsonify(peer_flags)

@app.route('/drop_stats')
def disp_drop_stats():
    from outbox import drop_stats
    return jsonify(drop_stats)