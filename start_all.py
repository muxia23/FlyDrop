# start_all.py

from PySide6.QtWidgets import QApplication
from frontend.file_browser import FileBrowser
from backend.device_discovery import BroadcastThread
import subprocess
import threading
import sys

def run_backend():
    subprocess.Popen(["python", "backend/file_server.py"])

if __name__ == "__main__":
    # 启动广播线程
    broadcast = BroadcastThread()
    broadcast.start()

    # 启动后端
    threading.Thread(target=run_backend, daemon=True).start()

    # 启动前端
    app = QApplication(sys.argv)
    window = FileBrowser()
    window.show()
    sys.exit(app.exec())