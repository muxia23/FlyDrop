from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import pyperclip
import hashlib
import threading
import time
from backend.core.logger import log_access
from backend.core.security import verify_request

router = APIRouter()

# 记录剪贴板最近一次变化，供 /ping 快速判断是否需要同步
_state = {"md5": "", "timestamp": 0.0}
_lock = threading.Lock()


class ClipboardData(BaseModel):
    content: str


def md5(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _read_clipboard():
    content = pyperclip.paste() or ""
    digest = md5(content)
    with _lock:
        if digest != _state["md5"]:
            _state["md5"] = digest
            _state["timestamp"] = time.time()
        return content, dict(_state)


@router.get("/get")
def get_clipboard(request: Request):
    ip = request.client.host
    verify_request(request)  # 权限认证

    try:
        content, state = _read_clipboard()
        log_access(ip, "CLIPBOARD_GET", "-", True)
        return {"content": content, "md5": state["md5"], "timestamp": state["timestamp"]}
    except Exception as e:
        log_access(ip, "CLIPBOARD_GET", "-", False)
        raise HTTPException(500, detail=f"获取剪贴板失败: {e}")


@router.post("/set")
def set_clipboard(data: ClipboardData, request: Request):
    ip = request.client.host
    verify_request(request)  # 权限认证

    try:
        pyperclip.copy(data.content)
        with _lock:
            _state["md5"] = md5(data.content)
            _state["timestamp"] = time.time()
        log_access(ip, "CLIPBOARD_SET", "-", True)
        return {"status": "success", "md5": _state["md5"]}
    except Exception as e:
        log_access(ip, "CLIPBOARD_SET", "-", False)
        raise HTTPException(500, detail=f"设置剪贴板失败: {e}")


@router.get("/ping")
def ping_clipboard(request: Request):
    """返回剪贴板内容的 md5 与最后变化时间，客户端据此决定是否拉取完整内容"""
    verify_request(request)
    try:
        _, state = _read_clipboard()
        return state
    except Exception as e:
        raise HTTPException(500, detail=f"读取剪贴板失败: {e}")
