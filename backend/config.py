# backend/config.py

import json
import os

CONFIG_PATH = "config.json"

default_config = {
    "device_name": "未命名设备",
    "broadcast_enabled": True,
    "share_port": 17257,
    "share_path": ""
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"⚠️ config.json 读取失败，将使用默认配置: {e}")
    return default_config.copy()

def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)