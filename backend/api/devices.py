# backend/api/devices.py

from fastapi import APIRouter, Request, HTTPException
from backend.core.device_manager import device_manager

router = APIRouter()

@router.get("/devices")
def list_devices(request: Request):
    client_ip = request.client.host
    if client_ip not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=403, detail="该接口仅限本机访问")
    return device_manager.get_devices()