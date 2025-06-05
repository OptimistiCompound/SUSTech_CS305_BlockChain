import socket
import threading
import time
import json
from message_handler import dispatch_message

RECV_BUFFER = 4096

def start_socket_server(self_id, self_ip, port):

    def listen_loop():
        # Create a TCP socket and bind it to the peer’s IP address and port.
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.bind((self_ip, port))
        peer_socket.listen()
        print(f"Listening on {self_ip}:{port}")
        # When receiving messages, pass the messages to the function `dispatch_message` in `message_handler.py`.
        while True:
            try:
                conn, addr = peer_socket.accept()
                with conn:  # 使用with确保连接正确关闭
                    try:
                        # 用文件对象逐行读取
                        f = conn.makefile()
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                msg_dict = json.loads(line)
                                dispatch_message(msg_dict, self_id, self_ip)
                            except json.JSONDecodeError:
                                print(f"从{addr}接收到无效JSON数据: {line}")
                    except Exception as e:
                        print(f"❌ Error receiving message: {e} in peer {self_id} at {self_ip}:{port}")
            except Exception as e:
                print(f"🔻 Error accepting connection: {e} in peer {self_id} at {self_ip}:{port}")
                continue

    # ✅ Run listener in background
    threading.Thread(target=listen_loop, daemon=True).start()

