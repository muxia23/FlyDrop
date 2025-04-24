import os
import subprocess
import socket
import datetime
from OpenSSL import crypto

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def cert_is_valid(cert_path: str, valid_days=7) -> bool:
    if not os.path.exists(cert_path):
        return False
    try:
        with open(cert_path, "rb") as f:
            cert_data = f.read()
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_data)
        expires = datetime.datetime.strptime(cert.get_notAfter().decode('ascii'), "%Y%m%d%H%M%SZ")
        remaining = (expires - datetime.datetime.utcnow()).days
        return remaining >= valid_days
    except Exception as e:
        print(f"⚠️ 证书读取失败: {e}")
        return False

def ensure_https_cert(cert_path="cert.pem", key_path="key.pem"):
    if cert_is_valid(cert_path) and cert_is_valid(cert_path,7):
        return  # 已存在有效证书

    ip = get_local_ip()
    print(f"🔐 正在为 {ip} 生成新的 HTTPS 自签名证书...")

    subj = f"/CN={ip}"
    cmd = [
        "openssl", "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", key_path,
        "-out", cert_path,
        "-days", "365", "-nodes",
        "-subj", subj
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ 证书生成成功: {cert_path} (有效期 365 天)")
    except Exception as e:
        print("❌ 生成证书失败:", e)
        exit(1)