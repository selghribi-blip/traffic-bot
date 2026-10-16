# spiders/browserstack_spider.py
# Slow Click Mode - Human-like behavior with proper timing
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
        ('edge', 'Windows', '11'),
    ]

    # ============================================================
    # SLOW CLICK MODE - Human-like behavior
    # ============================================================
    USE_MOBILE = True

    # Reading phase (before any click)
    READ_TIME_MIN = 30              # ثواني قراءة
    READ_TIME_MAX = 60

    # Click behavior (VERY conservative)
    MAX_AD_CLICKS_PER_SESSION = 2   # ← فقط 2 نقرات
    CLICK_PROBABILITY = 0.6         # ← 60% فقط (ليس 100%)
    TIME_BEFORE_FIRST_CLICK_MIN = 45   # ← 45-90 ثانية قبل أول نقرة
    TIME_BEFORE_FIRST_CLICK_MAX = 90
    TIME_BETWEEN_CLICKS_MIN = 10    # ← 10-20 ثانية بين النقرات
    TIME_BETWEEN_CLICKS_MAX = 20
    TIME_AFTER_CLICK_MIN = 15       # ← 15-30 ثانية بعد النقرة
    TIME_AFTER_CLICK_MAX = 30

    # Dwell (total time on page)
    DWELL_TIME_MIN = 180            # ← 3 دقائق
    DWELL_TIME_MAX = 300            # ← 5 دقائق

    # Scrolling (slow and natural)
    SCROLL_MIN = 4                  # ← مرات أقل
    SCROLL_MAX = 8
    SCROLL_DELAY_MIN = 3.0          # ← تأخير طويل بين التمريرات
    SCROLL_DELAY_MAX = 7.0

    # Internal links (fewer, more meaningful)
    INTERNAL_LINKS_MIN = 1
    INTERNAL_LINKS_MAX = 2

    ADS_WAIT_MAX = 40

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
        self.ads_detected_in_dom = False
        self.click_attempts = 0
        self.reading_time = 0
        self._proxy_provider = None

    def start_requests(self):
        if not self.target_url.startswith(('http://', 'https://')):
            self.target_url = 'https://' + self.target_url

        self.logger.info(f"Starting SLOW CLICK bot for: {self.target_url}")
        self.logger.info(f"   Mode: {'BrowserStack' if self.use_browserstack else 'Local'}")
        self.logger.info(f"   Mobile: {self.USE_MOBILE}")
        self.logger.info(f"   Max clicks: {self.MAX_AD_CLICKS_PER_SESSION}")
        self.logger.info(f"   Dwell: {self.DWELL_TIME_MIN}-{self.DWELL_TIME_MAX}s")

        if self.use_browserstack:
            user = os.environ.get('BROWSERSTACK_USERNAME', '').strip()
            key = os.environ.get('BROWSERSTACK_ACCESS_KEY', '').strip()
            if not (user and key):
                self.logger.warning("BrowserStack credentials missing - LOCAL")
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

            # ============================================================
            # PHASE 1: Initial page load & settle
            # ============================================================
            self.logger.info("[PHASE 1] Page loaded - settling...")
            time.sleep(random.uniform(3, 6))

            # ============================================================
            # PHASE 2: Human-like reading (no clicks)
            # ============================================================
            self._human_reading_phase()

            # ============================================================
            # PHASE 3: Wait for ads
            # ============================================================
            self.ads_detected_in_dom = self._wait_for_ads()

            # ============================================================
            # PHASE 4: Trigger Monetag once
            # ============================================================
            if self.ads_detected_in_dom:
                self._trigger_monetag_once()
                time.sleep(random.uniform(2, 4))

            # ============================================================
            # PHASE 5: Wait before first click (critical!)
            # ============================================================
            wait_time = random.uniform(
                self.TIME_BEFORE_FIRST_CLICK_MIN,
                self.TIME_BEFORE_FIRST_CLICK_MAX,
            )
            self.logger.info(f"[PHASE 5] Waiting {wait_time:.0f}s before first click attempt")
            time.sleep(wait_time)

            # ============================================================
            # PHASE 6: Slow click (only 60% chance)
            # ============================================================
            if random.random() < self.CLICK_PROBABILITY:
                self.logger.info("[PHASE 6] Starting slow click sequence")
                self._slow_click_sequence()
            else:
                self.logger.info("[PHASE 6] Skipped clicking (probability)")

            # ============================================================
            # PHASE 7: Fill forms (if any)
            # ============================================================
            self.forms_filled = self.client.fill_form()
            if self.forms_filled > 0:
                time.sleep(random.uniform(5, 10))

            # ============================================================
            # PHASE 8: Maybe visit one internal link
            # ============================================================
            self._maybe_visit_internal_link()

            # ============================================================
            # PHASE 9: Final dwell
            # ============================================================
            self._final_dwell()

            try:
                fname = f"bs_{int(datetime.now(timezone.utc).timestamp())}.png"
                self.client.take_screenshot(fname)
            except Exception:
                pass

            status = 'success'
            self.logger.info(
                f"SLOW CLICK COMPLETE | ads={self.ads_clicked} "
                f"attempts={self.click_attempts} read={self.reading_time}s "
                f"dwell={self.dwell_time}s mobile={getattr(self.client, 'is_mobile', False)}"
            )

        except Exception as e:
            status = f'error: {e.__class__.__name__}'
            error_msg = str(e)[:200]
            self.logger.error(f"Browser failed: {e}")

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
            'click_attempts': self.click_attempts,
            'ads_detected': self.ads_detected_in_dom,
            'forms_filled': self.forms_filled,
            'reading_time': self.reading_time,
            'dwell_time': self.dwell_time,
            'scroll_count': self.scroll_count,
            'internal_clicks': self.internal_clicks,
            'captcha': self.captcha_detected,
            'mode': 'browserstack' if self.use_browserstack else 'local',
            'mobile': getattr(self.client, 'is_mobile', False),
            'proxy_used': self.proxy_used,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    # ============================================================
    # PHASE 2: Human Reading Phase (no clicks)
    # ============================================================
    def _human_reading_phase(self):
        """Simulate a human reading the page BEFORE any interaction."""
        read_time = random.uniform(self.READ_TIME_MIN, self.READ_TIME_MAX)
        self.logger.info(f"[READ] Reading page for {read_time:.0f}s...")
        start = time.time()

        # Slow scroll down like reading
        while time.time() - start < read_time:
            try:
                # Small scroll (like eye movement tracking)
                pixels = random.randint(150, 400)
                self.client.driver.execute_script(
                    f"window.scrollBy({{top: {pixels}, behavior: 'smooth'}});"
                )
                self.scroll_count += 1

                # Long pause (reading)
                time.sleep(random.uniform(3.0, 7.0))

                # Occasionally scroll back up (re-reading)
                if random.random() < 0.2:
                    self.client.driver.execute_script(
                        f"window.scrollBy({{top: -{random.randint(100, 250)}, behavior: 'smooth'}});"
                    )
                    time.sleep(random.uniform(1.5, 3.0))
            except Exception:
                pass

        self.reading_time = int(time.time() - start)
        self.logger.info(f"[READ] Done reading ({self.reading_time}s)")

    # ============================================================
    # PHASE 5: Trigger Monetag ONCE
    # ============================================================
    def _trigger_monetag_once(self):
        """Trigger Monetag with a single, natural click."""
        try:
            self.client.driver.execute_script("""
                (() => {
                    const x = window.innerWidth / 2;
                    const y = window.innerHeight / 2;
                    const el = document.elementFromPoint(x, y) || document.body;
                    el.dispatchEvent(new MouseEvent('click', {
                        bubbles: true, cancelable: true, view: window,
                        clientX: x, clientY: y, button: 0
                    }));
                })();
            """)
            self.logger.info("[MONETAG] Triggered once")
        except Exception as e:
            self.logger.debug(f"Monetag trigger failed: {e}")

    # ============================================================
    # PHASE 6: Slow Click Sequence
    # ============================================================
    def _slow_click_sequence(self):
        """Very slow, human-like clicking - max 2 clicks with long delays."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.action_chains import ActionChains

        self.logger.info("Starting SLOW click sequence...")

        clicked = 0
        tried_containers = set()
        tried_iframes = set()

        for attempt in range(self.MAX_AD_CLICKS_PER_SESSION):
            if clicked >= self.MAX_AD_CLICKS_PER_SESSION:
                break

            self.click_attempts += 1
            self.logger.info(f"[SLOW] Attempt {attempt + 1}/{self.MAX_AD_CLICKS_PER_SESSION}")

            # === Try container ===
            try:
                containers = self.client.driver.find_elements(
                    By.CSS_SELECTOR, 'div[id^="container-"]'
                )
                # Find one we haven't tried
                target = None
                for c in containers:
                    cid = c.get_attribute('id') or str(id(c))
                    if cid not in tried_containers and c.is_displayed():
                        target = c
                        tried_containers.add(cid)
                        break

                if target:
                    # Scroll smoothly to element
                    self.client.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center', behavior:'smooth'});",
                        target
                    )
                    time.sleep(random.uniform(2.0, 3.5))

                    # Human mouse move
                    try:
                        actions = ActionChains(self.client.driver)
                        actions.move_to_element(target)
                        actions.pause(random.uniform(0.3, 0.7))
                        actions.click(target)
                        actions.perform()
                        clicked += 1
                        self.ads_clicked += 1
                        self.logger.info(f"[SLOW] ✅ Clicked container (total: {clicked})")

                        # Long wait after click
                        post_wait = random.uniform(
                            self.TIME_AFTER_CLICK_MIN,
                            self.TIME_AFTER_CLICK_MAX,
                        )
                        self.logger.info(f"[SLOW] Waiting {post_wait:.0f}s after click")
                        time.sleep(post_wait)
                        self._close_extra_tabs()

                        # If we got max clicks, stop
                        if clicked >= self.MAX_AD_CLICKS_PER_SESSION:
                            break

                        # Wait between clicks
                        between_wait = random.uniform(
                            self.TIME_BETWEEN_CLICKS_MIN,
                            self.TIME_BETWEEN_CLICKS_MAX,
                        )
                        self.logger.info(f"[SLOW] Waiting {between_wait:.0f}s between clicks")
                        time.sleep(between_wait)
                        continue
                    except Exception as e:
                        self.logger.debug(f"ActionChains click failed: {e}")
            except Exception as e:
                self.logger.debug(f"Container strategy error: {e}")

            # === Try iframe ===
            try:
                iframes = self.client.driver.find_elements(
                    By.CSS_SELECTOR,
                    'iframe[src*="highrevenueformat"], '
                    'iframe[src*="effectivecpmnetwork"], '
                    'iframe[src*="highperformanceformat"]'
                )
                target = None
                for f in iframes:
                    fid = f.get_attribute('id') or str(id(f))
                    if fid not in tried_iframes and f.is_displayed():
                        target = f
                        tried_iframes.add(fid)
                        break

                if target:
                    self.client.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center', behavior:'smooth'});",
                        target
                    )
                    time.sleep(random.uniform(2.0, 3.5))

                    try:
                        actions = ActionChains(self.client.driver)
                        actions.move_to_element(target)
                        actions.pause(random.uniform(0.3, 0.7))
                        actions.click(target)
                        actions.perform()
                        clicked += 1
                        self.ads_clicked += 1
                        self.logger.info(f"[SLOW] ✅ Clicked iframe (total: {clicked})")

                        post_wait = random.uniform(
                            self.TIME_AFTER_CLICK_MIN,
                            self.TIME_AFTER_CLICK_MAX,
                        )
                        self.logger.info(f"[SLOW] Waiting {post_wait:.0f}s after click")
                        time.sleep(post_wait)
                        self._close_extra_tabs()

                        if clicked >= self.MAX_AD_CLICKS_PER_SESSION:
                            break

                        between_wait = random.uniform(
                            self.TIME_BETWEEN_CLICKS_MIN,
                            self.TIME_BETWEEN_CLICKS_MAX,
                        )
                        self.logger.info(f"[SLOW] Waiting {between_wait:.0f}s between clicks")
                        time.sleep(between_wait)
                    except Exception as e:
                        self.logger.debug(f"ActionChains iframe click failed: {e}")
            except Exception as e:
                self.logger.debug(f"Iframe strategy error: {e}")

            # If nothing worked this attempt, wait and try again
            if clicked == 0 and attempt < self.MAX_AD_CLICKS_PER_SESSION - 1:
                retry_wait = random.uniform(8, 15)
                self.logger.info(f"[SLOW] No click this attempt - waiting {retry_wait:.0f}s")
                time.sleep(retry_wait)

        self.logger.info(f"[SLOW] Sequence done: {clicked} clicks | {self.click_attempts} attempts")

    # ============================================================
    # PHASE 8: Maybe visit internal link (50% chance)
    # ============================================================
    def _maybe_visit_internal_link(self):
        """Visit ONE internal link if the mood strikes (50%)."""
        from selenium.webdriver.common.by import By

        if random.random() > 0.5:
            self.logger.info("[LINK] Skipping internal link this session")
            return

        try:
            selectors = [
                'article a:not([href^="#"])',
                'h2 a',
                '.post-title a',
            ]
            for selector in selectors:
                links = self.client.driver.find_elements(By.CSS_SELECTOR, selector)
                if not links:
                    continue

                link = random.choice(links[:3])
                href = link.get_attribute('href') or ''
                if not href or 'forjo.tech' not in href:
                    continue

                self.logger.info(f"[LINK] Visiting: {href[:60]}")
                link.click()
                time.sleep(random.uniform(5, 10))

                # Read on new page briefly
                for _ in range(random.randint(2, 4)):
                    self.client.driver.execute_script(
                        f"window.scrollBy({{top: {random.randint(200, 500)}, behavior: 'smooth'}});"
                    )
                    time.sleep(random.uniform(3, 6))

                # Go back
                self.client.driver.back()
                time.sleep(random.uniform(3, 5))
                self.internal_clicks = 1
                break
        except Exception as e:
            self.logger.debug(f"Internal link error: {e}")

    # ============================================================
    # PHASE 9: Final Dwell
    # ============================================================
    def _final_dwell(self):
        """Final dwell with slow, natural behavior."""
        try:
            duration = random.randint(self.DWELL_TIME_MIN, self.DWELL_TIME_MAX)
            self.logger.info(f"[DWELL] Final dwell for {duration}s...")
            start = time.time()
            last_scroll = time.time()

            while time.time() - start < duration:
                elapsed = time.time() - start

                # Slow scroll every 10-20 seconds
                if time.time() - last_scroll > random.uniform(10, 20):
                    try:
                        pixels = random.randint(200, 500)
                        self.client.driver.execute_script(
                            f"window.scrollBy({{top: {pixels}, behavior: 'smooth'}});"
                        )
                        # Occasional scroll back up
                        if random.random() < 0.3:
                            time.sleep(random.uniform(1, 2))
                            self.client.driver.execute_script(
                                f"window.scrollBy({{top: -{random.randint(100, 300)}, behavior: 'smooth'}});"
                            )
                        last_scroll = time.time()
                    except Exception:
                        pass

                # Small pause
                time.sleep(random.uniform(2, 5))

            self.dwell_time = int(time.time() - start)
            self.logger.info(f"[DWELL] Complete ({self.dwell_time}s)")
        except Exception as e:
            self.logger.debug(f"Dwell error: {e}")
            self.dwell_time = 180

    # ============================================================
    # WAIT FOR ADS
    # ============================================================
    def _wait_for_ads(self):
        from selenium.webdriver.common.by import By
        selectors = [
            'iframe[src*="highrevenueformat"]',
            'iframe[src*="effectivecpmnetwork"]',
            'iframe[src*="profitableratecpmnetwork"]',
            'iframe[src*="highperformanceformat"]',
            'div[id^="container-"]',
            'ins.adsbygoogle',
        ]
        self.logger.info(f"[ADS] Polling for ads (up to {self.ADS_WAIT_MAX}s)...")
        start = time.time()
        while time.time() - start < self.ADS_WAIT_MAX:
            for selector in selectors:
                try:
                    elements = self.client.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        self.logger.info(f"[ADS] Found: {selector} ({len(elements)}x)")
                        return True
                except Exception:
                    continue
            time.sleep(2.0)
        self.logger.warning(f"[ADS] No ads found after {self.ADS_WAIT_MAX}s")
        return False

    # ============================================================
    # CLOSE EXTRA TABS
    # ============================================================
    def _close_extra_tabs(self):
        try:
            handles = self.client.driver.window_handles
            if len(handles) > 1:
                main = handles[0]
                for handle in handles[1:]:
                    try:
                        self.client.driver.switch_to.window(handle)
                        time.sleep(random.uniform(2.0, 4.0))
                        self.client.driver.close()
                    except Exception:
                        continue
                try:
                    self.client.driver.switch_to.window(main)
                except Exception:
                    pass
                self.logger.info(f"[TABS] Closed {len(handles) - 1} extra tabs")
        except Exception as e:
            self.logger.debug(f"Tab close error: {e}")

    # ============================================================
    # PROXY
    # ============================================================
    def _pick_proxy(self):
        if os.environ.get('DISABLE_PROXIES', 'false').lower() == 'true':
            return None
        if os.environ.get('USE_PROXY_WITH_BROWSER', 'false').lower() != 'true':
            return None
        if self._proxy_provider is None:
            self._proxy_provider = BrowserProxyProvider()
        return self._proxy_provider.pick()

    # ============================================================
    # SESSION STARTERS
    # ============================================================
    def _start_browserstack(self, proxy=None):
        username = os.environ.get('BROWSERSTACK_USERNAME', '').strip()
        access_key = os.environ.get('BROWSERSTACK_ACCESS_KEY', '').strip()
        self.client = BrowserStackClient(username, access_key)
        browser, os_name, os_version = random.choice(self.BROWSERSTACK_BROWSERS)
        self.logger.info(f"BrowserStack: {browser} on {os_name} {os_version}")
        return self.client.start_session(
            url=self.target_url,
            browser=browser,
            os_name=os_name,
            os_version=os_version,
            proxy=proxy,
            use_local=False,
            mobile=self.USE_MOBILE,
        )

    def _start_local(self, proxy=None):
        self.client = LocalBrowserClient()
        self.logger.info(f"Local Chrome (Mobile: {self.USE_MOBILE})")
        return self.client.start_session(
            url=self.target_url,
            headless=True,
            proxy=proxy,
            mobile=self.USE_MOBILE,
        )

    def handle_error(self, failure):
        self.logger.error(f"{failure.request.url} | {failure.value}")

    def closed(self, reason):
        self.logger.info(
            f"Closed ({reason}) | ads={self.ads_clicked} "
            f"attempts={self.click_attempts} read={self.reading_time}s dwell={self.dwell_time}s"
        )
