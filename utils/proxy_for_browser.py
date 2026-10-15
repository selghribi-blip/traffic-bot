# utils/proxy_for_browser.py
import os
import random
import logging

logger = logging.getLogger(__name__)


class BrowserProxyProvider:
    """يقرأ من manual_proxies.txt ويختار بروكسي Webshare المضمون للمتصفح."""

    def __init__(self, path='manual_proxies.txt'):
        self.path = path
        self.all_proxies = []
        self.webshare_proxies = []
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

                # Webshare detection: format is ip:port:user:pass (4 parts)
                parts = line.split(':')
                if len(parts) == 4 and '@' not in line and '://' not in line:
                    self.webshare_proxies.append(line)

        logger.info(
            f"BrowserProxyProvider: {len(self.all_proxies)} total, "
            f"{len(self.webshare_proxies)} Webshare"
        )

    def pick(self):
        """
        يختار بروكسي للمتصفح:
        1) Webshare أولًا (موثوق)
        2) SOCKS5 ثانيًا (إن لم يوجد Webshare)
        3) None (اتصال مباشر)
        """
        # 1) Webshare (ip:port:user:pass) - موثوق جدًا
        if self.webshare_proxies:
            chosen = random.choice(self.webshare_proxies)
            formatted = self._format_webshare(chosen)
            logger.info(f"Using Webshare proxy: {chosen.split(':')[0]}")
            return formatted

        # 2) SOCKS5 من الملف
        socks5 = [p for p in self.all_proxies if p.startswith('socks5')]
        if socks5:
            chosen = random.choice(socks5)
            logger.info(f"Using SOCKS5 proxy: {chosen}")
            return chosen

        # 3) لا شيء
        logger.warning("No proxy available - direct connection")
        return None

    @staticmethod
    def _format_webshare(raw):
        """ip:port:user:pass -> http://user:pass@ip:port"""
        parts = raw.split(':')
        if len(parts) == 4:
            ip, port, user, pwd = parts
            return f"http://{user}:{pwd}@{ip}:{port}"
        return raw
