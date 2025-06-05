# CS305 2025 Spring Final Project - Blockchain Network Simulation Report

> 本项目托管于Github，访问链接：https://github.com/OptimistiCompound/SUSTech_CS305_BlockChain

#### 小组成员：钟庸，陈佳林，倪汇智

### 负责工作
||工作|
|:-:|:-:|
|钟庸   | socket_server.py, peer_discovery.py, outbox.py, message_handler.py |
|陈佳林 | peer_manager.py, block_handler.py, inv_message.py, transaction.py, dashboard.py |
|倪汇智 | |

## 各模块实现

## Part 1: Peer Initialization (`socket_server.py`)

创建TCP socket，绑定到ip和port，开始监听。
- 每当收到消息后，使用 `json.loads` 解析消息，并调用 `dispatch_message` 进行分发处理。
- 若收到空消息或无效 JSON，会直接跳过或打印错误日志，保证服务稳定。

```python
def start_socket_server(self_id, self_ip, port):
    def listen_loop():
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.bind((self_ip, port))
        peer_socket.listen()
        print(f"Listening on {self_ip}:{port}")
        while True:
            try:
                conn, addr = peer_socket.accept()
                with conn:
                    msg = conn.recv(RECV_BUFFER)
                    if not msg:
                        continue
                    try:
                        msg_dict = json.loads(msg)
                        dispatch_message(msg_dict, self_id, self_ip)
                    except json.JSONDecodeError:
                        print(f"从{addr}接收到无效JSON数据")
            except Exception as e:
                print(f"❌ Error receiving message: {e} in peer {self_id} at {self_ip}:{port}")
    threading.Thread(target=listen_loop, daemon=True).start()
```


## Part 2: Peer Discovery

### `Peer_discovery.py`

在 peer 初始化的时候，调用start_peer_discovery，开始进行peer discovery。start_peer_discovery会根据 peer_config 创建reachable_peer_list：
- 通过两层循环，计算每个 peer 的 reachable_by 集合，表示哪些 peer 能到达该节点（考虑 NAT 和局域网约束）。
- 非 NAT 节点可被所有节点到达。
NAT 节点只能被同局域网的节点到达。
创建 reachable_peer_list 全局一致。然后启动一个线程，每隔DISCOVERY_INTERVAL秒调用一次discover_peers。discover_peers会遍历reachable_peer_list，向每个peer发送 HELLO 消息，然后等待响应。收到响应后，会调用handle_discover_response处理响应:
- 如果 sender 不在 known_peer 中, 会将该节点加入到该节点的 known_peer 中。
- 如果 sender 不再 reachable_by[self_id] 中，会将该节点加入到 reachable_by[self_id] 中。

```python
def start_peer_discovery(self_id, self_info):
    ...
    ...
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


def handle_hello_message(msg, self_id):
    ...
    # If the sender is unknown, add it to the list of known peers (`known_peer`) and record their flags (`peer_flags`).
    if sender_id not in known_peers:
        known_peers[sender_id] = (sender_ip, sender_port)
        peer_flags[sender_id] = {
            "nat": sender_nat,
            "light": sender_light
        }
        new_peers.append(sender_id)
    ...

    # Update the set of reachable peers (`reachable_by`).
    if sender_id not in reachable_by[self_id]:
        reachable_by[self_id].add(sender_id)
```


### `Peer_manager.py`

该模块负责监控各节点存活状态、管理 RTT 延迟信息，并实现简单的黑名单封禁机制。

主要功能：

- `start_ping_loop(self_id, peer_table, interval=15)`：周期性向所有已知节点发送 PING 消息，检测节点是否在线。
- `handle_pong(msg)`：收到 PONG 响应后，测量 RTT 延迟并更新节点活性状态。
- `start_peer_monitor(timeout=10, check_interval=2)`：定时检测节点是否超时未响应，及时将失联节点标记为 "UNREACHABLE"。
- 黑名单机制：统计恶意行为（如非法区块），超过阈值自动将节点加入黑名单，确保网络安全与健壮性。

