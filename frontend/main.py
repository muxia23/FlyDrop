# frontend/main.py

import os
import sys
import traceback

# 允许直接在 frontend 目录下运行 `python main.py`（把项目根目录加入 import 路径）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Windows 控制台可能不是 UTF-8，避免打印 emoji / 中文时崩溃
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
from frontend.pages.file_download import FileDownloadPage
from frontend.pages.clipboard_page import ClipboardPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlyDrop - 局域网文件助手")
        self.setGeometry(300, 200, 1000, 600)

        self.clipboard_page = ClipboardPage()
        self.page = FileDownloadPage()

        # 文件页切换设备时，剪贴板页同步切换目标设备
        self.page.device_changed.connect(self.clipboard_page.set_target)
        self.page.settings_saved.connect(self.clipboard_page.reload_config)
        index = self.page.device_selector.currentIndex()
        if index != -1:
            self.clipboard_page.set_target(self.page.device_selector.itemData(index),
                                           self.page.device_selector.itemText(index))

        self.tabs = QTabWidget()
        self.tabs.addTab(self.page, "📁 文件")
        self.tabs.addTab(self.clipboard_page, "📋 剪贴板")
        self.setCentralWidget(self.tabs)

    def closeEvent(self, event):
        self.page.close()
        self.clipboard_page.shutdown()
        super().closeEvent(event)


def main():
    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())

    except Exception:
        print("❌ 启动异常:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
