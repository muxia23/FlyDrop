from backend.device_discovery import DeviceDiscoveryThread, BroadcastThread, get_device_name
from frontend.settings_dialog import SettingsDialog
import sys
import requests
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLineEdit,
    QFileDialog, QMessageBox, QComboBox
)
from PySide6.QtCore import Qt


class FileBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LAN 文件共享助手")
        self.setGeometry(100, 100, 600, 400)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["文件名"])
        self.tree.itemExpanded.connect(self.on_item_expanded)

        self.show_hidden = False
        self.current_path = ""
        self.filter_text = ""

        self.base_url = "http://localhost:8010"

        # 按钮：切换显示隐藏文件
        self.toggle_button = QPushButton("显示隐藏文件")
        self.toggle_button.clicked.connect(self.toggle_hidden)

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索")
        self.search_input.textChanged.connect(self.on_search_changed)

        # 刷新
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.reset_browser)

        # 下载按钮
        self.download_button = QPushButton("下载")
        self.download_button.clicked.connect(self.download_selected_file)

        # 设备下拉框
        self.device_box = QComboBox()
        self.device_box.currentIndexChanged.connect(self.on_device_changed)
        self.device_map = {}  # 设备名称 -> IP

        # 设置
        self.settings_button = QPushButton("⚙ 设置")
        self.settings_button.clicked.connect(self.open_settings)

        # 顶部布局
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.device_box)
        top_layout.addWidget(self.toggle_button)
        top_layout.addWidget(self.search_input)
        top_layout.addWidget(self.refresh_button)
        top_layout.addWidget(self.download_button)
        top_layout.addWidget(self.settings_button)

        # 主体布局
        layout = QVBoxLayout()
        layout.addLayout(top_layout)
        layout.addWidget(self.tree)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.load_directory("")
        # 启动广播和监听
        self.discovery_thread = DeviceDiscoveryThread(self.add_device)
        self.discovery_thread.start()

        self.broadcast_thread = BroadcastThread()
        self.broadcast_thread.start()

    def add_device(self, name, ip):
        if name not in self.device_map:
            self.device_box.addItem(name)
            self.device_map[name] = ip
        # 默认使用第一个设备 IP 作为文件列表请求地址
        self.base_url = f"http://{self.device_map[self.device_box.currentText()]}:8010"

    def on_device_changed(self):
        name = self.device_box.currentText()
        if name in self.device_map:
            self.base_url = f"http://{self.device_map[name]}:8010"
            self.refresh()

    def toggle_hidden(self):
        self.show_hidden = not self.show_hidden
        self.toggle_button.setText("隐藏隐藏文件" if self.show_hidden else "显示隐藏文件")
        self.refresh()

    def on_search_changed(self, text):
        self.filter_text = text.strip().lower()
        self.refresh()

    def refresh(self):
        self.tree.clear()
        self.load_directory(self.current_path)

    def load_directory(self, path, parent=None):
        self.current_path = path
        try:
            url = f"{self.base_url}/list"
            response = requests.get(url, params={"path": path})
            response.raise_for_status()
            data = response.json()

            for item in data:
                name = item["name"]
                if not self.show_hidden and name.startswith("."):
                    continue
                if self.filter_text and self.filter_text not in name.lower():
                    continue

                tree_item = QTreeWidgetItem([name])
                tree_item.setData(0, Qt.UserRole, item["path"])
                if item["type"] == "dir":
                    tree_item.addChild(QTreeWidgetItem(["加载中..."]))
                if parent:
                    parent.addChild(tree_item)
                else:
                    self.tree.addTopLevelItem(tree_item)

        except Exception as e:
            print("❌ 加载失败:", e)

    def on_item_expanded(self, item):
        if item.childCount() == 1 and item.child(0).text(0) == "加载中...":
            item.takeChildren()
            path = item.data(0, Qt.UserRole)
            self.load_directory(path, parent=item)

    def reset_browser(self):
        self.filter_text = ""
        self.search_input.clear()
        self.current_path = ""
        self.refresh()

    def download_selected_file(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "未选择", "请先选择一个文件再点击下载。")
            return

        item = selected_items[0]
        file_path = item.data(0, Qt.UserRole)
        name = item.text(0)

        # 如果是文件夹不给下载
        if item.childCount() > 0 and item.child(0).text(0) == "加载中...":
            QMessageBox.information(self, "提示", "请选择文件，而不是文件夹。")
            return

        # 弹出保存文件对话框
        save_path, _ = QFileDialog.getSaveFileName(self, "保存文件", name)
        if not save_path:
            return

        try:
            url = f"{self.base_url}/download"
            response = requests.get(url, params={"path": file_path}, stream=True)
            response.raise_for_status()

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            QMessageBox.information(self, "成功", f"文件已保存到：\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"下载失败：{e}")

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()




if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FileBrowser()
    window.show()
    sys.exit(app.exec())