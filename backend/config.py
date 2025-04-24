import json
import os

CONFIG_PATH = "config.json"

DEFAULTS = {
    "share_path": os.path.expanduser("~/Downloads"),
    "port": 8010,
    "device_name": "未命名设备",
    "discovery_port": 17257,
    "access_password": "",
    "allowed_ips": ["127.0.0.1"],
    "https_enabled": True,
    "cert_path": "cert.pem",
    "key_path": "key.pem"
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