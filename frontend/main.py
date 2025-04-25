# frontend/main.py

import sys
import traceback
from PySide6.QtWidgets import QApplication, QMainWindow
from frontend.pages.file_download import FileDownloadPage

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlyDrop - 局域网文件助手")
        self.setGeometry(300, 200, 1000, 600)

        self.page = FileDownloadPage()
        self.setCentralWidget(self.page)

def main():
    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())

    except Exception as e:
        print("❌ 启动异常:")
        traceback.print_exc()

if __name__ == "__main__":
    main()