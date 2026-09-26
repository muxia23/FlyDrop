import json
import os
import platform
import threading

# 配置文件固定放在 backend 目录下，避免与前端 config.json 冲突，也不依赖启动时的工作目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULTS = {
    "share_path": os.path.expanduser("~"),
    "port": 8010,
    "device_name": platform.node() or "未命名设备",
    "discovery_port": 17257,
    "access_password": "",
    "allowed_ips": ["127.0.0.1", "::1"],
    "https_enabled": True,
    "cert_path": "cert.pem",
    "key_path": "key.pem"
}

_lock = threading.Lock()


def _write(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_settings():
    with _lock:
        config = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                print("⚠️ config.json 无法读取，使用默认配置")
        else:
            print("📂 config.json 不存在，将使用默认配置")

        # 合并并写回（仅在有缺失字段时写回）
        merged = {**DEFAULTS, **config}
        if merged != config:
            _write(merged)
        return merged


def save_settings(data):
    with _lock:
        _write(data)


def resolve_path(path):
    """相对路径（证书等）统一相对于 backend 目录"""
    path = os.path.expanduser(path)
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)
