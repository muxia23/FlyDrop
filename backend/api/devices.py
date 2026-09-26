# backend/api/devices.py

from fastapi import APIRouter, Request
from backend.core.device_manager import device_manager
from backend.core.security import require_local

router = APIRouter()


@router.get("/devices")
def list_devices(request: Request):
    require_local(request)
    return device_manager.get_devices()
