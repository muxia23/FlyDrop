# frontend/config.py
import json
import os

# 配置文件固定放在 frontend 目录下，避免与后端 config.json 冲突
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULTS = {
    "port": 8010,                       # 本机后端端口
    "discovery_port": 17257,
    "access_password": "",              # 访问其他设备时使用的密码
    "base_url": "https://localhost:8010",  # 本机后端地址
    "download_dir": os.path.join(os.path.expanduser("~"), "Downloads", "FlyDrop"),
    "clipboard_auto_sync": False,       # 是否自动同步剪贴板
    "clipboard_interval": 2             # 自动同步轮询间隔（秒）
}


def get_settings():
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
        save_settings(merged)
    return merged


def save_settings(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
