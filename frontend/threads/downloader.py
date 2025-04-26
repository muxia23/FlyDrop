# frontend/threads/downloader.py

from PySide6.QtCore import QThread, Signal
import requests
import os

class InterruptedError(Exception):
    """用于标记下载中断的异常"""
    pass

class FileDownloadThread(QThread):
    progress = Signal(int)
    finished = Signal(str)  # 文件名
    failed = Signal(str, str)  # 文件名, 错误信息

    def __init__(self, url, headers, save_path, parent=None):
        super().__init__(parent)
        self.url = url
        self.headers = headers
        self.save_path = save_path
        self.name = os.path.basename(save_path)
        self._is_running = True

    def run(self):
        try:
            print(f"开始下载: {self.name}")
            response = requests.get(self.url, headers=self.headers, stream=True, verify=False, timeout=(10, 300))
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            os.makedirs(os.path.dirname(self.save_path), exist_ok=True)

            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(8192):
                    if not self._is_running:
                        print(f"中断下载: {self.name}")
                        if os.path.exists(self.save_path):
                            os.remove(self.save_path)
                        raise InterruptedError("Download manually stopped")
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int(100 * downloaded / total_size)
                            self.progress.emit(percent)

            self.progress.emit(100)
            print(f"下载完成: {self.name}")
            self.finished.emit(self.name)

        except InterruptedError as ie:
            self.failed.emit(self.name, str(ie))

        except requests.exceptions.RequestException as e:
            err = f"网络错误: {e}"
            print(f"下载失败 [{self.name}]: {err}")
            self.failed.emit(self.name, err)
            try:
                if os.path.exists(self.save_path):
                    os.remove(self.save_path)
            except Exception:
                pass

        except Exception as e:
            print(f"下载失败 [{self.name}]: {e}")
            self.failed.emit(self.name, str(e))
            try:
                if os.path.exists(self.save_path):
                    os.remove(self.save_path)
            except Exception:
                pass

        finally:
            self._is_running = False

    def stop(self):
        """请求中止线程"""
        self._is_running = False