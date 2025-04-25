# frontend/threads/downloader.py

from PySide6.QtCore import QThread, Signal
import requests
import os

class FileDownloadThread(QThread):
    progress = Signal(int)  # 当前进度
    finished = Signal(str)  # 下载完成，返回文件名
    failed = Signal(str, str)  # 下载失败，文件名 + 错误信息

    def __init__(self, url, headers, save_path, chunk_size=8192):
        super().__init__()
        self.url = url
        self.headers = headers
        self.save_path = save_path
        self.chunk_size = chunk_size
        self._filename = os.path.basename(save_path)

    def run(self):
        try:
            with requests.get(self.url, headers=self.headers, stream=True, verify=False) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length", 0))
                downloaded = 0

                with open(self.save_path, "wb") as f:
                    for chunk in r.iter_content(self.chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            self.progress.emit(downloaded)

            self.finished.emit(self._filename)
        except Exception as e:
            self.failed.emit(self._filename, str(e))