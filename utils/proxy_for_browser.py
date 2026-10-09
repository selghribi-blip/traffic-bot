# utils/proxy_for_browser.py
"""
جسر بين ProxyRotator و BrowserStack/Local.
يستخرج بروكسيًا صالحًا من قائمة مشتركة.
"""
import os
import random
import requests


class BrowserProxyProvider:
    """يجلب بروكسيًا صالحًا لاستخدامه في BrowserStack أو Local Chrome."""

    DEFAULT_SOURCES = [
        'https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/checked_proxies/http.txt',
        'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt',
        'https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/http/data.txt',
    ]

    def __init__(self, sources=None):
        self.sources = sources or self.DEFAULT_SOURCES
        self.proxies = []

    def load(self):
        seen = set()
        for url in self.sources:
            try:
                r = requests.get(url, timeout=15)
                for line in r.text.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#') and ':' in line:
                        seen.add(line)
            except Exception:
                continue
        self.proxies = list(seen)
        return self.proxies

    def pick(self):
        if not self.proxies:
            self.load()
        if not self.proxies:
            return None
        raw = random.choice(self.proxies)
        return self._format(raw)

    @staticmethod
    def _format(raw: str) -> str:
        if '://' in raw:
            return raw
        parts = raw.split(':')
        if len(parts) == 2:
            return f"http://{parts[0]}:{parts[1]}"
        if len(parts) == 4:
            ip, port, user, pwd = parts
            return f"http://{user}:{pwd}@{ip}:{port}"
        if '@' in raw:
            return f"http://{raw}"
        return f"http://{raw}"
