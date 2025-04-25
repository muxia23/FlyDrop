from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QFileDialog, QMessageBox, QLabel, QComboBox,
    QProgressDialog, QApplication
)
from PySide6.QtCore import Qt
from frontend.config import get_settings
from frontend.pages.settings_dialog import SettingsDialog
from frontend.threads.downloader import FileDownloadThread
import requests
import os
import uuid

class FileDownloadPage(QWidget):
    def __init__(self):
        super().__init__()

        self.config = get_settings()
        self.base_url = self.config["base_url"]
        self.access_password = self.config["access_password"]
        self.show_hidden = False  # 默认隐藏 . 文件夹和文件

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["文件名"])
        self.tree.itemExpanded.connect(self.expand_directory)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)

        self.tree.setHeaderLabels(["文件名"])
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)

        # 控件
        self.toggle_hidden_button = QPushButton("显示隐藏文件")
        self.refresh_button = QPushButton("刷新")
        self.download_button = QPushButton("下载")
        self.settings_button = QPushButton("⚙ 设置")
        self.zip_button = QPushButton("打包下载")

        self.zip_button.clicked.connect(self.download_zip)
        self.toggle_hidden_button.clicked.connect(self.toggle_hidden)
        self.refresh_button.clicked.connect(self.refresh_root)
        self.download_button.clicked.connect(self.download_selected_file)
        self.settings_button.clicked.connect(self.open_settings_dialog)

        self.device_selector = QComboBox()
        self.device_selector.addItem("本机")
        self.device_selector.currentIndexChanged.connect(self.change_device)

        self.devices = {
            "本机": "https://localhost:8010",
            # 可拓展自动发现设备
        }

        # 布局
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("设备："))
        top_layout.addWidget(self.device_selector)
        top_layout.addStretch()
        top_layout.addWidget(self.toggle_hidden_button)
        top_layout.addWidget(self.refresh_button)
        top_layout.addWidget(self.download_button)
        top_layout.addWidget(self.zip_button)
        top_layout.addWidget(self.settings_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.tree)

        self.load_directory("")

    def change_device(self):
        name = self.device_selector.currentText()
        self.base_url = self.devices.get(name, self.base_url)
        self.refresh_root()

    def refresh_root(self):
        self.tree.clear()
        self.load_directory("")

    def toggle_hidden(self):
        self.show_hidden = not self.show_hidden
        label = "隐藏隐藏文件" if self.show_hidden else "显示隐藏文件"
        self.toggle_hidden_button.setText(label)
        self.refresh_visible_items()

    def refresh_visible_items(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            self.refresh_item(item)

    def refresh_item(self, item):
        """刷新指定节点的内容（用于展开刷新）"""
        path = item.data(0, Qt.UserRole)
        item.takeChildren()
        self.load_directory(path, parent=item)
        for i in range(item.childCount()):
            child = item.child(i)
            if child.isExpanded():
                self.refresh_item(child)

    def load_directory(self, path, parent=None):
        try:
            url = f"{self.base_url}/api/files/list"
            headers = {"Authorization": self.access_password}
            response = requests.get(url, params={"path": path}, headers=headers, verify=False)
            response.raise_for_status()
            data = response.json()

            for item in data:
                name = item["name"]
                file_path = item["path"]

                if not self.show_hidden and name.startswith("."):
                    continue

                tree_item = QTreeWidgetItem([name])
                tree_item.setData(0, Qt.UserRole, file_path)

                if item["type"] == "dir":
                    tree_item.addChild(QTreeWidgetItem(["加载中..."]))

                if parent:
                    parent.addChild(tree_item)
                else:
                    self.tree.addTopLevelItem(tree_item)

        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"❌ {e}")

    def expand_directory(self, item):
        if item.childCount() == 1 and item.child(0).text(0) == "加载中...":
            item.takeChildren()
            path = item.data(0, Qt.UserRole)
            self.load_directory(path, parent=item)

    def download_selected_file(self):
        items = self.tree.selectedItems()
        if not items:
            QMessageBox.warning(self, "未选择", "请选择一个或多个文件")
            return

        download_dir = self.config.get("download_dir", os.path.expanduser("~/Downloads/FlyDrop"))
        os.makedirs(download_dir, exist_ok=True)

        for item in items:
            file_path = item.data(0, Qt.UserRole)
            name = item.text(0)

            if item.childCount() > 0:
                QMessageBox.information(self, "跳过", f"{name} 是文件夹，无法下载。")
                continue

            save_path = os.path.join(download_dir, name)
            url = f"{self.base_url}/api/files/download"
            headers = {"Authorization": self.access_password}
            params = {"path": file_path}
            full_url = requests.Request("GET", url, params=params).prepare().url

            progress = QProgressDialog(f"{name} 下载中...", "取消", 0, 100, self)
            progress.setWindowTitle("文件下载")
            progress.setValue(0)
            progress.setCancelButton(None)

            thread = FileDownloadThread(full_url, headers, save_path)
            thread.progress.connect(lambda val: self.update_progress(progress, val))
            thread.finished.connect(lambda n: self.download_success(progress, n))
            thread.failed.connect(lambda n, err: self.download_fail(progress, n, err))
            thread.start()

    def update_progress(self, progress, val):
        progress.setValue(val)

    def download_success(self, progress, name):
        progress.setValue(progress.maximum())
        QMessageBox.information(self, "完成", f"{name} 下载完成。")
        progress.close()

    def download_fail(self, progress, name, err):
        QMessageBox.critical(self, "下载失败", f"{name} 下载失败：{err}")
        progress.close()

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.config = get_settings()
            self.base_url = self.config["base_url"]
            self.access_password = self.config["access_password"]
            self.refresh_root()

    def download_zip(self):
        items = self.tree.selectedItems()
        if not items:
            QMessageBox.warning(self, "未选择", "请选择要打包的文件或文件夹")
            return

        paths = []
        for item in items:
            file_path = item.data(0, Qt.UserRole)
            paths.append(file_path)

        # 请求后端生成压缩包
        url = f"{self.base_url}/api/files/zip"
        headers = {"Authorization": self.access_password}

        try:
            response = requests.get(
                url,
                params={"paths": ",".join(paths)},
                headers=headers,
                stream=True,
                verify=False
            )
            response.raise_for_status()

            # 获取后端返回的文件名
            zip_filename = response.headers.get("X-Zip-Filename", "default.zip")

            save_path = os.path.join(
                self.config.get("download_dir", os.path.expanduser("~/Downloads/FlyDrop")),
                zip_filename
            )

            total_size = int(response.headers.get("Content-Length", 0))
            progress = QProgressDialog("正在打包下载...", "取消", 0, total_size, self)
            progress.setWindowTitle("正在下载压缩包")
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)
            progress.setValue(0)

            downloaded = 0
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(8192):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    progress.setValue(downloaded)
                    QApplication.processEvents()

            progress.setValue(total_size)
            QMessageBox.information(self, "完成", f"打包文件已保存到:\n{save_path}")
            progress.close()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"打包下载失败: {e}")