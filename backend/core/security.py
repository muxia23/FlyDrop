import os
from fastapi import Request, HTTPException
from backend.config import get_settings

LOCAL_IPS = ("127.0.0.1", "::1", "localhost")


def verify_request(request: Request):
    config = get_settings()
    client_ip = request.client.host
    allowed_ips = config.get("allowed_ips", [])
    access_password = config.get("access_password", "")
    auth = request.headers.get("Authorization")

    if client_ip in LOCAL_IPS or client_ip in allowed_ips:
        # ✅ 本机和白名单 IP 直接放行
        return

    if access_password and auth != access_password:
        raise HTTPException(403, detail=f"未授权访问（IP {client_ip} 不在白名单，且密码错误）")


def require_local(request: Request):
    """仅允许本机访问的接口（设备列表、设置等）"""
    if request.client.host not in LOCAL_IPS:
        raise HTTPException(status_code=403, detail="该接口仅限本机访问")


def safe_join(root: str, rel_path: str) -> str:
    """把客户端传来的相对路径拼接到共享根目录下，并阻止越界访问"""
    root = os.path.realpath(root)
    # 兼容不同系统的分隔符（Windows 客户端 <-> mac/Linux 服务端）
    rel_path = (rel_path or "").replace("\\", "/").lstrip("/")
    abs_path = os.path.realpath(os.path.join(root, *[p for p in rel_path.split("/") if p]))
    try:
        inside = os.path.commonpath([root, abs_path]) == root
    except ValueError:  # Windows 下不同盘符
        inside = False
    if not inside:
        raise HTTPException(403, detail="非法路径")
    return abs_path


def to_rel(root: str, abs_path: str) -> str:
    """返回统一使用 / 分隔的相对路径"""
    return os.path.relpath(abs_path, os.path.realpath(root)).replace(os.sep, "/")
