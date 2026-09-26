import socket
import threading
import time
import json
import uuid
from backend.config import get_settings
from backend.core.device_manager import device_manager

# 本机实例 ID，用于忽略自己发出的广播
INSTANCE_ID = uuid.uuid4().hex


class DeviceDiscoveryThread(threading.Thread):
    def __init__(self, on_device_found=None):
        super().__init__(daemon=True)
        self.on_device_found = on_device_found
        self.running = True
        self.port = get_settings().get("discovery_port", 17257)

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
                if not isinstance(info, dict) or info.get("id") == INSTANCE_ID:
                    continue  # 忽略自己的广播和无效数据

                name = info.get("name") or addr[0]
                ip = addr[0]
                port = info.get("port")
                https = info.get("https")

                # ✅ 更新全局设备缓存
                is_new = device_manager.update_device(name, ip, port, https)

                # ✅ 通知回调（只在新设备出现时打印，避免刷屏）
                if is_new and self.on_device_found:
                    self.on_device_found(name, ip)

            except socket.timeout:
                continue
            except (ValueError, UnicodeDecodeError):
                continue  # 非本程序的 UDP 包
            except Exception as e:
                print("❌ UDP 接收错误:", e)

        sock.close()

    def stop(self):
        self.running = False


class BroadcastThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.running = True
        self._wakeup = threading.Event()
        self.reload_config()

    def reload_config(self):
        config = get_settings()
        self.port = config.get("discovery_port", 17257)
        self.device_name = config.get("device_name", "未命名设备")
        self.http_port = config.get("port", 8010)
        self.https = bool(config.get("https_enabled", True))

    def run(self):
        while self.running:
            try:
                self.broadcast()
            except Exception as e:
                print("❌ 广播失败:", e)
            self._wakeup.wait(5)
            self._wakeup.clear()

    def broadcast(self):
        msg = json.dumps({
            "id": INSTANCE_ID,
            "name": self.device_name,
            "port": self.http_port,
            "https": self.https,
        }).encode("utf-8")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(msg, ("255.255.255.255", self.port))
        finally:
            sock.close()

    def stop(self):
        self.running = False
        self._wakeup.set()

    def update_name(self, new_name):
        self.device_name = new_name
        print(f"🔁 广播设备名已更新为: {new_name}")
        self._wakeup.set()  # 立即广播一次新名称


class DeviceDiscoveryService:
    def __init__(self, on_device_found=None):
        self.broadcast_thread = BroadcastThread()
        self.discovery_thread = DeviceDiscoveryThread(on_device_found)

    def start(self):
        self.broadcast_thread.start()
        self.discovery_thread.start()

    def restart_broadcast(self, new_name=None):
        """热更新广播内容（设备名等），无需重启线程"""
        self.broadcast_thread.reload_config()
        if new_name:
            self.broadcast_thread.update_name(new_name)

    def stop(self):
        self.broadcast_thread.stop()
        self.discovery_thread.stop()
