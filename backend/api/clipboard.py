from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import pyperclip
import hashlib
import time
from backend.core.logger import log_access
from backend.core.security import verify_request

router = APIRouter()

clipboard_content = ""
clipboard_time = 0

class ClipboardData(BaseModel):
    content: str

def md5(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()

@router.get("/get")
def get_clipboard(request: Request):
    ip = request.client.host
    verify_request(request)  # 权限认证

    try:
        content = pyperclip.paste()
        log_access(ip, "CLIPBOARD_GET", "-", True)
        return {"content": content, "md5": md5(content)}
    except Exception as e:
        log_access(ip, "CLIPBOARD_GET", "-", False)
        raise HTTPException(500, detail=f"获取剪贴板失败: {e}")

@router.post("/set")
def set_clipboard(data: ClipboardData, request: Request):
    ip = request.client.host
    verify_request(request)  # 权限认证

    try:
        pyperclip.copy(data.content)
        log_access(ip, "CLIPBOARD_SET", "-", True)
        return {"status": "success"}
    except Exception as e:
        log_access(ip, "CLIPBOARD_SET", "-", False)
        raise HTTPException(500, detail=f"设置剪贴板失败: {e}")


@router.get("/ping")
def ping_clipboard(request: Request):
    verify_request(request)  # ✅ 添加认证

    global clipboard_content, clipboard_time
    return {
        "timestamp": clipboard_time,
        "md5": md5(clipboard_content)
    }