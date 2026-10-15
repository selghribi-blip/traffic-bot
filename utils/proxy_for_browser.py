# utils/proxy_for_browser.py
import os
import random
import logging

logger = logging.getLogger(__name__)


class BrowserProxyProvider:
    """
    يقرأ من manual_proxies.txt ويعطي الأولوية القصوى للبروكسي السكني (HTTP).
    """

    def __init__(self, path='manual_proxies.txt'):
        self.path = path
        self.all_proxies = []
        self.residential_proxies = []
        self.webshare_proxies = []  # أبقيتها كاحتياطي
        self._load()

    def _load(self):
        if not os.path.isfile(self.path):
            logger.warning(f"Proxy file not found: {self.path}")
            return

        with open(self.path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                self.all_proxies.append(line)

                # 1. تحديد البروكسي السكني (الذي يحتوي على بروتوكول http و @)
                if line.startswith('http://') and '@' in line:
                    self.residential_proxies.append(line)
                    continue

                # 2. تحديد بروكسي Webshare (ip:port:user:pass)
                parts = line.split(':')
                if len(parts) == 4 and '@' not in line and '://' not in line:
                    self.webshare_proxies.append(line)

        logger.info(
            f"BrowserProxyProvider: {len(self.all_proxies)} total, "
            f"{len(self.residential_proxies)} Residential, "
            f"{len(self.webshare_proxies)} Webshare"
        )

    def pick(self):
        """
        يختار بروكسي للمتصفح بالأولوية:
        1) البروكسي السكني (الأفضل لـ Adsterra/Monetag)
        2) بروكسي Webshare (احتياطي)
        3) اتصال مباشر (إذا لم يوجد أي شيء)
        """
        # 1) الأولوية القصوى: البروكسي السكني
        if self.residential_proxies:
            chosen = random.choice(self.residential_proxies)
            logger.info(f"✅ Using Residential proxy: {chosen.split('@')[-1]}")
            return chosen  # الصيغة جاهزة للاستخدام

        # 2) الاحتياطي: بروكسي Webshare
        if self.webshare_proxies:
            chosen = random.choice(self.webshare_proxies)
            formatted = self._format_webshare(chosen)
            logger.info(f"⚠️ Using Webshare proxy (fallback): {chosen.split(':')[0]}")
            return formatted

        # 3) لا شيء
        logger.warning("⚠️ No proxy available - direct connection")
        return None

    @staticmethod
    def _format_webshare(raw):
        """ip:port:user:pass -> http://user:pass@ip:port"""
        parts = raw.split(':')
        if len(parts) == 4:
            ip, port, user, pwd = parts
            return f"http://{user}:{pwd}@{ip}:{port}"
        return raw
