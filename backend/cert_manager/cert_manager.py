import datetime
import ipaddress
import os
import socket

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def cert_is_valid(cert_path: str, valid_days=7) -> bool:
    """证书存在且剩余有效期不少于 valid_days 天"""
    if not os.path.exists(cert_path):
        return False
    try:
        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        remaining = (cert.not_valid_after - _utcnow()).days
        return remaining >= valid_days
    except Exception as e:
        print(f"⚠️ 证书读取失败: {e}")
        return False


def ensure_https_cert(cert_path="cert.pem", key_path="key.pem"):
    """
    生成自签名证书。直接使用 cryptography 库，不再依赖系统的 openssl 命令，
    这样 Windows 上也可以正常生成证书。
    """
    if cert_is_valid(cert_path) and os.path.exists(key_path):
        return  # 已存在有效证书

    ip = get_local_ip()
    print(f"🔐 正在为 {ip} 生成新的 HTTPS 自签名证书...")

    try:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ip)])
        san = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
        if ip != "127.0.0.1":
            san.append(x509.IPAddress(ipaddress.ip_address(ip)))

        now = _utcnow()
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .sign(key, hashes.SHA256())
        )

        for path in (cert_path, key_path):
            d = os.path.dirname(os.path.abspath(path))
            os.makedirs(d, exist_ok=True)

        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            ))
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        print(f"✅ 证书生成成功: {cert_path} (有效期 365 天)")
    except Exception as e:
        print("❌ 生成证书失败:", e)
        raise SystemExit(1)
