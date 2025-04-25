from datetime import datetime
import os

def get_log_path():
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join("logs", f"access-{today}.log")

def log_access(ip: str, action: str, path: str, success: bool = True):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = "✅" if success else "❌"
    log_line = f"[{timestamp}] {ip} {action} {path} {result}\n"

    log_path = get_log_path()
    try:
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print("⚠️ 写入日志失败:", e)