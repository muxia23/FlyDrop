# utils/network.py

import socket
import threading
import json
import time

UDP_PORT = 17257
BROADCAST_INTERVAL = 3  # 每 3 秒广播一次

class DeviceDiscovery:
    def __init__(self, device_name, on_device_found):
        self.device_name = device_name
        self.on_device_found = on_device_found  # 回调：新设备发现时执行
        self.running = False
        self.devices = {}  # ip -> device_name

    def _get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # 连一个不存在的地址来获取本地 IP
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def start(self):
        self.running = True
        threading.Thread(target=self._broadcast_loop, daemon=True).start()
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def stop(self):
        self.running = False

    def _broadcast_loop(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self.running:
            message = {
                "device_name": self.device_name,
                "ip": self._get_local_ip()
            }
            s.sendto(json.dumps(message).encode('utf-8'), ('255.255.255.255', UDP_PORT))
            time.sleep(BROADCAST_INTERVAL)

    def _listen_loop(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(('', UDP_PORT))
        while self.running:
            try:
                data, addr = s.recvfrom(1024)
                message = json.loads(data.decode('utf-8'))
                sender_ip = addr[0]
                if sender_ip != self._get_local_ip():  # 排除自己
                    if sender_ip not in self.devices:
                        self.devices[sender_ip] = message["device_name"]
                        self.on_device_found(sender_ip, message["device_name"])
            except Exception as e:
                print(f"接收设备信息时出错: {e}")