# middlewares/proxy_rotator.py
"""
Proxy Rotator — Final Optimized
================================
- لا Health-check (يعتمد على الحذف الديناميكي).
- لا يستخدم SOCKS4 لـ HTTPS (يسبب timeout).
- يعامل Google CAPTCHA كفشل فوري.
- يجلب HTTP من مصادر متعددة كـ fallback.
"""
import os
import re
import random
import logging
import requests
from urllib.parse import urlparse

from scrapy import signals
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


class FreeProxyRotatorMiddleware:
    HTTP_SOURCES = [
        'https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/http/data.txt',
        'https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/checked_proxies/http.txt',
        'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt',
    ]

    MAX_FAILURES = 2
    MAX_SWAPS_PER_REQUEST = 5
    PROXY_TIMEOUT = 25

    GOOGLE_CAPTCHA_PATTERNS = [
        'google.com/sorry',
        '/sorry/index',
        'consent.google.com',
    ]

    def __init__(self, proxies):
        self.pools = {'socks4': [], 'socks5': [], 'http': []}
        for p in proxies:
            scheme = self._scheme(p)
            if scheme in ('socks4', 'socks4a'):
                self.pools['socks4'].append(p)
            elif scheme in ('socks5', 'socks5h'):
                self.pools['socks5'].append(p)
            else:
                self.pools['http'].append(p)

        self.failures = {}
        self.used_by_pool = {k: 0 for k in self.pools}
        self.dead_removed = {k: 0 for k in self.pools}
        self.captcha_hits = 0

        logger.info(
            f"📊 Pools → SOCKS4: {len(self.pools['socks4'])} | "
            f"SOCKS5: {len(self.pools['socks5'])} | HTTP: {len(self.pools['http'])}"
        )

    @classmethod
    def from_crawler(cls, crawler):
        if os.environ.get('DISABLE_PROXIES', 'false').lower() == 'true':
            logger.warning("⛔ Proxies DISABLED via env")
            raise NotConfigured("Disabled by env")

        proxies = set()

        # ملف يدوي
        manual_file = os.environ.get('MANUAL_PROXY_FILE', 'manual_proxies.txt')
        if os.path.isfile(manual_file):
            with open(manual_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        proxies.add(line)
            logger.info(f"📁 Manual proxies: {len(proxies)}")

        # env
        manual_env = os.environ.get('MANUAL_PROXIES', '').strip()
        if manual_env:
            for p in re.split(r'[,\n]', manual_env):
                p = p.strip()
                if p:
                    proxies.add(p)

        # مصادر HTTP
        if os.environ.get('FETCH_REMOTE_PROXIES', 'true').lower() == 'true':
            for url in cls.HTTP_SOURCES:
                try:
                    r = requests.get(url, timeout=15)
                    r.raise_for_status()
                    count = 0
                    for line in r.text.splitlines():
                        line = line.strip()
                        if line and not line.startswith('#') and ':' in line:
                            proxies.add(line)
                            count += 1
                    logger.info(f"🌐 {url.split('/')[4]}: {count} HTTP")
                except Exception as e:
                    logger.warning(f"⚠️ {url}: {e}")

        if not proxies:
            raise NotConfigured("No proxies available")

        proxies = list(proxies)
        random.shuffle(proxies)

        # لا Health-check (يعتمد على الحذف الديناميكي)
        mw = cls(proxies)
        crawler.signals.connect(mw.spider_closed, signal=signals.spider_closed)
        return mw

    @staticmethod
    def _scheme(raw: str) -> str:
        raw = raw.strip().lower()
        if '://' in raw:
            return raw.split('://', 1)[0]
        return 'http'

    @staticmethod
    def _format_proxy(raw: str) -> str:
        raw = raw.strip()
        if not raw:
            return None
        if '://' in raw:
            return raw
        parts = raw.split(':')
        if len(parts) == 2:
            return f"http://{parts[0]}:{parts[1]}"
        if len(parts) == 4:
            ip, port, user, pwd = parts
            return f"http://{user}:{pwd}@{ip}:{port}"
        if '@' in raw and len(parts) == 3:
            creds, host = raw.rsplit('@', 1)
            return f"http://{creds}@{host}"
        return f"http://{raw}"

    def _is_google_captcha(self, response):
        url = response.url.lower()
        return any(p in url for p in self.GOOGLE_CAPTCHA_PATTERNS)

    def _pick_pool_for_url(self, url: str):
        """
        يختار pool مناسب:
          - HTTP scheme: socks4 → http → socks5
          - HTTPS scheme: socks5 → http (لا socks4!)
        """
        scheme = urlparse(url).scheme.lower()

        if scheme == 'http':
            # HTTP: socks4 مناسب
            for name in ('socks4', 'http', 'socks5'):
                if self.pools[name]:
                    return name
        else:
            # HTTPS: socks5 أو http فقط (لا socks4!)
            for name in ('socks5', 'http'):
                if self.pools[name]:
                    return name

        return None

    def process_request(self, request, spider):
        if request.meta.get('proxy'):
            return None

        swaps = request.meta.get('_proxy_swaps', 0)
        if swaps >= self.MAX_SWAPS_PER_REQUEST:
            return None

        pool_name = self._pick_pool_for_url(request.url)
        if not pool_name:
            return None

        pool = self.pools[pool_name]
        if not pool:
            return None

        chosen = random.choice(pool)
        formatted = self._format_proxy(chosen)
        if not formatted:
            return None

        request.meta['proxy'] = formatted
        request.meta['_raw_proxy'] = chosen
        request.meta['_proxy_pool'] = pool_name
        request.meta['_proxy_swaps'] = swaps + 1
        request.meta['download_timeout'] = self.PROXY_TIMEOUT
        self.used_by_pool[pool_name] += 1
        return None

    def process_response(self, request, response, spider):
        raw = request.meta.get('_raw_proxy')
        if not raw:
            return response

        # Google CAPTCHA
        if self._is_google_captcha(response):
            self.captcha_hits += 1
            self._mark_failure(raw, request.meta.get('_proxy_pool'))
            logger.warning(f"🚫 Google CAPTCHA via {raw} → rotating")
            retry = request.copy()
            retry.meta['proxy'] = None
            retry.meta.pop('_raw_proxy', None)
            retry.dont_filter = True
            return retry

        if response.status < 400:
            self.failures[raw] = 0
            return response

        if response.status in (403, 407, 429, 500, 502, 503, 504):
            self._mark_failure(raw, request.meta.get('_proxy_pool'))
            retry = request.copy()
            retry.meta['proxy'] = None
            retry.meta.pop('_raw_proxy', None)
            retry.dont_filter = True
            return retry

        return response

    def process_exception(self, request, exception, spider):
        raw = request.meta.get('_raw_proxy')
        if not raw:
            return None

        self._mark_failure(raw, request.meta.get('_proxy_pool'))
        retry = request.copy()
        retry.meta['proxy'] = None
        retry.meta.pop('_raw_proxy', None)
        retry.dont_filter = True
        return retry

    def _mark_failure(self, raw, pool_name):
        self.failures[raw] = self.failures.get(raw, 0) + 1
        if self.failures[raw] >= self.MAX_FAILURES:
            if pool_name and raw in self.pools[pool_name]:
                self.pools[pool_name].remove(raw)
                self.dead_removed[pool_name] += 1

    def spider_closed(self, spider):
        logger.info(
            f"📊 Proxy Stats:\n"
            f"   SOCKS4: used={self.used_by_pool['socks4']} | "
            f"removed={self.dead_removed['socks4']} | alive={len(self.pools['socks4'])}\n"
            f"   SOCKS5: used={self.used_by_pool['socks5']} | "
            f"removed={self.dead_removed['socks5']} | alive={len(self.pools['socks5'])}\n"
            f"   HTTP:   used={self.used_by_pool['http']} | "
            f"removed={self.dead_removed['http']} | alive={len(self.pools['http'])}\n"
            f"   Captcha hits: {self.captcha_hits}"
        )
