# middlewares/proxy_rotator.py
"""
Proxy Rotator Middleware — Production-Ready
============================================
يجلب البروكسيات من مصادر موثوقة، يدعم قائمة يدوية،
يُدير الفشل بذكاء، ويدعم صيغ متعددة.

صيغ البروكسي المدعومة:
  - ip:port                          → http://ip:port
  - ip:port:user:pass                → http://user:pass@ip:port
  - user:pass@ip:port                → http://user:pass@ip:port
  - protocol://ip:port               → protocol://ip:port
  - protocol://user:pass@ip:port     → protocol://user:pass@ip:port
  - socks5://ip:port                 → socks5://ip:port
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
    # ---------- مصادر موثوقة ومحدَّثة ----------
    PROXY_SOURCES = [
        # 1) dinoz0rg — 5,860 بروكسي مُتحقَّق منه
        'https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/checked_proxies/http.txt',
        # 2) proxifly — 48,585 بروكسي (تحديث كل 5 دقائق)
        'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt',
        # 3) Thordata — verified + GeoIP + latency tiers
        'https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/top-trusted.txt',
        # 4) xyzs996 — 6,609 بروكسي (تحديث كل 30 دقيقة)
        'https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/http/data.txt',
        # 5) databay-labs — تحديث كل 5 دقائق
        'https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/http.txt',
        # 6) proxy-free — متعدد البروتوكولات
        'https://raw.githubusercontent.com/proxy-free/free-proxy-list/main/socks5.txt',
    ]

    # ---------- إعدادات ----------
    MAX_FAILURES = 2              # حذف بعد فشلين
    PROXY_TIMEOUT = 20            # بروكسي أبطأ من 20s = ميت
    HEALTHCHECK_URL = 'http://httpbin.org/ip'
    HEALTHCHECK_TIMEOUT = 5
    HEALTHCHECK_WORKERS = 50

    def __init__(self, proxies, healthcheck=False):
        self.proxies = list(proxies)
        self.failures = {}
        self.used = 0
        self.dead_removed = 0
        self.healthcheck_enabled = healthcheck
        self.verified = []

    @classmethod
    def from_crawler(cls, crawler):
        # 1) تعطيل كامل عبر env
        if os.environ.get('DISABLE_PROXIES', 'false').lower() == 'true':
            logger.warning("⛔ Proxies DISABLED via DISABLE_PROXIES env")
            raise NotConfigured("Disabled by env")

        # 2) اجمع من: manual file + env + remote sources
        proxies = set()

        # (أ) بروكسيات يدوية من ملف
        manual_file = os.environ.get('MANUAL_PROXY_FILE', 'manual_proxies.txt')
        if os.path.isfile(manual_file):
            with open(manual_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        proxies.add(line)
            logger.info(f"📁 Loaded {len(proxies)} manual proxies from {manual_file}")

        # (ب) بروكسيات يدوية من env (فاصلة أو سطر جديد)
        manual_env = os.environ.get('MANUAL_PROXIES', '')
        if manual_env:
            for p in re.split(r'[,\n]', manual_env):
                p = p.strip()
                if p:
                    proxies.add(p)
            logger.info(f"📁 Loaded manual proxies from MANUAL_PROXIES env")

        # (ج) بروكسيات من مصادر بعيدة
        remote_urls = crawler.settings.getlist('FREE_PROXY_LIST_URL') or cls.PROXY_SOURCES
        for url in remote_urls:
            try:
                r = requests.get(url, timeout=15)
                r.raise_for_status()
                count = 0
                for line in r.text.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        proxies.add(line)
                        count += 1
                logger.info(f"🌐 {url.split('/')[4]}: {count} proxies")
            except Exception as e:
                logger.warning(f"⚠️ Failed {url}: {e}")

        if not proxies:
            raise NotConfigured("No proxies available")

        proxies = list(proxies)
        random.shuffle(proxies)

        # 3) فحص حياة اختياري
        healthcheck = os.environ.get('PROXY_HEALTHCHECK', 'false').lower() == 'true'
        if healthcheck:
            proxies = cls._filter_alive(proxies)

        mw = cls(proxies, healthcheck)
        crawler.signals.connect(mw.spider_closed, signal=signals.spider_closed)
        logger.info(f"✅ ProxyRotator ready: {len(mw.proxies)} proxies")
        return mw

    @staticmethod
    def _filter_alive(proxies, sample=200):
        """يفحص عينة عشوائية من البروكسيات ويرجع الحية فقط."""
        sample_list = random.sample(proxies, min(sample, len(proxies)))
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

        logger.info(f"🔍 Health-checking {len(sample_list)} proxies...")
        with ThreadPoolExecutor(max_workers=FreeProxyRotatorMiddleware.HEALTHCHECK_WORKERS) as ex:
            futures = {ex.submit(check, p): p for p in sample_list}
            for fut in as_completed(futures):
                res = fut.result()
                if res:
                    alive.append(res)

        logger.info(f"✅ Alive: {len(alive)}/{len(sample_list)}")
        return alive or sample_list

    # ---------- تحويل الصيغ ----------
    @staticmethod
    def _format_proxy(raw: str) -> str:
        """
        يحوّل أي صيغة إلى URL صالح لـ Scrapy.
        يدعم: ip:port | ip:port:user:pass | user:pass@ip:port | scheme://...
        """
        raw = raw.strip()
        if not raw:
            return None

        # إذا يحوي scheme مسبقًا
        if '://' in raw:
            return raw

        parts = raw.split(':')

        # ip:port
        if len(parts) == 2:
            return f"http://{parts[0]}:{parts[1]}"

        # ip:port:user:pass
        if len(parts) == 4:
            ip, port, user, pwd = parts
            return f"http://{user}:{pwd}@{ip}:{port}"

        # user:pass@ip:port
        if '@' in raw and len(parts) == 3:
            creds, host = raw.rsplit('@', 1)
            return f"http://{creds}@{host}"

        # احتياطي
        return f"http://{raw}"

    # ---------- Request ----------
    def process_request(self, request, spider):
        if request.meta.get('proxy'):
            return None
        if not self.proxies:
            return None

        chosen = random.choice(self.proxies)
        formatted = self._format_proxy(chosen)
        if not formatted:
            return None

        request.meta['proxy'] = formatted
        request.meta['_raw_proxy'] = chosen
        request.meta['download_timeout'] = self.PROXY_TIMEOUT
        self.used += 1
        return None

    # ---------- Response ----------
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

    # ---------- Exception ----------
    def process_exception(self, request, exception, spider):
        raw = request.meta.get('_raw_proxy')
        if not raw:
            return None

        self._mark_failure(raw)
        logger.debug(f"💀 Proxy failed: {raw} ({exception.__class__.__name__})")

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
            f"📊 Proxies | used={self.used} | removed={self.dead_removed} | alive={len(self.proxies)}"
        )
