# backend/core/device_manager.py

import threading
import time

class DeviceManager:
    def __init__(self):
        self.devices = {}  # name -> {ip, last_seen}
        self.lock = threading.Lock()

    def update_device(self, name, ip):
        with self.lock:
            self.devices[name] = {
                "ip": ip,
                "last_seen": time.time()
            }

    def get_devices(self):
        with self.lock:
            # 只返回最近15秒有响应的设备（防止过期设备）
            now = time.time()
            return [
                {"name": name, "ip": info["ip"]}
                for name, info in self.devices.items()
                if now - info["last_seen"] <= 15
            ]

# 单例
device_manager = DeviceManager()