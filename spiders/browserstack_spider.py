# spiders/browserstack_spider.py
# Adsterra + Monetag optimized with ad detection
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
        ('firefox', 'Windows', '11'),
        ('edge', 'Windows', '11'),
    ]

    # ============================================================
    # Optimized settings for revenue
    # ============================================================
    AD_CLICK_PROBABILITY = 0.95
    MAX_AD_CLICKS_PER_SESSION = 3
    DWELL_TIME_MIN = 60
    DWELL_TIME_MAX = 120
    INTERNAL_LINKS_MIN = 2
    INTERNAL_LINKS_MAX = 3
    SCROLL_MIN = 5
    SCROLL_MAX = 10
    ADS_WAIT = 15  # Wait for Adsterra/Monetag to load

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

        self.logger.info(f"Starting browser bot for: {self.target_url}")
        self.logger.info(f"   Mode: {'BrowserStack' if self.use_browserstack else 'Local'}")

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

            # 1) Initial scroll to load ads
            self._random_scroll()

            # 2) Wait for Adsterra/Monetag
            time.sleep(self.ADS_WAIT)

            # 3) Trigger Monetag (any click)
            self._trigger_monetag()

            # 4) Ad clicks (95% probability)
            if random.random() < self.AD_CLICK_PROBABILITY:
                self._click_adsterra_monetag()
            else:
                self.logger.info("Ad click skipped (probability)")

            # 5) Fill forms
            self.forms_filled = self.client.fill_form()

            # 6) Internal links
            self._click_internal_links()

            # 7) Dwell
            self._dwell()

            try:
                fname = f"bs_{int(datetime.now(timezone.utc).timestamp())}.png"
                self.client.take_screenshot(fname)
            except Exception:
                pass

            status = 'success'
            self.logger.info(
                f"Visit successful | ads={self.ads_clicked} "
                f"forms={self.forms_filled} dwell={self.dwell_time}s "
                f"scrolls={self.scroll_count} internal={self.internal_clicks}"
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
            'forms_filled': self.forms_filled,
            'dwell_time': self.dwell_time,
            'scroll_count': self.scroll_count,
            'internal_clicks': self.internal_clicks,
            'captcha': self.captcha_detected,
            'mode': 'browserstack' if self.use_browserstack else 'local',
            'proxy_used': self.proxy_used,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    # ============================================================
    # TRIGGER MONETAG (Service Worker)
    # ============================================================
    def _trigger_monetag(self):
        """Monetag is triggered by ANY user click. Simulate one."""
        try:
            self.client.driver.execute_script("""
                (() => {
                    const x = window.innerWidth / 2;
                    const y = window.innerHeight / 2;
                    const el = document.elementFromPoint(x, y);
                    if (el) {
                        el.dispatchEvent(new MouseEvent('click', {
                            bubbles: true, cancelable: true, view: window,
                            clientX: x, clientY: y, button: 0
                        }));
                        try { el.click(); } catch(e) {}
                        return true;
                    }
                    return false;
                })();
            """)
            time.sleep(2)
            self.logger.info("Monetag triggered via center click")
        except Exception as e:
            self.logger.debug(f"Monetag trigger failed: {e}")

    # ============================================================
    # ADSTERRA + MONETAG CLICKING
    # ============================================================
    def _click_adsterra_monetag(self):
        """
        Clicks Adsterra and Monetag ads.
        1) Wait for ad to appear in DOM (up to 8s)
        2) Try 5 JS scripts in random order
        3) Close any new tab (Popunder)
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        # ============================================================
        # 1) Wait for ad in DOM
        # ============================================================
        self.logger.info("Waiting for ads to appear in DOM...")
        ad_found = False

        ad_selectors = [
            'iframe[src*="highrevenueformat"]',
            'iframe[src*="effectivecpmnetwork"]',
            'iframe[src*="profitableratecpmnetwork"]',
            'iframe[src*="highperformanceformat"]',
            'div[id^="container-"]',
        ]

        for selector in ad_selectors:
            try:
                WebDriverWait(self.client.driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                self.logger.info(f"Ad detected: {selector}")
                ad_found = True
                break
            except Exception:
                continue

        if not ad_found:
            self.logger.warning("No ad elements found in DOM after 8s wait")

        # ============================================================
        # 2) Ad clicks
        # ============================================================
        max_clicks = random.randint(1, self.MAX_AD_CLICKS_PER_SESSION)
        self.logger.info(f"Adsterra/Monetag clicking: up to {max_clicks} ads")

        clicked = 0

        # --- Script 1: Adsterra Native Bar ---
        js_native = """
        (() => {
            const containers = document.querySelectorAll('[id^="container-"]');
            if (containers.length === 0) return null;
            const c = containers[Math.floor(Math.random() * containers.length)];
            if (c.offsetWidth < 100 || c.offsetHeight < 50) return null;
            c.scrollIntoView({block: 'center', behavior: 'smooth'});
            const rect = c.getBoundingClientRect();
            const x = rect.left + rect.width / 2;
            const y = rect.top + rect.height / 2;
            const targets = [
                document.elementFromPoint(x, y),
                c.querySelector('iframe'),
                c.querySelector('a'),
                c.firstElementChild,
                c,
            ].filter(t => t);
            for (const t of targets) {
                try {
                    t.click();
                    t.dispatchEvent(new MouseEvent('click', {
                        bubbles: true, cancelable: true, view: window,
                        clientX: x, clientY: y, button: 0
                    }));
                    return 'native-' + c.id;
                } catch(e) {}
            }
            return null;
        })();
        """

        # --- Script 2: Adsterra Banners ---
        js_banners = """
        (() => {
            const iframes = document.querySelectorAll('iframe');
            const banners = [];
            for (const f of iframes) {
                const src = (f.src || '').toLowerCase();
                if (src.includes('highrevenueformat') ||
                    src.includes('profitableratecpmnetwork') ||
                    src.includes('effectivecpmnetwork') ||
                    src.includes('highperformanceformat')) {
                    banners.push(f);
                }
            }
            if (banners.length === 0) return null;
            const b = banners[Math.floor(Math.random() * banners.length)];
            b.scrollIntoView({block: 'center', behavior: 'smooth'});
            const rect = b.getBoundingClientRect();
            const x = rect.left + rect.width / 2;
            const y = rect.top + rect.height / 2;
            const evt = new MouseEvent('click', {
                bubbles: true, cancelable: true, view: window,
                clientX: x, clientY: y, button: 0
            });
            try {
                b.click();
                b.dispatchEvent(evt);
            } catch(e) {}
            const el = document.elementFromPoint(x, y);
            if (el && el !== b) {
                try { el.click(); el.dispatchEvent(evt); } catch(e) {}
            }
            return 'banner-' + (b.src || '').slice(0, 50);
        })();
        """

        # --- Script 3: Monetag ---
        js_monetag = """
        (() => {
            const meta = document.querySelector('meta[name="monetag"]');
            const hasMonetag = meta || (window.location.href.includes('quge5') ||
                                document.documentElement.innerHTML.includes('quge5.com'));
            if (!hasMonetag) return null;

            const clickable = document.querySelectorAll(
                'a[href*="quge5"], a[href*="monetag"], '
                + '[class*="monetag"], [id*="monetag"], '
                + '[data-zone="260812"], [data-zone="260829"]'
            );
            if (clickable.length === 0) return null;
            const el = clickable[Math.floor(Math.random() * clickable.length)];
            el.scrollIntoView({block: 'center'});
            const rect = el.getBoundingClientRect();
            const x = rect.left + rect.width / 2;
            const y = rect.top + rect.height / 2;
            const evt = new MouseEvent('click', {
                bubbles: true, cancelable: true, view: window,
                clientX: x, clientY: y, button: 0
            });
            try { el.click(); el.dispatchEvent(evt); return 'monetag'; } catch(e) {}
            return null;
        })();
        """

        # --- Script 4: Any ad iframe ---
        js_any_iframe = """
        (() => {
            const iframes = Array.from(document.querySelectorAll('iframe')).filter(f => {
                const rect = f.getBoundingClientRect();
                return rect.width >= 100 && rect.height >= 40 &&
                       rect.width <= 800 && rect.height <= 700;
            });
            if (iframes.length === 0) return null;
            const b = iframes[Math.floor(Math.random() * iframes.length)];
            b.scrollIntoView({block: 'center', behavior: 'smooth'});
            const rect = b.getBoundingClientRect();
            const x = rect.left + rect.width / 2;
            const y = rect.top + rect.height / 2;
            try {
                b.click();
                b.dispatchEvent(new MouseEvent('click', {
                    bubbles: true, cancelable: true, view: window,
                    clientX: x, clientY: y, button: 0
                }));
                return 'iframe';
            } catch(e) {}
            return null;
        })();
        """

        # --- Script 5: Any ad-sized element ---
        js_any_ad = """
        (() => {
            const all = document.querySelectorAll('*');
            const candidates = [];
            for (const el of all) {
                const rect = el.getBoundingClientRect();
                if (rect.width < 150 || rect.height < 40) continue;
                if (rect.width > 900 || rect.height > 700) continue;
                const cls = (el.className || '').toString().toLowerCase();
                const id = (el.id || '').toString().toLowerCase();
                if (cls.includes('ad') || id.includes('ad') ||
                    cls.includes('banner') || cls.includes('sponsor') ||
                    cls.includes('popunder') || cls.includes('container-')) {
                    candidates.push(el);
                }
            }
            if (candidates.length === 0) return null;
            const el = candidates[Math.floor(Math.random() * candidates.length)];
            el.scrollIntoView({block: 'center'});
            const rect = el.getBoundingClientRect();
            try {
                el.click();
                el.dispatchEvent(new MouseEvent('click', {
                    bubbles: true, cancelable: true, view: window,
                    clientX: rect.left + rect.width / 2,
                    clientY: rect.top + rect.height / 2,
                    button: 0
                }));
                return 'generic-ad';
            } catch(e) {}
            return null;
        })();
        """

        # ============================================================
        # 3) Run scripts in random order
        # ============================================================
        scripts = [
            ('native', js_native),
            ('banners', js_banners),
            ('monetag', js_monetag),
            ('any_iframe', js_any_iframe),
            ('any_ad', js_any_ad),
        ]
        random.shuffle(scripts)

        for script_name, script_code in scripts:
            if clicked >= max_clicks:
                break

            try:
                result = self.client.driver.execute_script(script_code)
                if result:
                    clicked += 1
                    self.ads_clicked += 1
                    self.logger.info(f"Ad clicked via {script_name}: {result}")

                    time.sleep(random.uniform(4.0, 8.0))
                    self._close_extra_tabs()
                    time.sleep(random.uniform(2.0, 4.0))

                    try:
                        self.client.driver.execute_script(
                            "window.scrollBy({top: 300, behavior: 'smooth'});"
                        )
                    except Exception:
                        pass
                    time.sleep(random.uniform(1.0, 2.0))
                else:
                    self.logger.debug(f"Script {script_name}: no ad found")

            except Exception as e:
                self.logger.debug(f"Script {script_name} failed: {e}")

        self.logger.info(f"Total ads clicked: {clicked}")

    def _close_extra_tabs(self):
        """Closes Adsterra Popunder tabs."""
        try:
            handles = self.client.driver.window_handles
            if len(handles) > 1:
                main = handles[0]
                for handle in handles[1:]:
                    self.client.driver.switch_to.window(handle)
                    time.sleep(random.uniform(2.0, 4.0))
                    self.client.driver.close()
                self.client.driver.switch_to.window(main)
                self.logger.info(f"Closed {len(handles) - 1} extra tabs")
        except Exception as e:
            self.logger.debug(f"Tab close error: {e}")

    # ============================================================
    # SCROLL
    # ============================================================
    def _random_scroll(self):
        try:
            count = random.randint(self.SCROLL_MIN, self.SCROLL_MAX)
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

    # ============================================================
    # INTERNAL LINKS
    # ============================================================
    def _click_internal_links(self):
        from selenium.webdriver.common.by import By
        try:
            count = random.randint(self.INTERNAL_LINKS_MIN, self.INTERNAL_LINKS_MAX)
            clicked = 0
            selectors = [
                'article a:not([href^="#"])',
                'h2 a',
                'h3 a',
                '.post-title a',
                '.entry-title a',
                'main a:not([href^="#"])',
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

    # ============================================================
    # DWELL
    # ============================================================
    def _dwell(self):
        try:
            duration = random.randint(self.DWELL_TIME_MIN, self.DWELL_TIME_MAX)
            self.logger.info(f"Dwelling {duration}s...")
            start = time.time()
            while time.time() - start < duration:
                time.sleep(random.uniform(5, 12))
                if random.random() < 0.6:
                    try:
                        self.client.driver.execute_script(
                            f"window.scrollBy({{top: {random.randint(200, 500)}, behavior: 'smooth'}});"
                        )
                    except Exception:
                        pass
            self.dwell_time = int(time.time() - start)
        except Exception:
            self.dwell_time = 60

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
        )

    def _start_local(self, proxy=None):
        self.client = LocalBrowserClient()
        self.logger.info("Local Chrome")
        return self.client.start_session(
            url=self.target_url,
            headless=True,
            proxy=proxy,
        )

    def handle_error(self, failure):
        self.logger.error(f"{failure.request.url} | {failure.value}")

    def closed(self, reason):
        self.logger.info(
            f"Closed ({reason}) | ads={self.ads_clicked} forms={self.forms_filled}"
        )