```python
def start_ping_loop(self_id, peer_table, interval=15):
    def loop():
       while True:
            cur_time = time.time()
            for peer_id, (ip, port) in peer_table.items():
                if peer_id == self_id:
                    continue
                msg = {
                    "type": "PING",
                    "sender": self_id,
                    "timestamp": cur_time,
                    "message_id": generate_message_id()
                }
                enqueue_message(peer_id, ip, port, msg)
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True).start()

def handle_pong(msg):
    sender = msg.get("sender")
    sent_ts = msg.get("timestamp")
    now = time.time()
    if sender is not None and sent_ts is not None:
        rtt = now - sent_ts
        rtt_tracker[sender] = rtt
        update_peer_heartbeat(sender)
```
```python
def record_offense(peer_id):
    peer_offense_counts[peer_id] += 1
    if peer_offense_counts[peer_id] > 0:
        blacklist.add(peer_id)
        print(f"[{peer_id}] has been added to the blacklist due to repeated offenses.")
```



## Part 3: Block and Transaction Generation and Verification

### `Block_handler.py`

主要负责生成区块和验证区块。
- `block_generation` `create_dummy_block` 函数用于生成一个新的区块。
- `handle_block` 函数用于接收区块，验证其block_id的合法性，并将其添加到 `received_blocks` 列表中。如果收到同一个peer的不合法消息超过3个，将其记作恶意节点。如果收到的块没有匹配的上一个block的id，将其加入到 `orphan_blocks` 列表中。


```python
def block_generation(self_id, MALICIOUS_MODE, interval=20):
    from inv_message import create_inv
    def mine():
        while True:
            # 创建新区块
            block = create_dummy_block(self_id, MALICIOUS_MODE)
            if block is not None:
                # 生成INV消息并广播
                inv_msg = create_inv([block["block_id"]], self_id)
                gossip_message([peer for peer in known_peers if peer != self_id], inv_msg)
            time.sleep(interval)
    threading.Thread(target=mine, daemon=True).start()
```
```python
def handle_block(msg, self_id):
    block_id = msg.get("block_id")
    expected_hash = compute_block_hash(msg)
    if block_id != expected_hash:
        record_offense(msg.get("sender"))
        print(f"Invalid block ID {block_id} from {msg.get('sender')}, expected {expected_hash}")
        return False
    if any(b["block_id"] == block_id for b in received_blocks):
        return False
    prev_id = msg.get("previous_block_id")
    if prev_id != "GENESIS" and not any(b["block_id"] == prev_id for b in received_blocks):
        orphan_blocks[block_id] = msg
        return False
    receive_block(msg)
    return True
```

### `transaction.py`

该模块负责生成、验证交易，并维护本地交易池。

主要功能：

- `TransactionMessage` 类：封装了交易的各项属性（发送者、接收者、金额、时间戳、唯一哈希 ID 等），便于序列化和网络传输。
- `transaction_generation(self_id, interval=15)`：周期性自动生成并广播新的交易消息，每隔一定时间随机生成一次，模拟真实网络的交易流量。
- `add_transaction(tx)`：去重后将新交易加入本地交易池。
- `get_recent_transactions()`：返回交易池内所有交易的字典列表，用于状态展示与区块打包。
- `clear_pool()`：打包新区块后清空交易池。

```python
class TransactionMessage:
    def __init__(self, sender, receiver, amount, timestamp=None):
        self.type = "TX"
        self.from_peer = sender
        self.to_peer = receiver
        self.amount = amount
        self.timestamp = timestamp if timestamp else time.time()
        self.id = self.compute_hash()
    def compute_hash(self):
        tx_data = {
            "type": self.type,
            "from": self.from_peer,
            "to": self.to_peer,
            "amount": self.amount,
            "timestamp": self.timestamp
        }
        return hashlib.sha256(json.dumps(tx_data, sort_keys=True).encode()).hexdigest()
    def to_dict(self):
        return {
            "type": self.type,
            "tx_id": self.id,
            "from": self.from_peer,
            "to": self.to_peer,
            "amount": self.amount,
            "timestamp": self.timestamp
        }
```
```python
def transaction_generation(self_id, interval=15):
    def loop():
        while True:
            candidates = [peer for peer in known_peers if peer != self_id]
            if not candidates:
                time.sleep(interval)
                continue
            to_peer = random.choice(candidates)
            amount = random.randint(1, 100)
            tx = TransactionMessage(self_id, to_peer, amount)
            add_transaction(tx)
            gossip_message([peer for peer in known_peers if peer != self_id], tx.to_dict())
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True).start()
```


