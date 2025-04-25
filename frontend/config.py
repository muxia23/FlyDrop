# frontend/config.py
import json
import os

CONFIG_PATH = "config.json"

DEFAULTS = {
    "port": 8010,
    "discovery_port": 17257,
    "access_password": "",
    "base_url": "https://localhost:8010",
    "download_dir": os.path.expanduser("~/Downloads")
}

def get_settings():
    config = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
        except Exception:
            print("⚠️ config.json 无法读取，使用默认配置")
    else:
        print("📂 config.json 不存在，将使用默认配置")

    # 合并并写回
    config = {**DEFAULTS, **config}
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    return config

def save_settings(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)
