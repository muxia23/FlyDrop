# frontend/pages/settings_dialog.py

import requests
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QTabWidget, QWidget, QFileDialog, QCheckBox, QSpinBox, QPlainTextEdit,
    QDialogButtonBox
)
from frontend.config import get_settings, save_settings
from frontend.threads.request_worker import error_message


def _path_row(line_edit: QLineEdit, parent) -> QHBoxLayout:
    """输入框 + “浏览”按钮"""
    row = QHBoxLayout()
    row.addWidget(line_edit)
    btn = QPushButton("浏览…")
    btn.clicked.connect(lambda: _browse(line_edit, parent))
    row.addWidget(btn)
    return row


def _browse(line_edit: QLineEdit, parent):
    path = QFileDialog.getExistingDirectory(parent, "选择文件夹", line_edit.text())
    if path:
        line_edit.setText(path)


class SettingsDialog(QDialog):
    """
    设置页面：
      - 客户端设置：保存在 frontend/config.json
      - 本机共享设置：通过本机后端 /api/settings 接口读取和保存（backend/config.json）
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙ 设置")
        self.setMinimumSize(520, 460)

        self.config = get_settings()
        self.backend_config = None

        tabs = QTabWidget()
        tabs.addTab(self._build_client_tab(), "客户端")
        tabs.addTab(self._build_backend_tab(), "本机共享")

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("保存")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

        self.load_backend_settings()

    # ---------- 客户端 ----------
    def _build_client_tab(self):
        w = QWidget()
        form = QFormLayout(w)

        self.download_dir_input = QLineEdit(self.config.get("download_dir", ""))
        self.remote_password_input = QLineEdit(self.config.get("access_password", ""))
        self.remote_password_input.setEchoMode(QLineEdit.Password)
        self.remote_password_input.setPlaceholderText("对方设置了访问密码时填写")
        self.base_url_input = QLineEdit(self.config.get("base_url", "https://localhost:8010"))
        self.auto_sync_check = QCheckBox("自动同步剪贴板")
        self.auto_sync_check.setChecked(bool(self.config.get("clipboard_auto_sync", False)))
        self.interval_input = QSpinBox()
        self.interval_input.setRange(1, 60)
        self.interval_input.setSuffix(" 秒")
        self.interval_input.setValue(int(self.config.get("clipboard_interval", 2)))

        form.addRow("下载目录", _path_row(self.download_dir_input, self))
        form.addRow("访问其他设备的密码", self.remote_password_input)
        form.addRow("本机后端地址", self.base_url_input)
        form.addRow("剪贴板", self.auto_sync_check)
        form.addRow("同步间隔", self.interval_input)
        return w

    # ---------- 本机共享（后端） ----------
    def _build_backend_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        self.backend_status = QLabel("正在连接本机后端…")
        self.backend_status.setWordWrap(True)
        layout.addWidget(self.backend_status)

        self.backend_form = QWidget()
        form = QFormLayout(self.backend_form)
        self.device_input = QLineEdit()
        self.share_path_input = QLineEdit()
        self.local_password_input = QLineEdit()
        self.local_password_input.setEchoMode(QLineEdit.Password)
        self.local_password_input.setPlaceholderText("留空表示不需要密码")
        self.allowed_ips_input = QPlainTextEdit()
        self.allowed_ips_input.setPlaceholderText("每行一个 IP，白名单内的设备无需密码")
        self.allowed_ips_input.setFixedHeight(70)
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.discovery_port_input = QSpinBox()
        self.discovery_port_input.setRange(1, 65535)
        self.https_check = QCheckBox("启用 HTTPS（自签名证书）")

        form.addRow("设备名称", self.device_input)
        form.addRow("共享目录", _path_row(self.share_path_input, self))
        form.addRow("访问密码", self.local_password_input)
        form.addRow("IP 白名单", self.allowed_ips_input)
        form.addRow("服务端口 *", self.port_input)
        form.addRow("广播端口 *", self.discovery_port_input)
        form.addRow("", self.https_check)
        form.addRow(QLabel("* 修改后需重启后端生效"))
        layout.addWidget(self.backend_form)
        layout.addStretch()

        self.backend_form.setEnabled(False)
        return w

    def _backend_url(self):
        return self.config.get("base_url", "https://localhost:8010").rstrip("/") + "/api/settings"

    def load_backend_settings(self):
        try:
            r = requests.get(self._backend_url(), verify=False, timeout=3)
            r.raise_for_status()
            cfg = r.json()
        except Exception as e:
            self.backend_status.setText(f"⚠️ 无法连接本机后端（{error_message(e)}）。\n请先启动 backend/main.py，"
                                        f"并确认“客户端 → 本机后端地址”正确。")
            return

        self.backend_config = cfg
        self.device_input.setText(cfg.get("device_name", ""))
        self.share_path_input.setText(cfg.get("share_path", ""))
        self.local_password_input.setText(cfg.get("access_password", ""))
        self.allowed_ips_input.setPlainText("\n".join(cfg.get("allowed_ips", [])))
        self.port_input.setValue(int(cfg.get("port", 8010)))
        self.discovery_port_input.setValue(int(cfg.get("discovery_port", 17257)))
        self.https_check.setChecked(bool(cfg.get("https_enabled", True)))
        self.backend_status.setText("✅ 已连接本机后端，修改将写入后端配置。")
        self.backend_form.setEnabled(True)

    # ---------- 保存 ----------
    def save(self):
        messages = []

        # 1. 后端设置
        if self.backend_config is not None:
            payload = {
                "device_name": self.device_input.text().strip(),
                "share_path": self.share_path_input.text().strip(),
                "access_password": self.local_password_input.text(),
                "allowed_ips": [ip.strip() for ip in self.allowed_ips_input.toPlainText().splitlines() if ip.strip()],
                "port": self.port_input.value(),
                "discovery_port": self.discovery_port_input.value(),
                "https_enabled": self.https_check.isChecked(),
            }
            try:
                r = requests.post(self._backend_url(), json=payload, verify=False, timeout=5)
                r.raise_for_status()
                result = r.json()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"保存本机共享设置失败:\n{error_message(e)}")
                return
            if result.get("restart_required"):
                messages.append("端口 / HTTPS 设置需要重启后端后生效。")

        # 2. 客户端设置
        try:
            self.config["download_dir"] = self.download_dir_input.text().strip() or self.config["download_dir"]
            self.config["access_password"] = self.remote_password_input.text()
            self.config["base_url"] = self.base_url_input.text().strip().rstrip("/")
            self.config["clipboard_auto_sync"] = self.auto_sync_check.isChecked()
            self.config["clipboard_interval"] = self.interval_input.value()
            if self.backend_config is not None:
                self.config["port"] = self.port_input.value()
                self.config["discovery_port"] = self.discovery_port_input.value()
                # 本机后端端口 / 协议改变后，本机地址随之改变（重启后端后生效）
                if (self.port_input.value() != int(self.backend_config.get("port", 8010))
                        or self.https_check.isChecked() != bool(self.backend_config.get("https_enabled", True))):
                    scheme = "https" if self.https_check.isChecked() else "http"
                    self.config["base_url"] = f"{scheme}://localhost:{self.port_input.value()}"
            save_settings(self.config)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存失败: {e}")
            return

        QMessageBox.information(self, "成功", "设置已保存\n" + "\n".join(messages))
        self.accept()