### `inv_message.py`

该模块负责区块链网络中区块广播、同步的 INV 消息机制。

主要功能如下：

- `create_inv(block_ids, sender_id)`：根据给定的区块 ID 列表和发送者 ID 构建 INV 消息（格式为字典），用于通知其他节点有新块可同步。
- `get_inventory()`：返回本节点已持有的所有区块 ID 列表。
- `broadcast_inventory(self_id)`：自动构建 INV 消息并向所有其他已知节点广播，告知新获得的区块信息，实现区块间的快速同步。

**实现要点：**
- 利用 `gossip_message()` 完成消息的广播，自动排除自身节点，保证消息只发送给其他节点。
- 与区块生成、区块请求等模块协同，实现区块链主链的全网同步。

```python
def create_inv(block_ids, sender_id):
    return {
        "type": "INV",
        "sender": sender_id,
        "block_ids": block_ids,
        "message_id": generate_message_id()
    }

def broadcast_inventory(self_id):
    inv_msg = create_inv(get_inventory(), self_id)
    peer_ids = [peer_id for peer_id in known_peers if peer_id != self_id]
    gossip_message(peer_ids, inv_msg)
```


## Part 4: Sending Message Processing (outbox.py)

负责消息的发送。维护一个消息队列 queue，用于存储待发送的消息。
发送消息的时候按照优先级发送,当优先级高的消息没有发送完的时候,会先发送优先级高的消息,当优先级高的消息发送完了,才发送优先级低的消息。
如果发送目的节点不可达,是nat节点,会将消息发送发给对应的relay节点,然后通过relay节点的消息队列forwarding给最终的nat节点。

此外，还通过 `RateLimiter` 类来模拟真实网络的发送速率限制。


## PART 5: Receiving Message Processing (message_handler.py)

处理消息接受。主要通过`dispatch_message`方法，按照message的type来分类处理。
此外，通过维护 seen_message_ids，seen_txs，redundant_blocks，redundant_txs，message_redundancy，处理重复接受的消息。并且通过`is_inbound_limited`方法，限制消息接收的速度


## Part 6: Dashboard 可视化面板 (`dashboard.py`)

该模块基于 Flask 实现，为模拟区块链网络提供实时可视化界面。通过访问 HTTP 接口，用户可以直观地查看区块链、节点、交易、消息队列等关键信息，便于调试、观测网络状态和性能。

主要功能接口如下：

- `/`：首页，展示项目基本信息。
- `/blocks`：展示本节点已接收的区块链内容（`received_blocks`）。
- `/peers`：展示所有已知节点的详细信息，包括 NAT/Light 节点标记、状态等。
- `/transactions`：展示本地交易池当前所有交易。
- `/latency`：展示与其他节点的 RTT（延迟）信息，便于分析网络延迟状况。
- `/capacity`：预留接口，可用于后续扩展展示带宽或吞吐量等信息。
- `/orphans`：展示孤块池 orphan_blocks，便于追踪未被主链接收的区块。
- `/queue`：展示消息队列队列内容，按节点和优先级分类。
- `/redundancy`：展示冗余消息统计，通过调用 `get_redundancy_stats()` 获取信息。
- `/blacklist`：展示黑名单，便于观测恶意节点的封禁情况。

此外还提供了若干 debug 接口，如 `/reachable`、`/peer_config`、`/known_peers`、`/peer_flags`、`/drop_stats` 等，用于调试和展示网络内部状态。


## 运行说明

1. 使用 `docker compose up --build` 启动所有节点，每个节点运行在独立容器内。
2. 节点自动完成初始化、发现、消息收发、区块与交易生成。
3. 通过访问各节点 `localhost:port` 下不同接口，观察区块链、交易池、队列、节点状态等实时数据。
