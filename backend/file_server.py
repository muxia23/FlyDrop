# backend/file_server.py

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import platform
import uvicorn

# 根目录设置
if platform.system() == "Windows":
    SHARED_ROOT = "C:\\"
else:
    SHARED_ROOT = "/"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/list")
def list_files(path: str = Query(default="")):
    abs_path = os.path.abspath(os.path.join(SHARED_ROOT, path))
    if not abs_path.startswith(os.path.abspath(SHARED_ROOT)):
        raise HTTPException(status_code=403, detail="非法路径（越界）")

    if not os.path.isdir(abs_path):
        raise HTTPException(status_code=404, detail="路径不存在")

    file_list = []
    try:
        for name in os.listdir(abs_path):
            full_path = os.path.join(abs_path, name)
            rel_path = os.path.relpath(full_path, SHARED_ROOT)
            if os.path.isdir(full_path):
                file_list.append({"type": "dir", "path": rel_path, "name": name})
            elif os.path.isfile(full_path):
                file_list.append({"type": "file", "path": rel_path, "name": name})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return file_list

@app.get("/download")
def download_file(path: str):
    abs_path = os.path.abspath(os.path.join(SHARED_ROOT, path))
    if not abs_path.startswith(os.path.abspath(SHARED_ROOT)):
        raise HTTPException(status_code=403, detail="非法路径（越界）")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(abs_path, filename=os.path.basename(path))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8010)