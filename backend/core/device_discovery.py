import socket
import threading
import time
import json
import platform
from backend.config import get_settings
from backend.core.device_manager import device_manager

_discovered = {}  # 设备名称 -> IP 映射表（全局缓存）


class DeviceDiscoveryThread(threading.Thread):
    def __init__(self, on_device_found):
        super().__init__(daemon=True)
        self.on_device_found = on_device_found
        self.running = True
        self.port = get_settings().get("discovery_port", 17257)

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("", self.port))
            sock.settimeout(1.0)
            print(f"📡 正在监听设备广播 (port {self.port}) ...")
        except OSError as e:
            print(f"❌ 无法绑定 UDP 端口 {self.port}：", e)
            return

        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                info = json.loads(data.decode("utf-8"))
                name = info.get("name", addr[0])
                ip = addr[0]

                # ✅ 更新全局设备缓存
                device_manager.update_device(name, ip)

                # ✅ 通知 UI 回调
                self.on_device_found(name, ip)

            except socket.timeout:
                continue
            except Exception as e:
                print("❌ UDP 接收错误:", e)

        sock.close()

    def stop(self):
        self.running = False


class BroadcastThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.running = True
        self.config = get_settings()
        self.port = self.config.get("discovery_port", 17257)
        self.device_name = self.config.get("device_name", platform.node())

    def run(self):
        while self.running:
            try:
                self.broadcast()
                time.sleep(5)
            except Exception as e:
                print("❌ 广播失败:", e)

    def broadcast(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        msg = json.dumps({"name": self.device_name}).encode("utf-8")
        sock.sendto(msg, ("255.255.255.255", self.port))
        sock.close()

    def stop(self):
        self.running = False

    def update_name(self, new_name):
        self.device_name = new_name
        print(f"🔁 广播设备名已更新为: {new_name}")


class DeviceDiscoveryService:
    def __init__(self, on_device_found):
        self.broadcast_thread = BroadcastThread()
        self.discovery_thread = DeviceDiscoveryThread(on_device_found)

    def start(self):
        self.broadcast_thread.start()
        self.discovery_thread.start()

    def restart_broadcast(self, new_name=None):
        if new_name:
            self.broadcast_thread.update_name(new_name)
        # 重启广播线程（简化：这里只更新 name）
        print("🔁 重启广播线程 (不实际 kill 线程，只更新 name)")

    def stop(self):
        self.broadcast_thread.stop()
        self.discovery_thread.stop()