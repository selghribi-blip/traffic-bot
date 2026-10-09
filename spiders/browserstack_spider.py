# spiders/browserstack_spider.py
"""
BrowserStack + Local Browser Spider
====================================
- يستخدم BrowserStack (متصفحات حقيقية على أجهزة حقيقية).
- fallback تلقائي إلى Chrome محلي إذا فشلت بيانات BrowserStack.
- دعم بروكسي اختياري عبر utils/proxy_for_browser.py.
- يضمن إنتاج عنصر زيارة دائمًا (نجاح أو فشل) لتسهيل التجميع.
"""
import os
import random
import scrapy
from datetime import datetime, timezone

from utils.browserstack_client import BrowserStackClient, LocalBrowserClient
from utils.proxy_for_browser import BrowserProxyProvider


class BrowserStackSpider(scrapy.Spider):
    name = 'browserstack_bot'

    custom_settings = {
        'DOWNLOAD_DELAY': 3,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'CONCURRENT_REQUESTS': 1,
        'RETRY_TIMES': 1,
        'DOWNLOAD_TIMEOUT': 90,
    }

    # ---------- متصفحات BrowserStack المدعومة ----------
    BROWSERSTACK_BROWSERS = [
        ('chrome',  'Windows', '11'),
        ('chrome',  'Windows', '10'),
        ('chrome',  'OS X',    'Ventura'),
        ('chrome',  'OS X',    'Monterey'),
        ('firefox', 'Windows', '11'),
        ('edge',    'Windows', '11'),
        ('safari',  'OS X',    'Ventura'),
    ]

    def __init__(self, target_url=None, use_browserstack='true', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_url = (target_url or '').strip() or 'https://www.forjo.tech/'
        self.use_browserstack = str(use_browserstack).lower() == 'true'
        self.client = None
        self.ads_clicked = 0
        self.forms_filled = 0
        self.proxy_used = None
        self._proxy_provider = None

    # ============================================================
    # START
    # ============================================================
    def start_requests(self):
        # تصحيح البروتوكول
        if not self.target_url.startswith(('http://', 'https://')):
            self.target_url = 'https://' + self.target_url

        self.logger.info(f"🎬 Starting browser bot for: {self.target_url}")
        self.logger.info(f"   Mode: {'BrowserStack' if self.use_browserstack else 'Local'}")

        # التحقق من بيانات BrowserStack
        if self.use_browserstack:
            user = os.environ.get('BROWSERSTACK_USERNAME', '').strip()
            key = os.environ.get('BROWSERSTACK_ACCESS_KEY', '').strip()
            if not (user and key):
                self.logger.warning(
                    "⚠️ BrowserStack credentials missing → falling back to LOCAL"
                )
                self.use_browserstack = False

        yield scrapy.Request(
            url=self.target_url,
            callback=self.parse_with_browser,
            errback=self.handle_error,
            dont_filter=True,
            meta={'handle_httpstatus_all': True},
        )

    # ============================================================
    # MAIN CALLBACK
    # ============================================================
    def parse_with_browser(self, response):
        """يشغّل المتصفح، يزور الموقع، ويُنتج عنصر الزيارة."""
        status = 'unknown'
        error_msg = None

        try:
            # 1) اختر البروكسي (اختياري)
            proxy = self._pick_proxy()
            self.proxy_used = proxy

            # 2) أنشئ جلسة المتصفح
            if self.use_browserstack:
                driver = self._start_browserstack(proxy)
            else:
                driver = self._start_local(proxy)

            if driver is None:
                raise RuntimeError("Browser session creation returned None")

            # 3) تفاعل مع الصفحة
            self.client.wait_for_page_load(timeout=30)
            self._random_scroll()

            self.ads_clicked = self.client.click_ads()
            self.forms_filled = self.client.fill_form()

            # 4) لقطة شاشة (اختياري، محمي)
            try:
                filename = f"bs_{int(datetime.now(timezone.utc).timestamp())}.png"
                self.client.take_screenshot(filename)
                self.logger.info(f"📸 Screenshot saved: {filename}")
            except Exception as e:
                self.logger.debug(f"Screenshot skipped: {e}")

            status = 'success'
            self.logger.info(
                f"✅ Visit successful | ads={self.ads_clicked} "
                f"forms={self.forms_filled} proxy={self.proxy_used or 'direct'}"
            )

        except Exception as e:
            status = f'error: {e.__class__.__name__}'
            error_msg = str(e)[:200]
            self.logger.exception(f"❌ Browser automation failed: {e}")

        finally:
            # إغلاق المتصفح دائمًا
            if self.client:
                try:
                    self.client.close()
                except Exception:
                    pass

        # 5) أنتج عنصر الزيارة (يُسلَّم حتى عند الفشل)
        yield {
            'type': 'browserstack_visit',
            'url': self.target_url,
            'status': status,
            'error': error_msg,
            'ads_clicked': self.ads_clicked,
            'forms_filled': self.forms_filled,
            'mode': 'browserstack' if self.use_browserstack else 'local',
            'proxy_used': self.proxy_used,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    # ============================================================
    # HELPERS
    # ============================================================
    def _pick_proxy(self):
        """يختار بروكسيًا إذا كان مفعّلًا عبر env."""
        if os.environ.get('DISABLE_PROXIES', 'false').lower() == 'true':
            return None

        if os.environ.get('USE_PROXY_WITH_BROWSER', 'false').lower() != 'true':
            return None

        if self._proxy_provider is None:
            self._proxy_provider = BrowserProxyProvider()

        proxy = self._proxy_provider.pick()
        if proxy:
            self.logger.info(f"🌐 Using proxy: {proxy}")
        else:
            self.logger.warning("⚠️ No proxy available → using direct connection")
        return proxy

    def _start_browserstack(self, proxy=None):
        """ينشئ جلسة BrowserStack."""
        username = os.environ.get('BROWSERSTACK_USERNAME', '').strip()
        access_key = os.environ.get('BROWSERSTACK_ACCESS_KEY', '').strip()

        self.client = BrowserStackClient(username, access_key)
        browser, os_name, os_version = random.choice(self.BROWSERSTACK_BROWSERS)
        self.logger.info(f"🖥️ BrowserStack session: {browser} on {os_name} {os_version}")

        return self.client.start_session(
            url=self.target_url,
            browser=browser,
            os_name=os_name,
            os_version=os_version,
            proxy=proxy,
            use_local=False,
        )

    def _start_local(self, proxy=None):
        """ينشئ جلسة Chrome محلي (undetected)."""
        self.client = LocalBrowserClient()
        self.logger.info("🖥️ Local Chrome (undetected-chromedriver)")
        return self.client.start_session(
            url=self.target_url,
            headless=True,
            proxy=proxy,
        )

    def _random_scroll(self):
        """تمرير عشوائي لمحاكاة السلوك البشري."""
        try:
            count = random.randint(3, 7)
            self.client.scroll_page(scroll_count=count)
            self.logger.debug(f"📜 Scrolled {count} times")
        except Exception as e:
            self.logger.debug(f"Scroll failed: {e}")

    def handle_error(self, failure):
        self.logger.error(
            f"❌ Request failed: {failure.request.url} | {failure.value}"
        )

    def closed(self, reason):
        self.logger.info(
            f"🏁 BrowserStack spider closed ({reason}) | "
            f"ads={self.ads_clicked} forms={self.forms_filled}"
        )
