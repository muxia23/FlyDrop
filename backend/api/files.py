# backend/api/files.py
from zipfile import ZipFile, ZIP_DEFLATED
from backend.core.logger import log_access
from fastapi import APIRouter, Request, Query, HTTPException, Response, Header
from backend.config import get_settings
from backend.core.security import verify_request
from fastapi.responses import FileResponse, StreamingResponse
import os
from typing import Optional
import tempfile
import uuid
from io import BytesIO

router = APIRouter()

@router.get("/zip")
def download_zip(request: Request, paths: str = Query(...)):
    verify_request(request)

    # 获取设置
    settings = get_settings()
    root = settings["share_path"]

    # 路径处理
    rel_paths = [p.strip() for p in paths.split(",") if p.strip()]
    if not rel_paths:
        raise HTTPException(400, detail="缺少有效路径")

    # 找出最外层路径（假设根目录为最外层）
    common_root = os.path.commonpath([os.path.join(root, p) for p in rel_paths])

    # 判断是否为单个文件夹
    if len(rel_paths) == 1 and os.path.isdir(os.path.join(root, rel_paths[0])):
        zip_filename = f"{os.path.basename(rel_paths[0])}.zip"
    else:
        zip_filename = f"flydrop-{uuid.uuid4().hex[:8]}.zip"

    # 创建临时文件保存 zip
    temp_dir = tempfile.gettempdir()
    zip_path = os.path.join(temp_dir, zip_filename)

    try:
        with ZipFile(zip_path, "w", ZIP_DEFLATED) as zipf:
            for rel_path in rel_paths:
                abs_path = os.path.abspath(os.path.join(root, rel_path))

                # 处理路径越界的情况
                if not abs_path.startswith(common_root):
                    continue  # 忽略越界路径

                # 如果是文件夹，递归添加其中的文件
                if os.path.isdir(abs_path):
                    for foldername, subfolders, filenames in os.walk(abs_path):
                        for filename in filenames:
                            full_path = os.path.join(foldername, filename)
                            arcname = os.path.relpath(full_path, common_root)
                            zipf.write(full_path, arcname=arcname)

                # 如果是文件，直接添加
                elif os.path.isfile(abs_path):
                    arcname = os.path.relpath(abs_path, common_root)
                    zipf.write(abs_path, arcname=arcname)

        # 以流的形式返回 zip 文件并删除
        def file_stream():
            with open(zip_path, "rb") as f:
                yield from f
            os.remove(zip_path)  # 下载完后自动删除

        return StreamingResponse(
            file_stream(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={zip_filename}",
                "X-Zip-Filename": zip_filename  # 返回 zip 文件名
            }
        )

    except Exception as e:
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise HTTPException(500, detail=f"打包失败: {e}")

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