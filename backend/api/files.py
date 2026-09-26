# backend/api/files.py
from zipfile import ZipFile, ZIP_DEFLATED
from backend.core.logger import log_access
from fastapi import APIRouter, Request, Query, HTTPException, Header
from backend.config import get_settings
from backend.core.security import verify_request, safe_join, to_rel
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask
import os
from typing import List, Optional
from urllib.parse import quote
import tempfile
import uuid

router = APIRouter()

CHUNK_SIZE = 1024 * 1024


def _content_disposition(filename: str) -> str:
    """同时兼容 ASCII 与中文文件名（RFC 5987）"""
    ascii_name = filename.encode("ascii", "replace").decode("ascii").replace("?", "_").replace('"', "_")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


@router.get("/zip")
def download_zip(request: Request, paths: List[str] = Query(...)):
    verify_request(request)
    ip = request.client.host

    root = get_settings()["share_path"]

    # 兼容旧客户端：paths=a,b,c 的写法（仅当只有一个参数且对应路径不存在时才按逗号拆分）
    if len(paths) == 1 and "," in paths[0] and not os.path.exists(safe_join(root, paths[0])):
        paths = paths[0].split(",")
    rel_paths = [p.strip() for p in paths if p.strip()]
    if not rel_paths:
        raise HTTPException(400, detail="缺少有效路径")

    abs_paths = [safe_join(root, p) for p in rel_paths]  # 越界路径直接 403
    abs_paths = [p for p in abs_paths if os.path.exists(p)]
    if not abs_paths:
        raise HTTPException(404, detail="文件不存在")

    # 压缩包内的相对路径以所选项目的公共父目录为基准
    if len(abs_paths) == 1:
        base_dir = os.path.dirname(abs_paths[0])
    else:
        base_dir = os.path.commonpath([os.path.dirname(p) for p in abs_paths])

    if len(abs_paths) == 1 and os.path.isdir(abs_paths[0]):
        zip_filename = f"{os.path.basename(abs_paths[0])}.zip"
    else:
        zip_filename = f"flydrop-{uuid.uuid4().hex[:8]}.zip"

    # 临时文件使用唯一名称，避免并发下载同名文件夹时互相覆盖
    fd, zip_path = tempfile.mkstemp(prefix="flydrop-", suffix=".zip")
    os.close(fd)

    try:
        with ZipFile(zip_path, "w", ZIP_DEFLATED) as zipf:
            for abs_path in abs_paths:
                if os.path.isdir(abs_path):
                    for foldername, subfolders, filenames in os.walk(abs_path):
                        # 保留空文件夹
                        if not subfolders and not filenames:
                            zipf.write(foldername, arcname=os.path.relpath(foldername, base_dir))
                        for filename in filenames:
                            full_path = os.path.join(foldername, filename)
                            if os.path.isfile(full_path):
                                zipf.write(full_path, arcname=os.path.relpath(full_path, base_dir))
                elif os.path.isfile(abs_path):
                    zipf.write(abs_path, arcname=os.path.relpath(abs_path, base_dir))
    except Exception as e:
        _remove(zip_path)
        log_access(ip, "ZIP", ",".join(rel_paths), False)
        raise HTTPException(500, detail=f"打包失败: {e}")

    log_access(ip, "ZIP", ",".join(rel_paths), True)
    # FileResponse 会带上 Content-Length，前端可以显示准确进度；下载完成后删除临时文件
    return FileResponse(
        zip_path,
        media_type="application/zip",
        headers={
            "Content-Disposition": _content_disposition(zip_filename),
            "X-Zip-Filename": quote(zip_filename),
        },
        background=BackgroundTask(_remove, zip_path),
    )


@router.get("/list")
def list_files(request: Request, path: str = Query(default="")):
    verify_request(request)  # ✅ 验证访问权限
    ip = request.client.host

    root = get_settings()["share_path"]
    abs_path = safe_join(root, path)

    if not os.path.isdir(abs_path):
        raise HTTPException(404, detail="路径不存在")

    file_list = []
    try:
        for name in sorted(os.listdir(abs_path), key=str.lower):
            full_path = os.path.join(abs_path, name)
            rel_path = to_rel(root, full_path)
            if os.path.isdir(full_path):
                file_list.append({"type": "dir", "path": rel_path, "name": name})
            elif os.path.isfile(full_path):
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    size = None
                file_list.append({"type": "file", "path": rel_path, "name": name, "size": size})
        log_access(ip, "LIST", path, True)
    except Exception as e:
        log_access(ip, "LIST", path, False)
        raise HTTPException(500, detail=str(e))

    # 文件夹排在前面
    file_list.sort(key=lambda x: x["type"] != "dir")
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

        root = get_settings()["share_path"]
        abs_path = safe_join(root, path)

        if not os.path.isfile(abs_path):
            raise HTTPException(404, detail="文件不存在")

        file_size = os.path.getsize(abs_path)
        filename = os.path.basename(abs_path)

        if not range:
            log_access(ip, action, path, success=True)
            return FileResponse(
                abs_path,
                media_type="application/octet-stream",
                headers={"Content-Disposition": _content_disposition(filename), "Accept-Ranges": "bytes"},
            )

        # ✅ 解析 Range: bytes=xxx-yyy
        try:
            unit, range_str = range.strip().split("=", 1)
            if unit.strip() != "bytes":
                raise ValueError
            start_str, end_str = range_str.split(",")[0].split("-")
            if start_str:
                start = int(start_str)
                end = int(end_str) if end_str else file_size - 1
            else:  # bytes=-500 表示最后 500 字节
                start = max(0, file_size - int(end_str))
                end = file_size - 1
        except Exception:
            raise HTTPException(416, detail="无效的 Range 格式")

        end = min(end, file_size - 1)
        if start >= file_size or start > end:
            raise HTTPException(416, detail="起始位置超过文件大小")

        length = end - start + 1

        def file_stream():
            with open(abs_path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Disposition": _content_disposition(filename),
        }

        log_access(ip, action, path, success=True)
        return StreamingResponse(file_stream(), status_code=206, headers=headers, media_type="application/octet-stream")

    except Exception:
        log_access(ip, action, path, success=False)
        raise
