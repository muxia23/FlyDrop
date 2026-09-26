# frontend/threads/request_worker.py
# 在后台线程执行一次 HTTP 请求，避免阻塞界面

from PySide6.QtCore import QThread, Signal
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # 自签名证书


def error_message(e: Exception) -> str:
    """把 requests 异常转成对用户友好的文字（优先使用后端返回的 detail）"""
    if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
        try:
            return f"{e.response.status_code}: {e.response.json().get('detail', e.response.text)}"
        except ValueError:
            return f"{e.response.status_code}: {e.response.text}"
    if isinstance(e, requests.exceptions.ConnectionError):
        return "无法连接到设备，请确认对方后端已启动且网络可达"
    if isinstance(e, requests.exceptions.Timeout):
        return "连接超时"
    return str(e)


class RequestWorker(QThread):
    succeeded = Signal(object)  # 解析后的 JSON
    failed = Signal(str)

    def __init__(self, method, url, headers=None, params=None, json=None, timeout=5, parent=None):
        super().__init__(parent)
        self.method = method
        self.url = url
        self.headers = headers or {}
        self.params = params
        self.json = json
        self.timeout = timeout

    def run(self):
        try:
            r = requests.request(self.method, self.url, headers=self.headers, params=self.params,
                                 json=self.json, verify=False, timeout=self.timeout)
            r.raise_for_status()
            self.succeeded.emit(r.json())
        except Exception as e:
            self.failed.emit(error_message(e))
