#!/bin/bash
# setup-proxy.sh
# ============================================================
# تحويل Ubuntu VPS إلى بروكسي SOCKS5 احترافي
# ============================================================

set -e  # أوقف عند أي خطأ

# ---------- الإعدادات ----------
PROXY_PORT=1080
PROXY_USER="proxyuser"
PROXY_PASS="$(openssl rand -base64 16 | tr -d '=+/' | cut -c1-16)"  # كلمة مرور عشوائية
ALLOWED_IPS="0.0.0.0/0"  # ← اسمح للجميع (يمكنك تحديد GitHub IPs لاحقًا)

echo "🚀 بدء إعداد VPS كبروكسي SOCKS5..."
echo ""

# ---------- 1) تحديث النظام ----------
echo "📦 [1/6] تحديث النظام..."
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# ---------- 2) تثبيت Dante ----------
echo "📦 [2/6] تثبيت Dante Server..."
sudo apt-get install -y -qq dante-server curl net-tools

# ---------- 3) إنشاء مستخدم البروكسي ----------
echo "👤 [3/6] إنشاء مستخدم البروكسي..."
if ! id "$PROXY_USER" &>/dev/null; then
    sudo useradd -r -s /bin/false "$PROXY_USER"
fi
echo "$PROXY_USER:$PROXY_PASS" | sudo chpasswd
echo "✅ المستخدم: $PROXY_USER"

# ---------- 4) تكوين Dante ----------
echo "⚙️  [4/6] تكوين Dante..."

# اكتشف الواجهة الشبكية تلقائيًا
EXT_IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
echo "🌐 الواجهة الخارجية: $EXT_IFACE"

sudo tee /etc/danted.conf > /dev/null <<EOF
# ============================================================
# Dante SOCKS5 Server Configuration
# ============================================================

logoutput: /var/log/danted.log

# ---------- الواجهات ----------
internal: 0.0.0.0 port = ${PROXY_PORT}
external: ${EXT_IFACE}

# ---------- المصادقة ----------
socksmethod: username
clientmethod: none

# ---------- المستخدمون ----------
user.privileged: root
user.notprivileged: nobody

# ---------- المنع/السماح ----------
client pass {
    from: ${ALLOWED_IPS} to: 0.0.0.0/0
    log: connect disconnect error
}

socks pass {
    from: 0.0.0.0/0 to: 0.0.0.0/0
    command: bind connect udpassociate
    log: error
    socksmethod: username
}

socks block {
    from: 0.0.0.0/0 to: 0.0.0.0/0
    log: error
}
EOF

echo "✅ تم إنشاء /etc/danted.conf"

# ---------- 5) تكوين الجدار الناري ----------
echo "🔥 [5/6] تكوين UFW..."
sudo ufw allow 22/tcp
sudo ufw allow ${PROXY_PORT}/tcp
sudo ufw --force enable
echo "✅ UFW مفعل"

# ---------- 6) تشغيل Dante ----------
echo "▶️  [6/6] تشغيل Dante..."
sudo systemctl enable danted
sudo systemctl restart danted
sleep 2

# ---------- التحقق ----------
if sudo systemctl is-active --quiet danted; then
    echo "✅ Dante يعمل"
else
    echo "❌ Dante فشل"
    sudo journalctl -u danted -n 20 --no-pager
    exit 1
fi

# ---------- عرض المعلومات ----------
PUBLIC_IP=$(curl -s ifconfig.me)

echo ""
echo "════════════════════════════════════════════════════════════"
echo "🎉 تم إعداد البروكسي بنجاح!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📋 معلومات الاتصال:"
echo ""
echo "   Type:     SOCKS5"
echo "   Host:     ${PUBLIC_IP}"
echo "   Port:     ${PROXY_PORT}"
echo "   Username: ${PROXY_USER}"
echo "   Password: ${PROXY_PASS}"
echo ""
echo "🔗 صيغ الاتصال:"
echo ""
echo "   SOCKS5 (DNS محلي):"
echo "     socks5://${PROXY_USER}:${PROXY_PASS}@${PUBLIC_IP}:${PROXY_PORT}"
echo ""
echo "   SOCKS5h (DNS على البروكسي):"
echo "     socks5h://${PROXY_USER}:${PROXY_PASS}@${PUBLIC_IP}:${PROXY_PORT}"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""
echo "⚠️  احفظ كلمة المرور في مكان آمن!"
echo ""
