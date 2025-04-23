import socket
import threading
import time
import json
import platform

class DeviceDiscoveryThread(threading.Thread):
    def __init__(self, on_device_found, port=17257):
        super().__init__(daemon=True)
        self.on_device_found = on_device_found
        self.port = port

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", self.port))
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                info = json.loads(data.decode())
                name = info.get("name", addr[0])
                self.on_device_found(name, addr[0])
            except Exception as e:
                print("UDP 接收错误:", e)

class BroadcastThread(threading.Thread):
    def __init__(self, name, port=17257):
        super().__init__(daemon=True)
        self.name = name
        self.port = port

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        msg = json.dumps({"name": self.name}).encode("utf-8")

        while True:
            try:
                sock.sendto(msg, ("255.255.255.255", self.port))
                time.sleep(5)
            except Exception as e:
                print("UDP 广播失败:", e)

def get_device_name():
    return platform.node()