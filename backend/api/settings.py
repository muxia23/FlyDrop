# backend/api/settings.py
# 设置接口：仅限本机访问，供前端设置页面读取 / 修改后端配置

import os
from typing import List, Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from backend.config import get_settings, save_settings
from backend.core.security import require_local

router = APIRouter()

# 修改后需要重启后端才能生效的字段
RESTART_FIELDS = ("port", "https_enabled", "discovery_port")

# 由 main.py 在启动时注入，用于热更新广播设备名
discovery_service = None


class SettingsUpdate(BaseModel):
    device_name: Optional[str] = None
    share_path: Optional[str] = None
    port: Optional[int] = None
    discovery_port: Optional[int] = None
    access_password: Optional[str] = None
    allowed_ips: Optional[List[str]] = None
    https_enabled: Optional[bool] = None


@router.get("")
def read_settings(request: Request):
    require_local(request)
    return get_settings()


@router.post("")
def update_settings(data: SettingsUpdate, request: Request):
    require_local(request)
    config = get_settings()
    changes = {k: v for k, v in data.model_dump().items() if v is not None}

    if "device_name" in changes:
        changes["device_name"] = changes["device_name"].strip()
        if not changes["device_name"]:
            raise HTTPException(400, detail="设备名称不能为空")

    if "share_path" in changes:
        path = os.path.abspath(os.path.expanduser(changes["share_path"].strip()))
        if not os.path.isdir(path):
            raise HTTPException(400, detail=f"共享目录不存在: {path}")
        changes["share_path"] = path

    for key in ("port", "discovery_port"):
        if key in changes and not (1 <= changes[key] <= 65535):
            raise HTTPException(400, detail=f"{key} 必须在 1-65535 之间")

    if "allowed_ips" in changes:
        ips = [ip.strip() for ip in changes["allowed_ips"] if ip.strip()]
        # 始终保留本机，避免把自己锁在门外
        for local in ("127.0.0.1", "::1"):
            if local not in ips:
                ips.append(local)
        changes["allowed_ips"] = ips

    need_restart = [k for k in RESTART_FIELDS if k in changes and changes[k] != config.get(k)]

    config.update(changes)
    save_settings(config)

    # 设备名热更新
    if discovery_service is not None and "device_name" in changes:
        discovery_service.restart_broadcast(changes["device_name"])

    return {"status": "success", "restart_required": need_restart, "settings": config}
