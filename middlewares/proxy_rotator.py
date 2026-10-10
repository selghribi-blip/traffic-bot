# middlewares/proxy_rotator.py
"""
Proxy Rotator — Supports HTTP + SOCKS4 + SOCKS5
================================================
- يدعم manual_proxies.txt بصيغ متعددة.
- يجلب HTTP من مصادر بعيدة كـ fallback.
- Health-check موازي + حذف فوري للميت.
- دعم كامل لـ socks4:// / socks5:// / socks5h://
"""
import os
import re
import random
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from scrapy import signals
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


class FreeProxyRotatorMiddleware:
    HTTP_SOURCES = [
        'https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/checked_proxies/http.txt',
        'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt',
        'https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/top-trusted.txt',
        'https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/http/data.txt',
    ]

    # إعدادات
    MAX_FAILURES = 2
    MAX_SWAPS_PER_REQUEST = 3
    PROXY_TIMEOUT = 20
    HEALTHCHECK_URL = 'http://httpbin.org/ip'
    HEALTHCHECK_TIMEOUT = 10
    HEALTHCHECK_WORKERS = 30
    HEALTHCHECK_SAMPLE = 150

    def __init__(self, proxies, healthcheck=False):
        self.proxies = list(proxies)
        self.failures = {}
        self.used = 0
        self.dead_removed = 0
        self.healthcheck_enabled = healthcheck
        self.count_http = sum(1 for p in self.proxies if self._scheme(p).startswith('http'))
        self.count_socks = len(self.proxies) - self.count_http

    @classmethod
    def from_crawler(cls, crawler):
        if os.environ.get('DISABLE_PROXIES', 'false').lower() == 'true':
            logger.warning("⛔ Proxies DISABLED via env")
            raise NotConfigured("Disabled by env")

        proxies = set()

        # (أ) ملف يدوي
        manual_file = os.environ.get('MANUAL_PROXY_FILE', 'manual_proxies.txt')
        if os.path.isfile(manual_file):
            with open(manual_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        proxies.add(line)
            logger.info(f"📁 Loaded {len(proxies)} manual proxies from {manual_file}")

        # (ب) env
        manual_env = os.environ.get('MANUAL_PROXIES', '').strip()
        if manual_env:
            for p in re.split(r'[,\n]', manual_env):
                p = p.strip()
                if p:
                    proxies.add(p)
            logger.info(f"📁 Loaded {len(proxies)} from env")

        # (ج) مصادر HTTP بعيدة
        if os.environ.get('FETCH_REMOTE_PROXIES', 'false').lower() == 'true':
            for url in cls.HTTP_SOURCES:
                try:
                    r = requests.get(url, timeout=15)
                    r.raise_for_status()
                    for line in r.text.splitlines():
                        line = line.strip()
                        if line and not line.startswith('#') and ':' in line:
                            proxies.add(line)
                    logger.info(f"🌐 {url.split('/')[4]}: OK")
                except Exception as e:
                    logger.warning(f"⚠️ Failed {url}: {e}")

        if not proxies:
            raise NotConfigured("No proxies available")

        proxies = list(proxies)
        random.shuffle(proxies)

        healthcheck = os.environ.get('PROXY_HEALTHCHECK', 'false').lower() == 'true'
        if healthcheck:
            proxies = cls._filter_alive(proxies)

        mw = cls(proxies, healthcheck)
        crawler.signals.connect(mw.spider_closed, signal=signals.spider_closed)
        logger.info(
            f"✅ ProxyRotator ready: {len(mw.proxies)} proxies "
            f"(HTTP: {mw.count_http}, SOCKS: {mw.count_socks})"
        )
        return mw

    @staticmethod
    def _filter_alive(proxies):
        sample_size = min(FreeProxyRotatorMiddleware.HEALTHCHECK_SAMPLE, len(proxies))
        sample_list = random.sample(proxies, sample_size)
        alive = []

        def check(proxy_str):
            try:
                url = FreeProxyRotatorMiddleware._format_proxy(proxy_str)
                if not url:
                    return None
                r = requests.get(
                    FreeProxyRotatorMiddleware.HEALTHCHECK_URL,
                    proxies={'http': url, 'https': url},
                    timeout=FreeProxyRotatorMiddleware.HEALTHCHECK_TIMEOUT,
                )
                if r.status_code == 200:
                    return proxy_str
            except Exception:
                pass
            return None

        logger.info(f"🔍 Health-checking {sample_size} proxies...")
        with ThreadPoolExecutor(
            max_workers=FreeProxyRotatorMiddleware.HEALTHCHECK_WORKERS
        ) as ex:
            futures = {ex.submit(check, p): p for p in sample_list}
            for fut in as_completed(futures):
                res = fut.result()
                if res:
                    alive.append(res)

        logger.info(f"✅ Alive: {len(alive)}/{sample_size}")
        return alive or sample_list

    @staticmethod
    def _scheme(raw: str) -> str:
        raw = raw.strip()
        if '://' in raw:
            return raw.split('://', 1)[0].lower()
        return 'http'

    @staticmethod
    def _format_proxy(raw: str) -> str:
        """يدعم: ip:port | ip:port:user:pass | user:pass@ip:port | scheme://..."""
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

    def process_request(self, request, spider):
        if request.meta.get('proxy'):
            return None
        if not self.proxies:
            return None

        swaps = request.meta.get('_proxy_swaps', 0)
        if swaps >= self.MAX_SWAPS_PER_REQUEST:
            return None

        chosen = random.choice(self.proxies)
        formatted = self._format_proxy(chosen)
        if not formatted:
            return None

        request.meta['proxy'] = formatted
        request.meta['_raw_proxy'] = chosen
        request.meta['_proxy_swaps'] = swaps + 1
        request.meta['download_timeout'] = self.PROXY_TIMEOUT
        self.used += 1
        return None

    def process_response(self, request, response, spider):
        raw = request.meta.get('_raw_proxy')
        if not raw:
            return response

        if response.status < 400:
            self.failures[raw] = 0
            return response

        if response.status in (403, 407, 429, 500, 502, 503, 504):
            self._mark_failure(raw)
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

        self._mark_failure(raw)
        logger.debug(f"💀 {raw} ({exception.__class__.__name__})")

        retry = request.copy()
        retry.meta['proxy'] = None
        retry.meta.pop('_raw_proxy', None)
        retry.dont_filter = True
        return retry

    def _mark_failure(self, raw):
        self.failures[raw] = self.failures.get(raw, 0) + 1
        if self.failures[raw] >= self.MAX_FAILURES:
            if raw in self.proxies:
                self.proxies.remove(raw)
                self.dead_removed += 1

    def spider_closed(self, spider):
        logger.info(
            f"📊 Proxies | used={self.used} | removed={self.dead_removed} | "
            f"alive={len(self.proxies)}"
        )
