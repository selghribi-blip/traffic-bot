# spiders/browserstack_spider.py
import os
import random
import time
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

    BROWSERSTACK_BROWSERS = [
        ('chrome', 'Windows', '11'),
        ('chrome', 'Windows', '10'),
        ('chrome', 'OS X', 'Ventura'),
        ('chrome', 'OS X', 'Monterey'),
        ('firefox', 'Windows', '11'),
        ('edge', 'Windows', '11'),
        ('safari', 'OS X', 'Ventura'),
    ]

    AD_CLICK_PROBABILITY = 0.40
    MAX_AD_CLICKS_PER_SESSION = 2
    DWELL_TIME_MIN = 30
    DWELL_TIME_MAX = 90

    def __init__(self, target_url=None, use_browserstack='true', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_url = (target_url or '').strip() or 'https://www.forjo.tech/'
        self.use_browserstack = str(use_browserstack).lower() == 'true'
        self.client = None
        self.ads_clicked = 0
        self.forms_filled = 0
        self.proxy_used = None
        self.dwell_time = 0
        self.scroll_count = 0
        self.internal_clicks = 0
        self.captcha_detected = False
        self._proxy_provider = None

    def start_requests(self):
        if not self.target_url.startswith(('http://', 'https://')):
            self.target_url = 'https://' + self.target_url

        self.logger.info(f"🎬 Starting browser bot for: {self.target_url}")
        self.logger.info(f"   Mode: {'BrowserStack' if self.use_browserstack else 'Local'}")

        if self.use_browserstack:
            user = os.environ.get('BROWSERSTACK_USERNAME', '').strip()
            key = os.environ.get('BROWSERSTACK_ACCESS_KEY', '').strip()
            if not (user and key):
                self.logger.warning("⚠️ BrowserStack credentials missing → LOCAL")
                self.use_browserstack = False

        yield scrapy.Request(
            url=self.target_url,
            callback=self.parse_with_browser,
            errback=self.handle_error,
            dont_filter=True,
            meta={'handle_httpstatus_all': True},
        )

    def parse_with_browser(self, response):
        status = 'unknown'
        error_msg = None

        try:
            proxy = self._pick_proxy()
            self.proxy_used = proxy

            if self.use_browserstack:
                driver = self._start_browserstack(proxy)
            else:
                driver = self._start_local(proxy)

            if driver is None:
                raise RuntimeError("Session creation returned None")

            self.client.wait_for_page_load(timeout=30)

            if self.client.is_captcha_page():
                self.captcha_detected = True
                raise RuntimeError("Google CAPTCHA detected")

            self._random_scroll()

            if random.random() < self.AD_CLICK_PROBABILITY:
                self._safe_click_ads()

            self.forms_filled = self.client.fill_form()
            self._click_internal_links()
            self._dwell()

            try:
                fname = f"bs_{int(datetime.now(timezone.utc).timestamp())}.png"
                self.client.take_screenshot(fname)
            except Exception:
                pass

            status = 'success'
            self.logger.info(
                f"✅ Visit successful | ads={self.ads_clicked} "
                f"forms={self.forms_filled} dwell={self.dwell_time}s "
                f"scrolls={self.scroll_count} internal={self.internal_clicks}"
            )

        except Exception as e:
            status = f'error: {e.__class__.__name__}'
            error_msg = str(e)[:200]
            self.logger.exception(f"❌ Browser failed: {e}")

        finally:
            if self.client:
                try:
                    self.client.close()
                except Exception:
                    pass

        yield {
            'type': 'browserstack_visit',
            'url': self.target_url,
            'status': status,
            'error': error_msg,
            'ads_clicked': self.ads_clicked,
            'forms_filled': self.forms_filled,
            'dwell_time': self.dwell_time,
            'scroll_count': self.scroll_count,
            'internal_clicks': self.internal_clicks,
            'captcha': self.captcha_detected,
            'mode': 'browserstack' if self.use_browserstack else 'local',
            'proxy_used': self.proxy_used,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    def _safe_click_ads(self):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.action_chains import ActionChains

        max_clicks = random.randint(1, self.MAX_AD_CLICKS_PER_SESSION)
        self.logger.info(f"🖱️ Will try up to {max_clicks} ads")

        clicked_this_session = 0
        tried_selectors = set()

        for selector in self.client.AD_SELECTORS:
            if clicked_this_session >= max_clicks:
                break
            if selector in tried_selectors:
                continue
            tried_selectors.add(selector)

            try:
                elements = self.client.driver.find_elements(By.CSS_SELECTOR, selector)
                if not elements:
                    continue
                element = random.choice(elements[:5])
                if not (element.is_displayed() and element.is_enabled()):
                    continue

                self.client.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                    element
                )
                time.sleep(random.uniform(1.0, 2.5))

                try:
                    ActionChains(self.client.driver).move_to_element(element).pause(
                        random.uniform(0.3, 0.8)
                    ).perform()
                except Exception:
                    pass

                if not element.is_displayed():
                    continue

                try:
                    element.click()
                except Exception:
                    self.client.driver.execute_script("arguments[0].click();", element)

                clicked_this_session += 1
                self.ads_clicked += 1
                self.logger.info(f"🎯 Ad clicked: {selector}")

                time.sleep(random.uniform(3.0, 7.0))

                try:
                    if len(self.client.driver.window_handles) > 1:
                        main = self.client.driver.window_handles[0]
                        for handle in self.client.driver.window_handles[1:]:
                            self.client.driver.switch_to.window(handle)
                            time.sleep(random.uniform(2.0, 4.0))
                            self.client.driver.close()
                        self.client.driver.switch_to.window(main)
                except Exception:
                    pass

                time.sleep(random.uniform(2.0, 5.0))

            except Exception:
                continue

        self.logger.info(f"🖱️ Total ads clicked: {clicked_this_session}")

    def _random_scroll(self):
        try:
            count = random.randint(3, 7)
            for i in range(count):
                pixels = random.randint(300, 800)
                self.client.driver.execute_script(
                    f"window.scrollBy({{top: {pixels}, behavior: 'smooth'}});"
                )
                time.sleep(random.uniform(0.8, 2.0))
                if random.random() < 0.3:
                    self.client.driver.execute_script(
                        f"window.scrollBy({{top: -{random.randint(100, 300)}, behavior: 'smooth'}});"
                    )
                    time.sleep(random.uniform(0.5, 1.0))
            self.scroll_count = count
        except Exception:
            pass

    def _click_internal_links(self):
        from selenium.webdriver.common.by import By
        try:
            count = random.randint(1, 2)
            clicked = 0
            selectors = [
                'article a:not([href^="#"])', 'h2 a', 'h3 a',
                '.post-title a', '.entry-title a',
            ]
            for selector in selectors:
                if clicked >= count:
                    break
                try:
                    links = self.client.driver.find_elements(By.CSS_SELECTOR, selector)
                    if not links:
                        continue
                    link = random.choice(links[:5])
                    if not link.is_displayed():
                        continue
                    href = link.get_attribute('href') or ''
                    if not href or href.startswith('#') or 'forjo.tech' not in href:
                        continue

                    self.client.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", link
                    )
                    time.sleep(random.uniform(0.8, 1.5))
                    link.click()
                    time.sleep(random.uniform(3.0, 6.0))
                    self.client.driver.execute_script("window.scrollBy(0, 500);")
                    time.sleep(random.uniform(2.0, 4.0))
                    clicked += 1
                    self.internal_clicks += 1
                    self.client.driver.back()
                    time.sleep(random.uniform(2.0, 4.0))
                except Exception:
                    continue
        except Exception:
            pass

    def _dwell(self):
        try:
            duration = random.randint(self.DWELL_TIME_MIN, self.DWELL_TIME_MAX)
            self.logger.info(f"⏳ Dwelling {duration}s...")
            start = time.time()
            while time.time() - start < duration:
                time.sleep(random.uniform(5, 12))
                if random.random() < 0.5:
                    try:
                        self.client.driver.execute_script(
                            f"window.scrollBy({{top: {random.randint(200, 500)}, behavior: 'smooth'}});"
                        )
                    except Exception:
                        pass
            self.dwell_time = int(time.time() - start)
        except Exception:
            self.dwell_time = 30

    def _pick_proxy(self):
        if os.environ.get('DISABLE_PROXIES', 'false').lower() == 'true':
            return None
        if os.environ.get('USE_PROXY_WITH_BROWSER', 'false').lower() != 'true':
            return None
        if self._proxy_provider is None:
            self._proxy_provider = BrowserProxyProvider()
        return self._proxy_provider.pick()

    def _start_browserstack(self, proxy=None):
        username = os.environ.get('BROWSERSTACK_USERNAME', '').strip()
        access_key = os.environ.get('BROWSERSTACK_ACCESS_KEY', '').strip()
        self.client = BrowserStackClient(username, access_key)
        browser, os_name, os_version = random.choice(self.BROWSERSTACK_BROWSERS)
        self.logger.info(f"🖥️ BrowserStack: {browser} on {os_name} {os_version}")
        return self.client.start_session(
            url=self.target_url,
            browser=browser,
            os_name=os_name,
            os_version=os_version,
            proxy=proxy,
            use_local=False,
        )

    def _start_local(self, proxy=None):
        self.client = LocalBrowserClient()
        self.logger.info("🖥️ Local Chrome")
        return self.client.start_session(
            url=self.target_url,
            headless=True,
            proxy=proxy,
        )

    def handle_error(self, failure):
        self.logger.error(f"❌ {failure.request.url} | {failure.value}")

    def closed(self, reason):
        self.logger.info(
            f"🏁 Closed ({reason}) | ads={self.ads_clicked} forms={self.forms_filled}"
        )
