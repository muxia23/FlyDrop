# backend/api/files.py
from backend.core.logger import log_access
from fastapi import APIRouter, Request, Query, HTTPException, Response, Header
from backend.config import get_settings
from backend.core.security import verify_request
from fastapi.responses import FileResponse, StreamingResponse
import os
from typing import Optional

router = APIRouter()

@router.get("/list")
def list_files(request: Request, path: str = Query(default="")):
    verify_request(request)  # ✅ 验证访问权限
    ip = request.client.host

    settings = get_settings()
    root = settings["share_path"]
    abs_path = os.path.abspath(os.path.join(root, path))

    if not abs_path.startswith(os.path.abspath(root)):
        raise HTTPException(403, detail="非法路径")

    if not os.path.isdir(abs_path):
        raise HTTPException(404, detail="路径不存在")

    file_list = []
    try:
        for name in os.listdir(abs_path):
            full_path = os.path.join(abs_path, name)
            rel_path = os.path.relpath(full_path, root)
            if os.path.isdir(full_path):
                file_list.append({"type": "dir", "path": rel_path, "name": name})
            elif os.path.isfile(full_path):
                file_list.append({"type": "file", "path": rel_path, "name": name})
        log_access(ip, "LIST", path, True)
    except Exception as e:
        log_access(ip, "LIST", path, False)
        raise HTTPException(500, detail=str(e))

    return file_list

@router.get("/download")
def download_file(
    request: Request,
    path: str = Query(...),
    range: Optional[str] = Header(None)
):
    ip = request.client.host
    action = "DOWNLOAD"

    try:
        verify_request(request)  # ✅ 身份验证

        settings = get_settings()
        root = settings["share_path"]
        abs_path = os.path.abspath(os.path.join(root, path))

        if not abs_path.startswith(os.path.abspath(root)):
            log_access(ip, action, path, success=False)
            raise HTTPException(403, detail="非法路径")

        if not os.path.isfile(abs_path):
            log_access(ip, action, path, success=False)
            raise HTTPException(404, detail="文件不存在")

        file_size = os.path.getsize(abs_path)

        if not range:
            log_access(ip, action, path, success=True)
            return FileResponse(
                abs_path,
                filename=os.path.basename(abs_path),
                media_type="application/octet-stream"
            )

        # ✅ 解析 Range: bytes=xxx-yyy
        try:
            unit, range_str = range.strip().split("=")
            start_str, end_str = range_str.split("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
        except Exception:
            log_access(ip, action, path, success=False)
            raise HTTPException(416, detail="无效的 Range 格式")

        if start >= file_size:
            log_access(ip, action, path, success=False)
            raise HTTPException(416, detail="起始位置超过文件大小")

        chunk_size = end - start + 1

        def file_stream():
            with open(abs_path, "rb") as f:
                f.seek(start)
                yield f.read(chunk_size)

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Disposition": f'attachment; filename="{os.path.basename(abs_path)}"'
        }

        log_access(ip, action, path, success=True)
        return StreamingResponse(file_stream(), status_code=206, headers=headers, media_type="application/octet-stream")

    except Exception as e:
        # 如果上面忘了记录，这里兜底一次（避免漏掉）
        log_access(ip, action, path, success=False)
        raise e