# CS305 2025 Spring Final Project - Blockchain Network Simulation Report

> 本项目托管于Github，访问链接：https://github.com/OptimistiCompound/SUSTech_CS305_BlockChain

#### 小组成员：钟庸，陈佳林，倪汇智

### 负责工作
||工作|
|:-:|:-:|
|钟庸   | socket_server.py, peer_discovery.py, outbox.py, message_handler.py |
|陈佳林 | peer_manager.py, block_handler.py, inv_message.py, dashboard.py |
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

主要作用是向其他节点发送 PING 消息，告诉其他节点自己存活，并向对方确认对方是否存活或者是否可达。如果收到对方的 PONG 消息，说明对方存活。



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

### `transaction.py`

主要负责生成交易和验证交易。包含了一个`TransactionMessage`类，用于表示交易消息。
- `transaction_generation` 函数用于生成一个新的交易。

还负责维护本地的交易池 `tx_pool`，用于存储待广播的交易。

### `inv_message.py`
主要负责生成广播消息。本地生成交易后需要向别的 peer 广播 INV 消息。
维护 INV 消息的生成和处理。包含了一个`InvMessage`类，用于表示 INV 消息。
- `create_inv` 函数用于生成一个 INV 消息。
- `handle_inv` 函数用于接收 INV 消息，将其添加到 `received_inv` 列表中。如果收到同一个peer的不合法消息超过3个，将其记作恶意节点。


## Part 4: Sending Message Processing (outbox.py)

负责消息的发送。维护一个消息队列 queue，用于存储待发送的消息。
发送消息的时候按照优先级发送,当优先级高的消息没有发送完的时候,会先发送优先级高的消息,当优先级高的消息发送完了,才发送优先级低的消息。
如果发送目的节点不可达,是nat节点,会将消息发送发给对应的relay节点,然后通过relay节点的消息队列forwarding给最终的nat节点。

此外，还通过 `RateLimiter` 类来模拟真实网络的发送速率限制。


## PART 5: Receiving Message Processing (message_handler.py)

处理消息接受。主要通过`dispatch_message`方法，按照message的type来分类处理。
此外，通过维护 seen_message_ids，seen_txs，redundant_blocks，redundant_txs，message_redundancy，处理重复接受的消息。并且通过`is_inbound_limited`方法，限制消息接收的速度



## 运行说明

