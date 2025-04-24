# backend/device_discovery.py

import socket
import threading
import time
import json
import platform
from backend.config import load_config

class DeviceDiscoveryThread(threading.Thread):
    def __init__(self, on_device_found, port=17257):
        super().__init__(daemon=True)
        self.on_device_found = on_device_found
        self.port = port

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("", self.port))
        except OSError as e:
            print(f"❌ 绑定失败，端口 {self.port} 已被占用: {e}")
            return

        while True:
            try:
                data, addr = sock.recvfrom(1024)
                info = json.loads(data.decode())
                name = info.get("name", addr[0])
                self.on_device_found(name, addr[0])
            except json.JSONDecodeError as e:
                print(f"❌ JSON 解码失败: {e}, 原始数据: {data}")
            except Exception as e:
                print(f"UDP 接收错误: {e}")

class BroadcastThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        config = load_config()
        self.device_name = config.get("device_name", "未命名设备")
        self.port = int(config.get("share_port", 17257))  # 保证是整数

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        msg = json.dumps({"name": self.device_name}).encode("utf-8")  # 修复变量名

        while True:
            try:
                sock.sendto(msg, ("255.255.255.255", self.port))
                print(f"📡 广播中: {self.device_name} on {self.port}")
                time.sleep(3)
            except Exception as e:
                print("UDP 广播失败:", e)

def get_device_name():
    return platform.node()