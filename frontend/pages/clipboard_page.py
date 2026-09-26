# frontend/pages/clipboard_page.py
# 剪贴板共享页面：手动获取 / 发送剪贴板，或开启自动双向同步

import hashlib
import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QPlainTextEdit,
    QCheckBox, QApplication, QMessageBox
)
from PySide6.QtCore import QTimer

from frontend.config import get_settings, save_settings
from frontend.threads.request_worker import RequestWorker


def md5(text: str) -> str:
    return hashlib.md5((text or "").encode("utf-8")).hexdigest()


class ClipboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_settings()
        self.target_url = ""
        self.target_name = ""
        self.workers = set()          # 保持对后台线程的引用，防止被回收
        self.last_synced_md5 = None   # 最近一次双方已同步的内容，用于防止来回同步
        self.remote_md5 = None        # 对方剪贴板的最新 md5
        self.ping_in_flight = False

        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_local_clipboard_changed)

        # -- 控件 --
        self.target_label = QLabel("当前设备：未选择")
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("这里显示对方剪贴板的内容，也可以直接输入文字发送给对方")

        self.fetch_button = QPushButton("⬇ 获取对方剪贴板")
        self.copy_button = QPushButton("📋 复制到本机剪贴板")
        self.send_local_button = QPushButton("⬆ 发送本机剪贴板")
        self.send_text_button = QPushButton("⬆ 发送文本框内容")
        self.auto_sync_check = QCheckBox("自动同步")
        self.auto_sync_check.setToolTip("双向同步：本机复制的内容会自动发送给对方，对方复制的内容会自动写入本机剪贴板")
        self.auto_sync_check.setChecked(bool(self.config.get("clipboard_auto_sync", False)))

        self.fetch_button.clicked.connect(self.fetch_remote)
        self.copy_button.clicked.connect(self.copy_to_local)
        self.send_local_button.clicked.connect(lambda: self.send_to_remote(self.clipboard.text()))
        self.send_text_button.clicked.connect(lambda: self.send_to_remote(self.text_edit.toPlainText()))
        self.auto_sync_check.toggled.connect(self.on_auto_sync_toggled)

        # -- 布局 --
        top = QHBoxLayout()
        top.addWidget(self.target_label)
        top.addStretch()
        top.addWidget(self.auto_sync_check)

        buttons = QHBoxLayout()
        for b in (self.fetch_button, self.copy_button, self.send_local_button, self.send_text_button):
            buttons.addWidget(b)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.text_edit)
        layout.addLayout(buttons)
        layout.addWidget(self.status_label)

        # -- 自动同步定时器 --
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.poll_remote)
        self.apply_config()

    # ---------- 外部调用 ----------
    def set_target(self, url: str, name: str):
        """文件页切换设备时调用"""
        if url == self.target_url:
            return
        self.target_url = url or ""
        self.target_name = name or ""
        self.target_label.setText(f"当前设备：{name or '未选择'}")
        self.last_synced_md5 = None
        self.remote_md5 = None

    def reload_config(self):
        """设置保存后调用"""
        self.config = get_settings()
        self.auto_sync_check.blockSignals(True)
        self.auto_sync_check.setChecked(bool(self.config.get("clipboard_auto_sync", False)))
        self.auto_sync_check.blockSignals(False)
        self.apply_config()

    def apply_config(self):
        interval = max(1, int(self.config.get("clipboard_interval", 2))) * 1000
        self.sync_timer.setInterval(interval)
        if self.auto_sync_check.isChecked():
            self.sync_timer.start()
        else:
            self.sync_timer.stop()

    # ---------- 工具 ----------
    def headers(self):
        return {"Authorization": self.config.get("access_password", "")}

    def is_local_target(self):
        """目标就是本机时，无需同步"""
        local = self.config.get("base_url", "").rstrip("/")
        return self.target_url.rstrip("/") == local

    def set_status(self, text):
        self.status_label.setText(f"[{time.strftime('%H:%M:%S')}] {text}")

    def request(self, method, path, on_success, on_fail=None, json=None):
        if not self.target_url:
            self.set_status("未选择设备")
            return None
        worker = RequestWorker(method, f"{self.target_url}/api/clipboard/{path}",
                               headers=self.headers(), json=json, timeout=5)
        worker.succeeded.connect(on_success)
        worker.failed.connect(on_fail or (lambda msg: self.set_status(f"❌ {msg}")))
        worker.finished.connect(lambda w=worker: self.workers.discard(w))
        self.workers.add(worker)
        worker.start()
        return worker

    # ---------- 手动操作 ----------
    def fetch_remote(self):
        def done(data):
            content = data.get("content", "")
            self.text_edit.setPlainText(content)
            self.remote_md5 = data.get("md5")
            self.set_status(f"✅ 已获取 {self.target_name} 的剪贴板（{len(content)} 字符）")
        self.set_status("正在获取…")
        self.request("GET", "get", done)

    def copy_to_local(self):
        text = self.text_edit.toPlainText()
        self.last_synced_md5 = md5(text)
        self.clipboard.setText(text)
        self.set_status("✅ 已复制到本机剪贴板")

    def send_to_remote(self, text):
        if not text:
            QMessageBox.information(self, "提示", "没有可以发送的文本内容")
            return
        self._push(text, manual=True)

    def _push(self, text, manual=False):
        digest = md5(text)

        def done(_):
            self.last_synced_md5 = digest
            self.remote_md5 = digest
            self.set_status(f"✅ 已发送到 {self.target_name}（{len(text)} 字符）")

        def fail(msg):
            self.set_status(f"❌ 发送失败：{msg}")
            if manual:
                QMessageBox.warning(self, "发送失败", msg)

        self.request("POST", "set", done, fail, json={"content": text})

    # ---------- 自动同步 ----------
    def on_auto_sync_toggled(self, checked):
        self.config["clipboard_auto_sync"] = checked
        cfg = get_settings()
        cfg["clipboard_auto_sync"] = checked
        save_settings(cfg)
        self.last_synced_md5 = md5(self.clipboard.text())
        self.apply_config()
        self.set_status("自动同步已开启" if checked else "自动同步已关闭")

    def on_local_clipboard_changed(self):
        """本机剪贴板变化 → 推送给对方"""
        if not self.auto_sync_check.isChecked() or self.is_local_target():
            return
        text = self.clipboard.text()
        if not text:
            return  # 仅同步文本
        digest = md5(text)
        if digest in (self.last_synced_md5, self.remote_md5):
            return  # 内容刚从对方同步过来，避免回传
        self.last_synced_md5 = digest
        self._push(text)

    def poll_remote(self):
        """定时检查对方剪贴板是否变化 → 拉取并写入本机"""
        if self.ping_in_flight or not self.target_url or self.is_local_target():
            return

        def got_ping(state):
            self.ping_in_flight = False
            digest = state.get("md5")
            if not digest or digest == self.remote_md5:
                return
            self.remote_md5 = digest
            if digest in (self.last_synced_md5, md5(self.clipboard.text())):
                return
            self.request("GET", "get", got_content)

        def got_content(data):
            content = data.get("content", "")
            digest = md5(content)
            self.remote_md5 = digest
            self.last_synced_md5 = digest
            self.text_edit.setPlainText(content)
            self.clipboard.setText(content)
            self.set_status(f"🔄 已从 {self.target_name} 同步剪贴板（{len(content)} 字符）")

        def fail(msg):
            self.ping_in_flight = False
            self.set_status(f"❌ 同步失败：{msg}")

        self.ping_in_flight = True
        if self.request("GET", "ping", got_ping, fail) is None:
            self.ping_in_flight = False

    def shutdown(self):
        self.sync_timer.stop()
        for w in list(self.workers):
            w.wait(2000)
