from datetime import datetime
import os

LOG_PATH = "access.log"

def log_access(ip: str, action: str, path: str, success: bool = True):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = "✅" if success else "❌"

    log_line = f"[{timestamp}] {ip} {action} {path} {result}\n"

    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print("⚠️ 写入日志失败:", e)