# backend/main.py

import uvicorn
from fastapi import FastAPI
from backend.config import get_settings, save_settings
from backend.cert_manager.cert_manager import ensure_https_cert, get_local_ip
from fastapi.middleware.cors import CORSMiddleware
import socket
from backend.core.device_discovery import DeviceDiscoveryService
from backend.api import clipboard, files, devices
import threading

service = None  # 全局广播服务实例
app = FastAPI(title="FlyDrop")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(files.router, prefix="/api/files")
app.include_router(clipboard.router, prefix="/api/clipboard")
app.include_router(devices.router, prefix="/api")

@app.get("/")
def root():
    return {"status": "running", "version": "1.0"}

# 检查端口是否被占用
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0

def ask_for_new_port(current_port):
    print(f"\n⚠️ 端口 {current_port} 已被占用。")
    choice = input("是否使用下一个端口（+1）？[Y/n] 或输入新端口号：").strip()

    if choice.lower() == 'n':
        print("终止启动。")
        exit(1)
    elif choice.isdigit():
        return int(choice)
    else:
        return current_port + 1

def on_device_found(name, ip):
    print(f"发现设备：{name} @ {ip}")

if __name__ == "__main__":
    config = get_settings()
    port = config["port"]

    # 启动设备发现服务（UDP 广播 + 接收）
    service = DeviceDiscoveryService(on_device_found)
    service.start()

    if config.get("https_enabled", False):
        cert = config.get("cert_path", "cert.pem")
        key = config.get("key_path", "key.pem")
        ensure_https_cert(cert, key)

        uvicorn.run("backend.main:app", host="0.0.0.0", port=port,
                    ssl_certfile=cert, ssl_keyfile=key)
    else:
        uvicorn.run("backend.main:app", host="0.0.0.0", port=port)