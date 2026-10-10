#!/usr/bin/env python3
"""
deploy_proxy_to_github.py
=========================
ينشئ مستخدمًا على VPS، يشفّر بيانات البروكسي، ويرفعها إلى GitHub Secrets.

المتطلبات:
    pip install requests PyNaCl

الاستخدام:
    python deploy_proxy_to_github.py
"""

import os
import sys
import base64
import json
import secrets
import string
import subprocess
import requests
from nacl import encoding, public

# ============================================================
# الإعدادات — عدّلها
# ============================================================
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')  # Personal Access Token
GITHUB_REPO = "selghribi-blip/traffic-bot"     # owner/repo
SECRET_NAME = "VPS_PROXY"
VPS_IP = os.environ.get('VPS_IP', '')
VPS_SSH_USER = os.environ.get('VPS_SSH_USER', 'ubuntu')
PROXY_PORT = 1080
PROXY_USER = "proxyuser"


def generate_password(length=20):
    """يولّد كلمة مرور قوية."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def setup_vps_user(vps_ip, ssh_user, proxy_user, proxy_pass):
    """ينشئ مستخدم البروكسي على VPS عبر SSH."""
    print(f"🔧 إعداد المستخدم '{proxy_user}' على VPS...")
    script = f"""
    sudo useradd -r -s /bin/false {proxy_user} 2>/dev/null || true
    echo '{proxy_user}:{proxy_pass}' | sudo chpasswd
    sudo systemctl restart danted
    echo "✅ User ready"
    """
    result = subprocess.run(
        ['ssh', f'{ssh_user}@{vps_ip}', 'bash -s'],
        input=script, text=True, capture_output=True,
    )
    if result.returncode != 0:
        print(f"❌ فشل: {result.stderr}")
        return False
    print(result.stdout.strip())
    return True


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """يشفّر القيمة باستخدام LibSodium SealedBox."""
    public_key = public.PublicKey(
        base64.b64decode(public_key_b64),
        encoding.RawEncoder,
    )
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode('utf-8'))
    return base64.b64encode(encrypted).decode('utf-8')


def get_repo_public_key():
    """يجلب المفتاح العام للمستودع."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/public-key"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


def update_github_secret(secret_name, encrypted_value, key_id):
    """يرفع السرّ إلى GitHub."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/{secret_name}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "encrypted_value": encrypted_value,
        "key_id": key_id,
    }
    r = requests.put(url, headers=headers, json=payload, timeout=15)
    if r.status_code in (201, 204):
        return True
    print(f"❌ فشل الرفع: {r.status_code} — {r.text}")
    return False


def main():
    # التحقق من الإعدادات
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN غير مضبوط")
        sys.exit(1)
    if not VPS_IP:
        print("❌ VPS_IP غير مضبوط")
        sys.exit(1)

    # 1) توليد كلمة مرور
    proxy_pass = generate_password()
    print(f"🔑 كلمة المرور الجديدة: {proxy_pass}")

    # 2) إعداد VPS (اختياري — علّق إذا أردت استخدام بيانات موجودة)
    if os.environ.get('SETUP_VPS', 'false').lower() == 'true':
        if not setup_vps_user(VPS_IP, VPS_SSH_USER, PROXY_USER, proxy_pass):
            sys.exit(1)

    # 3) بناء سلسلة البروكسي
    proxy_string = f"socks5h://{PROXY_USER}:{proxy_pass}@{VPS_IP}:{PROXY_PORT}"
    print(f"🌐 البروكسي: {proxy_string}")

    # 4) تشفير ورفع
    print("🔐 جلب المفتاح العام من GitHub...")
    key_data = get_repo_public_key()
    print(f"   Key ID: {key_data['key_id']}")

    print("🔒 تشفير القيمة...")
    encrypted = encrypt_secret(key_data['key'], proxy_string)

    print(f"📤 رفع إلى GitHub Secrets باسم '{SECRET_NAME}'...")
    if update_github_secret(SECRET_NAME, encrypted, key_data['key_id']):
        print(f"\n✅ تم رفع البروكسي بنجاح!")
        print(f"   Secret: {SECRET_NAME}")
        print(f"   Repo:   {GITHUB_REPO}")
    else:
        print("\n❌ فشل الرفع")
        sys.exit(1)


if __name__ == "__main__":
    main()
