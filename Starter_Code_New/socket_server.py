import socket
import threading
import time
import json
from message_handler import dispatch_message

RECV_BUFFER = 4096

def start_socket_server(self_id, self_ip, port):

    def listen_loop():
        # TODO: Create a TCP socket and bind it to the peer’s IP address and port.

        # TODO: Start listening on the socket for receiving incoming messages.

        # TODO: When receiving messages, pass the messages to the function `dispatch_message` in `message_handler.py`.

        pass

    # ✅ Run listener in background
    threading.Thread(target=listen_loop, daemon=True).start()

