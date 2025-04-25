# frontend/pages/settings_dialog.py

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from frontend.config import get_settings, save_settings

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙ 设置")
        self.setFixedSize(400, 300)

        self.config = get_settings()

        self.device_input = QLineEdit(self.config.get("device_name", ""))
        self.port_input = QLineEdit(str(self.config.get("port", 8010)))
        self.password_input = QLineEdit(self.config.get("access_password", ""))
        self.password_input.setEchoMode(QLineEdit.Password)

        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.save)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("设备名称"))
        layout.addWidget(self.device_input)
        layout.addWidget(QLabel("端口号"))
        layout.addWidget(self.port_input)
        layout.addWidget(QLabel("访问密码"))
        layout.addWidget(self.password_input)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

    def save(self):
        try:
            self.config["device_name"] = self.device_input.text()
            self.config["port"] = int(self.port_input.text())
            self.config["access_password"] = self.password_input.text()
            save_settings(self.config)
            QMessageBox.information(self, "成功", "设置已保存")
            self.accept()  # 关闭窗口
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存失败: {e}")