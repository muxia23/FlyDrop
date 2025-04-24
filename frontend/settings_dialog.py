# frontend/settings_dialog.py
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from backend.config import load_config, save_config

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.config = load_config()

        layout = QVBoxLayout(self)

        self.name_input = QLineEdit(self.config.get("device_name", "未命名设备"))
        layout.addWidget(QLabel("设备名称："))
        layout.addWidget(self.name_input)

        self.password_input = QLineEdit(self.config.get("access_password", ""))
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(QLabel("访问密码："))
        layout.addWidget(self.password_input)

        save_button = QPushButton("保存")
        save_button.clicked.connect(self.save)
        layout.addWidget(save_button)

    def save(self):
        self.config["device_name"] = self.name_input.text().strip()
        self.config["access_password"] = self.password_input.text().strip()
        save_config(self.config)
        QMessageBox.information(self, "保存成功", "设置已保存，重启或切换设备后生效。")
        self.accept()