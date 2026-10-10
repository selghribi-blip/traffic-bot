# middlewares/proxy_rotator.py
"""
Smart Proxy Rotator — Fixed
============================
- Healthcheck ذكي حسب نوع البروكسي:
    * SOCKS4 → يفحص HTTP
    * SOCKS5/h → يفحص HTTPS
- يجلب HTTP من مصادر بعيدة (fallback).
- يميّز Google CAPTCHA ويعتبره فشل.
- يختار pool مناسب حسب scheme الطلب.
"""
import os
import re
import random
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from scrapy import signals
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


class FreeProxyRotatorMiddleware:
    HTTP_SOURCES = [
        'https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/http/data.txt',
        'https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/checked_proxies/http.txt',
        'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt',
        'https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/top-trusted.txt',
    ]

    # إعدادات
    MAX_FAILURES = 2
    MAX_SWAPS_PER_REQUEST = 4
    PROXY_TIMEOUT = 25
    HEALTHCHECK_HTTP_URL = 'http://httpbin.org/ip'
    HEALTHCHECK_HTTPS_URL = 'https://httpbin.org/ip'
    HEALTHCHECK_TIMEOUT = 10
    HEALTHCHECK_WORKERS = 30
    HEALTHCHECK_SAMPLE = 300

    # كشف Google CAPTCHA
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

        # (أ) ملف يدوي (SOCKS)
        manual_file = os.environ.get('MANUAL_PROXY_FILE', 'manual_proxies.txt')
        if os.path.isfile(manual_file):
            with open(manual_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        proxies.add(line)
            logger.info(f"📁 Manual proxies: {len(proxies)}")

        # (ب) env
        manual_env = os.environ.get('MANUAL_PROXIES', '').strip()
        if manual_env:
            for p in re.split(r'[,\n]', manual_env):
                p = p.strip()
                if p:
                    proxies.add(p)

        # (ج) مصادر HTTP (مهم جداً — fallback)
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

        # Healthcheck
        healthcheck = os.environ.get('PROXY_HEALTHCHECK', 'false').lower() == 'true'
        if healthcheck:
            proxies = cls._filter_alive(proxies)

        mw = cls(proxies)
        crawler.signals.connect(mw.spider_closed, signal=signals.spider_closed)
        return mw

    # ============================================================
    # HEALTHCHECK — ذكي حسب نوع البروكسي
    # ============================================================
    @classmethod
    def _filter_alive(cls, proxies):
        sample_size = min(cls.HEALTHCHECK_SAMPLE, len(proxies))
        sample_list = random.sample(proxies, sample_size)

        # فصل العينات حسب النوع
        socks4 = [p for p in sample_list if cls._scheme(p) in ('socks4', 'socks4a')]
        socks5 = [p for p in sample_list if cls._scheme(p) in ('socks5', 'socks5h')]
        https_like = [p for p in sample_list if cls._scheme(p) == 'http']

        alive = []

        # SOCKS4 → HTTP healthcheck
        if socks4:
            logger.info(f"🔍 Checking {len(socks4)} SOCKS4 via HTTP...")
            alive += cls._check_batch(socks4, cls.HEALTHCHECK_HTTP_URL)

        # SOCKS5/h + HTTP → HTTPS healthcheck (أهم)
        https_test = socks5 + https_like
        if https_test:
            logger.info(f"🔍 Checking {len(https_test)} via HTTPS...")
            alive += cls._check_batch(https_test, cls.HEALTHCHECK_HTTPS_URL)

        logger.info(f"✅ Alive: {len(alive)}/{sample_size}")
        return alive or sample_list

    @classmethod
    def _check_batch(cls, proxy_list, test_url):
        alive = []

        def check(proxy_str):
            try:
                url = cls._format_proxy(proxy_str)
                if not url:
                    return None
                r = requests.get(
                    test_url,
                    proxies={'http': url, 'https': url},
                    timeout=cls.HEALTHCHECK_TIMEOUT,
                )
                if r.status_code == 200:
                    return proxy_str
            except Exception:
                pass
            return None

        with ThreadPoolExecutor(max_workers=cls.HEALTHCHECK_WORKERS) as ex:
            futures = {ex.submit(check, p): p for p in proxy_list}
            for fut in as_completed(futures):
                res = fut.result()
                if res:
                    alive.append(res)

        return alive

    # ============================================================
    # HELPERS
    # ============================================================
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

    def _pick_pool_for_url(self, url: str) -> str:
        scheme = urlparse(url).scheme.lower()
        if scheme == 'http' and self.pools['socks4']:
            return 'socks4'
        if scheme == 'https' and self.pools['socks5']:
            return 'socks5'
        for name in ('socks5', 'socks4', 'http'):
            if self.pools[name]:
                return name
        return None

    # ============================================================
    # REQUEST
    # ============================================================
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

    # ============================================================
    # RESPONSE
    # ============================================================
    def process_response(self, request, response, spider):
        raw = request.meta.get('_raw_proxy')
        if not raw:
            return response

        # كشف Google CAPTCHA فورًا
        if self._is_google_captcha(response):
            logger.warning(f"🚫 Google CAPTCHA detected via {raw} → rotating")
            self._mark_failure(raw, request.meta.get('_proxy_pool'))
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

    # ============================================================
    # EXCEPTION
    # ============================================================
    def process_exception(self, request, exception, spider):
        raw = request.meta.get('_raw_proxy')
        if not raw:
            return None

        self._mark_failure(raw, request.meta.get('_proxy_pool'))
        logger.debug(f"💀 [{request.meta.get('_proxy_pool')}] {raw} ({exception.__class__.__name__})")

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
            f"removed={self.dead_removed['http']} | alive={len(self.pools['http'])}"
        )
