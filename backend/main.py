# backend/main.py

import os
import sys

# 允许直接在 backend 目录下运行 `python main.py`（把项目根目录加入 import 路径）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Windows 控制台可能不是 UTF-8，避免打印 emoji / 中文时崩溃
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

import socket
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings, save_settings, resolve_path
from backend.cert_manager.cert_manager import ensure_https_cert
from backend.core.device_discovery import DeviceDiscoveryService
from backend.api import clipboard, files, devices, settings as settings_api


def on_device_found(name, ip):
    print(f"发现设备：{name} @ {ip}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动设备发现服务（UDP 广播 + 接收），与 app 在同一个模块实例中，便于设置接口热更新
    service = DeviceDiscoveryService(on_device_found)
    service.start()
    settings_api.discovery_service = service
    yield
    service.stop()


app = FastAPI(title="FlyDrop", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(files.router, prefix="/api/files")
app.include_router(clipboard.router, prefix="/api/clipboard")
app.include_router(devices.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api/settings")


@app.get("/")
def root():
    config = get_settings()
    return {"status": "running", "version": "1.1", "name": config.get("device_name")}


# 检查端口是否被占用
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def ask_for_new_port(current_port):
    print(f"\n⚠️ 端口 {current_port} 已被占用。")
    choice = input("是否使用下一个端口（+1）？[Y/n] 或输入新端口号：").strip()

    if choice.lower() == 'n':
        print("终止启动。")
        sys.exit(1)
    elif choice.isdigit():
        return int(choice)
    else:
        return current_port + 1


def main():
    config = get_settings()
    port = config["port"]
    while is_port_in_use(port):
        port = ask_for_new_port(port)
    if port != config["port"]:
        # 记住新端口，保证广播出去的端口与实际一致
        config["port"] = port
        save_settings(config)

    print(f"📁 共享目录: {config['share_path']}")
    print(f"💻 设备名称: {config['device_name']}")

    kwargs = {"host": "0.0.0.0", "port": port}
    if config.get("https_enabled", False):
        cert = resolve_path(config.get("cert_path", "cert.pem"))
        key = resolve_path(config.get("key_path", "key.pem"))
        ensure_https_cert(cert, key)
        kwargs.update(ssl_certfile=cert, ssl_keyfile=key)

    # 直接传 app 对象，避免模块被二次导入
    uvicorn.run(app, **kwargs)


if __name__ == "__main__":
    main()
