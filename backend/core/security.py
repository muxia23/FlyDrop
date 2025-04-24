from fastapi import Request, HTTPException
from backend.config import get_settings

def verify_request(request: Request):
    config = get_settings()
    client_ip = request.client.host
    allowed_ips = config.get("allowed_ips", [])
    access_password = config.get("access_password", "")
    auth = request.headers.get("Authorization")

    if client_ip in allowed_ips:
        # ✅ 白名单 IP 直接放行
        return

    if access_password and auth != access_password:
        raise HTTPException(403, detail=f"未授权访问（IP {client_ip} 不在白名单，且密码错误）")