# frontend/pages/file_download.py

# --- 基础和必要的导入 ---
import sys
import traceback # 用于打印更详细的错误信息

# --- PySide6 界面和核心库 ---
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QFileDialog, QMessageBox, QLabel, QComboBox,
    QProgressDialog, QApplication, QInputDialog
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QThread

# --- 项目内部模块 (根据你的结构调整) ---
from frontend.config import get_settings         # 获取前端配置
from frontend.pages.settings_dialog import SettingsDialog # 设置对话框
from frontend.threads.downloader import FileDownloadThread  # 前端的下载线程

# --- 标准库和第三方库 ---
import requests # 用于向后端发送 HTTP 请求
import os       # 用于处理本地文件路径
import uuid     # 用于生成唯一ID

class FileDownloadPage(QWidget):
    """
    文件浏览和下载页面 (Frontend Page)。
    负责与用户交互，向后端请求数据，并展示结果。
    """
    def __init__(self):
        """初始化页面组件和状态"""
        super().__init__()

        # -- 配置和状态变量 --
        self.config = get_settings()
        self.base_url = self.config.get("base_url", "https://localhost:8010") # 后端 API 的根地址
        self.access_password = self.config.get("access_password", "") # 访问后端的密码
        self.show_hidden = False  # 是否显示隐藏文件
        self.manual_devices = {}  # 手动添加的设备 {名称: URL}
        self.active_download_threads = [] # 正在运行的下载线程列表

        # -- 界面控件 --
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["文件名"])
        self.tree.itemExpanded.connect(self.expand_directory) # 展开文件夹时加载内容
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection) # 允许多选

        # 定时器，用于定期向后端请求设备列表
        self.device_refresh_timer = QTimer(self)
        self.device_refresh_timer.timeout.connect(self.fetch_devices)
        self.device_refresh_timer.start(5000) # 5秒刷新一次

        # 按钮
        self.toggle_hidden_button = QPushButton("显示隐藏文件")
        self.refresh_button = QPushButton("刷新")
        self.download_button = QPushButton("下载")
        self.settings_button = QPushButton("⚙ 设置")
        self.zip_button = QPushButton("打包下载")

        # 连接按钮信号
        self.zip_button.clicked.connect(self.download_zip)
        self.toggle_hidden_button.clicked.connect(self.toggle_hidden)
        self.refresh_button.clicked.connect(self.refresh_root)
        self.download_button.clicked.connect(self.download_selected_files)
        self.settings_button.clicked.connect(self.open_settings_dialog)

        # 设备选择
        self.device_selector = QComboBox()
        self.device_selector.currentIndexChanged.connect(self.change_device) # 选择变化时切换后端地址
        self.add_device_button = QPushButton("添加设备")
        self.add_device_button.clicked.connect(self.add_manual_device)

        # -- 布局 --
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("设备："))
        top_layout.addWidget(self.device_selector)
        top_layout.addWidget(self.add_device_button)
        top_layout.addStretch()
        top_layout.addWidget(self.toggle_hidden_button)
        top_layout.addWidget(self.refresh_button)
        top_layout.addWidget(self.download_button)
        top_layout.addWidget(self.zip_button)
        top_layout.addWidget(self.settings_button)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.tree)

        # -- 初始化数据 --
        self.update_devices({}) # 初始化设备列表
        self.fetch_devices()    # 首次尝试获取设备

    def change_device(self, index):
        """切换当前连接的后端设备"""
        ip_url = self.device_selector.itemData(index)
        if ip_url and ip_url != self.base_url:
            self.base_url = ip_url # 更新目标后端 URL
            self.refresh_root()    # 刷新文件列表

    def refresh_root(self):
        """刷新文件树的根目录"""
        if not self.base_url: return # 必须有后端地址
        self.tree.clear()
        self.load_directory("") # 请求根目录 ""

    def toggle_hidden(self):
        """切换是否显示隐藏文件"""
        self.show_hidden = not self.show_hidden
        self.toggle_hidden_button.setText("隐藏隐藏文件" if self.show_hidden else "显示隐藏文件")
        self.refresh_root() # 重新加载列表以应用更改

    def load_directory(self, path, parent=None):
        """向后端请求指定路径的文件列表，并在UI上显示"""
        if not self.base_url: return
        try:
            # --- 前端职责：向后端 API 发送请求 ---
            url = f"{self.base_url}/api/files/list"
            headers = {"Authorization": self.access_password}
            response = requests.get(url, params={"path": path}, headers=headers, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json() # 后端返回的文件/文件夹列表

            # --- 前端职责：处理响应并在 UI 上展示 ---
            container = parent if parent else self.tree
            if parent: parent.takeChildren() # 清除旧的占位符

            for item_data in data:
                name = item_data["name"]
                file_path = item_data["path"]
                if not self.show_hidden and name.startswith("."): continue

                tree_item = QTreeWidgetItem([name])
                tree_item.setData(0, Qt.UserRole, file_path) # 存储后端提供的路径

                if item_data["type"] == "dir":
                    tree_item.addChild(QTreeWidgetItem([""])) # 添加占位符显示展开图标
                    tree_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)

                if parent: parent.addChild(tree_item)
                else: self.tree.addTopLevelItem(tree_item)

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "加载失败", f"无法从 {self.base_url} 加载列表。\n错误: {e}")
            # 在界面上显示错误提示
            err_node = QTreeWidgetItem([f"加载失败: {type(e).__name__}"])
            if parent: parent.addChild(err_node)
            else: self.tree.addTopLevelItem(err_node)
        except Exception as e:
            print(f"[Load Directory] Unexpected Error: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "加载失败", f"处理列表时发生未知错误: {e}")
            err_node = QTreeWidgetItem([f"加载失败: 未知错误"])
            if parent: parent.addChild(err_node)
            else: self.tree.addTopLevelItem(err_node)


    def expand_directory(self, item: QTreeWidgetItem):
        """用户展开文件夹节点时，向后端请求该文件夹的内容"""
        # 检查是否是首次展开（通过占位符判断）
        is_placeholder = item.childCount() == 1 and item.child(0).text(0) == ""
        if item.childIndicatorPolicy() == QTreeWidgetItem.ShowIndicator and is_placeholder:
            path = item.data(0, Qt.UserRole) # 获取要加载的后端路径
            item.takeChildren() # 移除占位符
            item.addChild(QTreeWidgetItem(["加载中..."])) # 显示加载提示
            QApplication.processEvents()
            self.load_directory(path, parent=item) # 请求后端加载

    def download_selected_files(self):
        """用户点击“下载”按钮，下载选中的文件"""
        items = self.tree.selectedItems()
        if not items:
            QMessageBox.warning(self, "未选择", "请选择文件进行下载")
            return

        download_dir = self.config.get("download_dir", os.path.expanduser("~/Downloads/FlyDrop"))
        try:
            os.makedirs(download_dir, exist_ok=True) # 确保本地下载目录存在
        except OSError as e:
             QMessageBox.critical(self, "错误", f"无法创建本地下载目录：{download_dir}\n{e}")
             return

        if not self.base_url:
             QMessageBox.warning(self, "错误", "未选择有效的设备 URL")
             return

        for item in items:
            file_path = item.data(0, Qt.UserRole) # 这是后端需要的相对路径
            name = item.text(0) # 文件名，用于本地保存

            if item.childIndicatorPolicy() == QTreeWidgetItem.ShowIndicator:
                # print(f"[Download] Skipping directory: {name}")
                continue # 跳过文件夹

            save_path = os.path.join(download_dir, name) # 本地完整保存路径

            # --- 前端职责：构建对后端下载接口的请求 ---
            url = f"{self.base_url}/api/files/download"
            headers = {"Authorization": self.access_password}
            params = {"path": file_path} # 将后端路径作为参数
            try:
                req = requests.Request("GET", url, params=params)
                prepared_req = req.prepare()
                full_url = prepared_req.url # 最终请求的 URL
            except Exception as e:
                 QMessageBox.critical(self, "URL错误", f"构建下载链接时出错:\n{e}")
                 continue

            # --- 前端职责：显示下载进度 ---
            progress = QProgressDialog(f"下载 '{name}'...", "取消", 0, 100, self)
            progress.setWindowTitle("文件下载")
            progress.setMinimumDuration(500)
            progress.setCancelButton(None) # 禁用取消
            progress.setAutoClose(False)
            progress.setValue(0)

            # --- 前端职责：创建后台线程处理下载 IO ---
            try:
                # FileDownloadThread 负责请求后端、接收数据、写入本地文件
                thread = FileDownloadThread(full_url, headers, save_path)
            except Exception as e:
                print(f"[Download] Error creating thread: {e}")
                traceback.print_exc()
                QMessageBox.critical(self, "错误", f"无法创建下载线程: {e}")
                progress.close()
                continue

            self.active_download_threads.append(thread)

            # --- 前端职责：连接线程信号更新 UI ---
            try:
                thread.progress.connect(lambda val, p=progress: self.update_progress(p, val), Qt.QueuedConnection)
                # 假设 finished/failed 信号会传递线程实例用于清理
                thread.finished.connect(lambda name_sig, t=thread, p=progress: self.download_finished(p, name_sig, t), Qt.QueuedConnection)
                thread.failed.connect(lambda name_sig, err_sig, t=thread, p=progress: self.download_failed(p, name_sig, err_sig, t), Qt.QueuedConnection)
            except Exception as e:
                 print(f"[Download] Error connecting signals: {e}")
                 QMessageBox.critical(self, "信号错误", f"连接线程信号时出错: {e}")
                 if thread in self.active_download_threads: self.active_download_threads.remove(thread)
                 progress.close()
                 continue

            # --- 前端职责：启动后台线程 ---
            try:
                thread.start()
                progress.show()
            except Exception as e:
                print(f"[Download] Error starting thread: {e}")
                traceback.print_exc()
                QMessageBox.critical(self, "启动错误", f"启动下载线程时出错: {e}")
                if thread in self.active_download_threads: self.active_download_threads.remove(thread)
                progress.close()

    def update_progress(self, progress_dialog: QProgressDialog, value: int):
        """槽：更新进度条"""
        if progress_dialog and progress_dialog.isVisible():
            progress_dialog.setValue(value)

    def download_finished(self, progress_dialog: QProgressDialog, name: str, thread_instance: FileDownloadThread):
        """槽：下载成功"""
        if progress_dialog and progress_dialog.isVisible():
            progress_dialog.setValue(progress_dialog.maximum())
            progress_dialog.setLabelText(f"'{name}' 下载完成!")
            progress_dialog.setCancelButtonText("关闭")
            progress_dialog.setAutoClose(True)
        else:
            QMessageBox.information(self, "下载完成", f"'{name}' 已成功下载。")
        self.cleanup_thread(thread_instance) # 从活动列表移除

    def download_failed(self, progress_dialog: QProgressDialog, name: str, error_message: str, thread_instance: FileDownloadThread):
        """槽：下载失败"""
        if progress_dialog and progress_dialog.isVisible():
            progress_dialog.setLabelText(f"'{name}' 下载失败!")
            progress_dialog.setCancelButtonText("关闭")
            progress_dialog.setAutoClose(True)
        QMessageBox.critical(self, "下载失败", f"下载 '{name}' 时发生错误:\n{error_message}")
        self.cleanup_thread(thread_instance) # 从活动列表移除

    def cleanup_thread(self, thread_instance: FileDownloadThread):
        """从活动线程列表中安全移除线程实例"""
        if thread_instance in self.active_download_threads:
            self.active_download_threads.remove(thread_instance)

    def open_settings_dialog(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.config = get_settings() # 重新加载前端配置
            self.base_url = self.config.get("base_url", "https://localhost:8010")
            self.access_password = self.config.get("access_password", "")
            self.update_devices({}) # 更新设备列表（可能改变本机 URL）

    def download_zip(self):
        """用户点击“打包下载”按钮"""
        items = self.tree.selectedItems()
        if not items:
            QMessageBox.warning(self, "未选择", "请选择要打包下载的文件或文件夹")
            return
        if not self.base_url:
             QMessageBox.warning(self, "错误", "未选择有效的设备 URL")
             return

        paths = [item.data(0, Qt.UserRole) for item in items] # 获取选中的后端路径

        # --- 前端职责：向后端打包接口发送请求 ---
        url = f"{self.base_url}/api/files/zip"
        headers = {"Authorization": self.access_password}
        params = {"paths": ",".join(paths)}
        progress = None

        try:
            # 请求后端生成并开始传输 Zip 流
            response = requests.get(url, params=params, headers=headers, stream=True, verify=False, timeout=(10, 600))
            response.raise_for_status()

            # --- 前端职责：获取文件名，准备本地保存 ---
            content_disposition = response.headers.get("Content-Disposition", "")
            zip_filename = response.headers.get("X-Zip-Filename") # 优先使用后端指定的头
            if not zip_filename and "filename=" in content_disposition:
                 filename_part = content_disposition.split("filename=")[1]
                 if filename_part: zip_filename = filename_part.strip('" ')
            if not zip_filename: zip_filename = f"flydrop_{uuid.uuid4().hex[:6]}.zip"

            download_dir = self.config.get("download_dir", os.path.expanduser("~/Downloads/FlyDrop"))
            os.makedirs(download_dir, exist_ok=True)
            save_path = os.path.join(download_dir, zip_filename) # 本地保存路径

            # --- 前端职责：显示打包下载进度 ---
            total_size = int(response.headers.get("Content-Length", 0))
            progress = QProgressDialog(f"下载 '{zip_filename}'...", "取消", 0, max(1, total_size), self)
            progress.setWindowTitle("打包下载")
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)
            progress.setValue(0)
            progress.show()
            QApplication.processEvents()

            # --- 前端职责：接收后端数据流并写入本地文件 ---
            downloaded = 0
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                       f.write(chunk) # 写入本地文件
                       downloaded += len(chunk)
                       if total_size > 0: progress.setValue(downloaded)
                       else: progress.setLabelText(f"下载中... ({downloaded / (1024*1024):.2f} MB)")
                    QApplication.processEvents() # 保持 UI 响应

            if total_size > 0: progress.setValue(total_size)
            else: progress.setValue(progress.maximum())
            QMessageBox.information(self, "下载完成", f"打包文件 '{zip_filename}' 已保存到:\n{save_path}")

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "打包失败", f"请求打包文件失败: {e}")
        except Exception as e:
            print(f"[Download Zip] Unexpected Error: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "打包失败", f"处理打包下载时发生未知错误: {e}")
        finally:
            if progress: progress.close() # 确保关闭进度条


    def fetch_devices(self):
        """向后端请求已发现的设备列表"""
        # 通常设备发现服务在本机运行
        discovery_url = f"https://localhost:{self.config.get('port', 8010)}/api/devices"
        try:
            # --- 前端职责：向后端设备接口发送请求 ---
            headers = {"Authorization": self.access_password}
            response = requests.get(discovery_url, headers=headers, verify=False, timeout=3)
            response.raise_for_status()
            data = response.json() # 后端返回的设备列表

            # --- 前端职责：处理响应数据 ---
            if not isinstance(data, list): return # 忽略无效数据
            discovered_devices = {}
            for dev in data:
                if isinstance(dev, dict) and "name" in dev and "ip" in dev:
                     port = self.config.get('port', 8010)
                     discovered_devices[dev["name"]] = f"https://{dev['ip']}:{port}"

            self.update_devices(discovered_devices) # 更新 UI 列表

        except requests.exceptions.RequestException:
            pass # 后台刷新失败，静默处理
        except Exception as e:
            print(f"[Fetch Devices] Error: {e}") # 打印其他错误到控制台
            pass

    def update_devices(self, discovered_devices: dict):
        """更新设备下拉框的选项"""
        current_selection_url = self.device_selector.currentData()
        all_devices = {}
        local_name = "本机"
        local_url = self.config.get("base_url", "https://localhost:8010")
        all_devices[local_name] = local_url # 添加本机

        for name, url in discovered_devices.items(): # 添加发现的设备
             if name != local_name and name not in self.manual_devices:
                 all_devices[name] = url

        all_devices.update(self.manual_devices) # 添加手动设备

        # --- 前端职责：更新下拉框 UI ---
        self.device_selector.blockSignals(True)
        self.device_selector.clear()
        new_index_to_select = -1
        idx = 0
        for name, url in all_devices.items():
            display_ip = url.replace('https://', '').split(':')[0]
            display_name = f"{name} ({display_ip})"
            self.device_selector.addItem(display_name, url) # 显示名称，关联 URL 数据
            if url == current_selection_url: new_index_to_select = idx
            idx += 1

        if new_index_to_select == -1 and local_name in all_devices: # 默认选本机
             try: new_index_to_select = list(all_devices.keys()).index(local_name)
             except ValueError: new_index_to_select = 0
        if new_index_to_select < 0 or new_index_to_select >= self.device_selector.count():
             new_index_to_select = 0 if self.device_selector.count() > 0 else -1

        self.device_selector.blockSignals(False)

        if new_index_to_select != -1:
             self.device_selector.setCurrentIndex(new_index_to_select)
             # 如果设置索引后，URL 没变，但树是空的，需要手动刷新
             new_selected_url = self.device_selector.itemData(new_index_to_select)
             if self.base_url == new_selected_url and not self.tree.topLevelItemCount():
                  self.refresh_root()
             # 如果 base_url 尚未初始化，则进行初始化
             elif not self.base_url:
                   self.base_url = new_selected_url
                   self.refresh_root()

    def add_manual_device(self):
        """弹出对话框，让用户手动输入并添加设备"""
        text, ok = QInputDialog.getText(self, "添加设备", "请输入 IP:端口（例如 192.168.1.100:8010）:")
        if ok and text:
            try:
                if ':' not in text: raise ValueError("格式错误，缺少端口号")
                ip, port_str = text.strip().split(":", 1)
                port = int(port_str)
                url = f"https://{ip}:{port}"
                name = f"手动: {ip}"
                self.manual_devices[name] = url # 存储到手动列表
                self.update_devices({}) # 更新设备下拉框
                new_index = self.device_selector.findData(url) # 找到新添加的
                if new_index != -1: self.device_selector.setCurrentIndex(new_index) # 选中它
            except ValueError as e:
                QMessageBox.warning(self, "格式错误", f"输入无效: {e}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"添加设备时出错: {e}")

    def closeEvent(self, event):
        """窗口关闭时停止定时器和可能的下载"""
        self.device_refresh_timer.stop()
        for thread in self.active_download_threads[:]:
            try:
                if hasattr(thread, 'stop') and callable(thread.stop):
                    thread.stop() # 请求线程停止
            except Exception as e:
                print(f"Error stopping thread {thread}: {e}")
        super().closeEvent(event)

# --- 用于独立测试此文件的入口 ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    # --- 提供测试设置 ---
    def get_settings_for_test():
         # !! 替换成你的密码 !!
         return {"base_url": "https://localhost:8010", "access_password": "YOUR_PASSWORD", "port": 8010, "download_dir": os.path.expanduser("~/Downloads/FlyDropTest")}
    import frontend.config
    frontend.config.get_settings = get_settings_for_test
    # --- 确保线程类存在 (或用占位符) ---
    try: from frontend.threads.downloader import FileDownloadThread
    except ImportError:
        class FileDownloadThread(QThread): # 最小占位符
            progress=Signal(int); finished=Signal(str); failed=Signal(str,str)
            def __init__(self,u,h,s,p=None): super().__init__(p);self.name=os.path.basename(s)
            def run(self): print("Placeholder run"); self.progress.emit(100); self.finished.emit(self.name)
            def stop(self): pass
    # --- 显示窗口 ---
    main_window = QWidget()
    main_window.setWindowTitle("File Download Test")
    layout = QVBoxLayout(main_window)
    download_page = FileDownloadPage()
    layout.addWidget(download_page)
    main_window.resize(800, 600); main_window.show()
    sys.exit(app.exec())