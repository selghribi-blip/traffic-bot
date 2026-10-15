# middlewares/proxy_rotator.py
# Proxy Rotator with section headers support and SOCKS4 for HTTPS fallback
# ============================================
# Supported formats in manual_proxies.txt:
#   - ip:port                       (uses current section)
#   - ip:port:user:pass             (HTTP auth)
#   - user:pass@ip:port             (HTTP auth)
#   - socks4://ip:port              (explicit)
#   - socks5://ip:port              (explicit)
#   - http://ip:port                (explicit)
# Section headers:
#   # SOCKS4
#   # SOCKS5
#   # HTTP

import os
import re
import random
import logging
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from scrapy import signals
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


class FreeProxyRotatorMiddleware:
    HTTP_SOURCES = [
        'https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/http/data.txt',
        'https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/checked_proxies/http.txt',
    ]

    MAX_FAILURES = 1
    MAX_SWAPS_PER_REQUEST = 8
    SOCKS_FAILS_BEFORE_HTTP = 3
    PROXY_TIMEOUT = 20
    HEALTHCHECK_URL = 'http://httpbin.org/ip'
    HEALTHCHECK_TIMEOUT = 8
    HEALTHCHECK_WORKERS = 50
    HEALTHCHECK_SAMPLE = 300

    GOOGLE_CAPTCHA_PATTERNS = [
        'google.com/sorry',
        '/sorry/index',
        'consent.google.com',
    ]

    def __init__(self, pools, healthcheck_enabled=False):
        self.pools = pools
        self.failures = {}
        self.used_by_pool = {k: 0 for k in self.pools}
        self.dead_removed = {k: 0 for k in self.pools}
        self.captcha_hits = 0
        self.socks_fail_count = 0

        logger.info(
            f"Pools -> SOCKS4: {len(self.pools['socks4'])} | "
            f"SOCKS5: {len(self.pools['socks5'])} | HTTP: {len(self.pools['http'])}"
        )

    @classmethod
    def from_crawler(cls, crawler):
        if os.environ.get('DISABLE_PROXIES', 'false').lower() == 'true':
            raise NotConfigured("Disabled by env")

        pools = {'socks4': [], 'socks5': [], 'http': []}

        # 1) Parse manual_proxies.txt
        manual_file = os.environ.get('MANUAL_PROXY_FILE', 'manual_proxies.txt')
        if os.path.isfile(manual_file):
            parsed = cls._parse_manual_file(manual_file)
            for k in pools:
                pools[k].extend(parsed[k])
            total = sum(len(v) for v in parsed.values())
            logger.info(f"Manual proxies: {total}")

        # 2) env
        manual_env = os.environ.get('MANUAL_PROXIES', '').strip()
        if manual_env:
            for p in re.split(r'[,\n]', manual_env):
                p = p.strip()
                if p:
                    pools['http'].append(p)

        # 3) Remote HTTP sources
        if os.environ.get('FETCH_REMOTE_PROXIES', 'true').lower() == 'true':
            for url in cls.HTTP_SOURCES:
                try:
                    r = requests.get(url, timeout=15)
                    r.raise_for_status()
                    count = 0
                    for line in r.text.splitlines():
                        line = line.strip()
                        if line and not line.startswith('#') and ':' in line:
                            pools['http'].append(line)
                            count += 1
                    logger.info(f"Remote {url.split('/')[4]}: {count} HTTP")
                except Exception as e:
                    logger.warning(f"Failed {url}: {e}")

        total = sum(len(v) for v in pools.values())
        if total == 0:
            raise NotConfigured("No proxies available")

        for k in pools:
            random.shuffle(pools[k])

        healthcheck = os.environ.get('PROXY_HEALTHCHECK', 'false').lower() == 'true'
        if healthcheck:
            for k in pools:
                if pools[k]:
                    pools[k] = cls._filter_alive(pools[k], k)

        mw = cls(pools, healthcheck)
        crawler.signals.connect(mw.spider_closed, signal=signals.spider_closed)
        return mw

    @classmethod
    def _parse_manual_file(cls, path):
        pools = {'socks4': [], 'socks5': [], 'http': []}
        current_scheme = 'http'

        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if line.startswith('#'):
                    lower = line.lower()
                    if 'socks4' in lower or 'socks 4' in lower:
                        current_scheme = 'socks4'
                    elif 'socks5' in lower or 'socks 5' in lower:
                        current_scheme = 'socks5'
                    elif 'http' in lower:
                        current_scheme = 'http'
                    continue

                if '://' in line:
                    scheme = line.split('://', 1)[0].lower()
                    if scheme in ('socks4', 'socks4a'):
                        pools['socks4'].append(line)
                    elif scheme in ('socks5', 'socks5h'):
                        pools['socks5'].append(line)
                    else:
                        pools['http'].append(line)
                    continue

                if current_scheme == 'socks4':
                    pools['socks4'].append(f"socks4://{line}")
                elif current_scheme == 'socks5':
                    pools['socks5'].append(f"socks5h://{line}")
                else:
                    pools['http'].append(line)

        return pools

    @classmethod
    def _filter_alive(cls, proxies, pool_name):
        sample_size = min(cls.HEALTHCHECK_SAMPLE, len(proxies))
        sample_list = random.sample(proxies, sample_size)
        alive = []

        def check(proxy_str):
            try:
                url = cls._format_proxy(proxy_str)
                if not url:
                    return None
                r = requests.get(
                    cls.HEALTHCHECK_URL,
                    proxies={'http': url, 'https': url},
                    timeout=cls.HEALTHCHECK_TIMEOUT,
                )
                if r.status_code == 200:
                    return proxy_str
            except Exception:
                pass
            return None

        logger.info(f"Health-checking {sample_size} {pool_name} proxies...")
        with ThreadPoolExecutor(max_workers=cls.HEALTHCHECK_WORKERS) as ex:
            futures = {ex.submit(check, p): p for p in sample_list}
            for fut in as_completed(futures):
                res = fut.result()
                if res:
                    alive.append(res)

        logger.info(f"Alive {pool_name}: {len(alive)}/{sample_size}")
        return alive or sample_list

    @staticmethod
    def _format_proxy(raw: str) -> str:
        raw = raw.strip()
        if not raw:
            return None
        if '://' in raw:
            return raw
        if '@' in raw:
            return f"http://{raw}"
        parts = raw.split(':')
        if len(parts) == 4:
            ip, port, user, pwd = parts
            return f"http://{user}:{pwd}@{ip}:{port}"
        if len(parts) == 2:
            return f"http://{raw}"
        return f"http://{raw}"

    def _is_google_captcha(self, response):
        url = response.url.lower()
        return any(p in url for p in self.GOOGLE_CAPTCHA_PATTERNS)

    def _pick_pool_for_url(self, url):
        scheme = urlparse(url).scheme.lower()
        if scheme == 'http':
            for name in ('socks4', 'http', 'socks5'):
                if self.pools[name]:
                    return name
        else:
            # HTTPS: SOCKS5 -> SOCKS4 -> HTTP (allow SOCKS4 fallback)
            if self.socks_fail_count >= self.SOCKS_FAILS_BEFORE_HTTP:
                if self.pools['http']:
                    return 'http'
            for name in ('socks5', 'socks4', 'http'):
                if self.pools[name]:
                    return name
        return None

    def process_request(self, request, spider):
        swaps = request.meta.get('_proxy_swaps', 0)
        if swaps >= self.MAX_SWAPS_PER_REQUEST:
            request.meta.pop('proxy', None)
            request.meta.pop('_raw_proxy', None)
            return None

        request.meta.pop('proxy', None)
        request.meta.pop('_raw_proxy', None)

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
        pool = request.meta.get('_proxy_pool')
        if not raw:
            return response

        if self._is_google_captcha(response):
            self.captcha_hits += 1
            self._mark_failure(raw, pool)
            logger.warning(f"Google CAPTCHA via {raw}")
            return self._retry(request)

        if response.status < 400:
            self.failures[raw] = 0
            return response

        if response.status in (403, 407, 429, 500, 502, 503, 504):
            self._mark_failure(raw, pool)
            return self._retry(request)

        return response

    def process_exception(self, request, exception, spider):
        raw = request.meta.get('_raw_proxy')
        pool = request.meta.get('_proxy_pool')
        if not raw:
            return None
        if pool in ('socks4', 'socks5'):
            self.socks_fail_count += 1
        self._mark_failure(raw, pool)
        return self._retry(request)

    def _retry(self, request):
        retry = request.copy()
        retry.meta['proxy'] = None
        retry.meta.pop('_raw_proxy', None)
        retry.meta.pop('_proxy_pool', None)
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
            "\n"
            "============================================================\n"
            "PROXY ROTATOR REPORT\n"
            "============================================================\n"
            f"   Total used:     {sum(self.used_by_pool.values())}\n"
            f"   Total removed:  {sum(self.dead_removed.values())}\n"
            f"   Captcha hits:   {self.captcha_hits}\n"
            f"   SOCKS failures: {self.socks_fail_count}\n"
            f"   SOCKS4: used={self.used_by_pool['socks4']} | alive={len(self.pools['socks4'])}\n"
            f"   SOCKS5: used={self.used_by_pool['socks5']} | alive={len(self.pools['socks5'])}\n"
            f"   HTTP:   used={self.used_by_pool['http']} | alive={len(self.pools['http'])}\n"
            "============================================================"
        )
