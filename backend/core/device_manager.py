# backend/core/device_manager.py

import threading
import time

EXPIRE_SECONDS = 15


class DeviceManager:
    def __init__(self):
        self.devices = {}  # ip -> {name, port, https, last_seen}
        self.lock = threading.Lock()

    def update_device(self, name, ip, port=None, https=None):
        """更新设备信息，返回是否为新出现（或重新上线）的设备"""
        with self.lock:
            now = time.time()
            old = self.devices.get(ip)
            is_new = old is None or now - old["last_seen"] > EXPIRE_SECONDS or old["name"] != name
            self.devices[ip] = {
                "name": name,
                "port": port,
                "https": https,
                "last_seen": now
            }
            return is_new

    def get_devices(self):
        with self.lock:
            # 只返回最近15秒有响应的设备（防止过期设备）
            now = time.time()
            return [
                {"name": info["name"], "ip": ip, "port": info["port"], "https": info["https"]}
                for ip, info in self.devices.items()
                if now - info["last_seen"] <= EXPIRE_SECONDS
            ]


# 单例
device_manager = DeviceManager()
