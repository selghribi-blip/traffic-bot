# spiders/browserstack_spider.py
# Advanced Adsterra + Monetag with REAL mouse clicks + CDP clicks
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

    # NOTE: Firefox removed - does not support CDP anymore
    BROWSERSTACK_BROWSERS = [
        ('chrome', 'Windows', '11'),
        ('chrome', 'Windows', '10'),
        ('chrome', 'OS X', 'Ventura'),
        ('edge', 'Windows', '11'),
    ]

    # ============================================================
    # Aggressive settings
    # ============================================================
    USE_MOBILE = True
    AD_CLICK_PROBABILITY = 1.0
    MAX_AD_CLICKS_PER_SESSION = 5
    DWELL_TIME_MIN = 90
    DWELL_TIME_MAX = 150
    INTERNAL_LINKS_MIN = 2
    INTERNAL_LINKS_MAX = 4
    SCROLL_MIN = 8
    SCROLL_MAX = 15
    ADS_WAIT_MAX = 40
    CLICK_DURING_DWELL_INTERVAL = 6

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
        self._proxy_provider = None

    def start_requests(self):
        if not self.target_url.startswith(('http://', 'https://')):
            self.target_url = 'https://' + self.target_url

        self.logger.info(f"Starting browser bot for: {self.target_url}")
        self.logger.info(f"   Mode: {'BrowserStack' if self.use_browserstack else 'Local'}")
        self.logger.info(f"   Mobile emulation: {self.USE_MOBILE}")

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

            # 1) Initial scroll
            self._random_scroll()

            # 2) Poll for ads
            self.ads_detected_in_dom = self._wait_for_ads()

            # 3) Trigger Monetag
            self._trigger_monetag()

            # 4) Aggressive ad clicking
            self._click_ads_aggressive()

            # 5) Fill forms
            self.forms_filled = self.client.fill_form()

            # 6) Internal links
            self._click_internal_links()

            # 7) Dwell (with periodic clicks)
            self._dwell()

            try:
                fname = f"bs_{int(datetime.now(timezone.utc).timestamp())}.png"
                self.client.take_screenshot(fname)
            except Exception:
                pass

            status = 'success'
            self.logger.info(
                f"Visit successful | ads={self.ads_clicked} "
                f"attempts={self.click_attempts} detected={self.ads_detected_in_dom} "
                f"mobile={getattr(self.client, 'is_mobile', False)} dwell={self.dwell_time}s"
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
    # Human-like mouse movement
    # ============================================================
    def _human_mouse_move(self, target_element):
        from selenium.webdriver.common.action_chains import ActionChains
        try:
            if getattr(self.client, 'is_mobile', False):
                from selenium.webdriver.common.actions.action_builder import ActionBuilder
                from selenium.webdriver.common.actions.pointer_input import PointerInput
                from selenium.webdriver.common.actions import interaction
                touch = PointerInput(interaction.POINTER_TOUCH, "touch")
                actions = ActionBuilder(self.client.driver, mouse=touch)
                actions.pointer_action.move_to(target_element)
                actions.pointer_action.pointer_down()
                actions.pointer_action.pause(random.uniform(0.05, 0.15))
                actions.pointer_action.pointer_up()
                actions.perform()
            else:
                actions = ActionChains(self.client.driver)
                actions.move_to_element_with_offset(
                    target_element, random.randint(-10, 10), random.randint(-10, 10)
                )
                actions.pause(random.uniform(0.2, 0.5))
                actions.move_to_element(target_element)
                actions.perform()
            time.sleep(random.uniform(0.1, 0.3))
        except Exception as e:
            self.logger.debug(f"Human mouse move failed: {e}")

    # ============================================================
    # CDP-level Real Mouse Click (bypasses isTrusted check)
    # ============================================================
    def _cdp_click_at(self, x, y):
        """Real browser-level click via CDP. Bypasses event.isTrusted=false."""
        try:
            self.client.driver.execute_cdp_cmd('Input.dispatchMouseEvent', {
                'type': 'mouseMoved',
                'x': int(x), 'y': int(y),
                'button': 'none', 'clickCount': 0,
            })
            time.sleep(random.uniform(0.05, 0.15))
            self.client.driver.execute_cdp_cmd('Input.dispatchMouseEvent', {
                'type': 'mousePressed',
                'x': int(x), 'y': int(y),
                'button': 'left', 'clickCount': 1,
            })
            time.sleep(random.uniform(0.05, 0.12))
            self.client.driver.execute_cdp_cmd('Input.dispatchMouseEvent', {
                'type': 'mouseReleased',
                'x': int(x), 'y': int(y),
                'button': 'left', 'clickCount': 1,
            })
            return True
        except Exception as e:
            self.logger.debug(f"CDP click failed: {e}")
            return False

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
            'iframe[src*="doubleclick"]',
            'iframe[src*="googlesyndication"]',
        ]
        self.logger.info(f"Polling for ads (up to {self.ADS_WAIT_MAX}s)...")
        start = time.time()
        while time.time() - start < self.ADS_WAIT_MAX:
            for selector in selectors:
                try:
                    elements = self.client.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        self.logger.info(f"Ad element found: {selector} ({len(elements)}x)")
                        return True
                except Exception:
                    continue
            try:
                self.client.driver.execute_script(
                    f"window.scrollBy({{top: {random.randint(200, 500)}, behavior: 'smooth'}});"
                )
            except Exception:
                pass
            time.sleep(2.0)
        self.logger.warning(f"No ads found after {self.ADS_WAIT_MAX}s polling")
        return False

    # ============================================================
    # TRIGGER MONETAG
    # ============================================================
    def _trigger_monetag(self):
        try:
            self.client.driver.execute_script("""
                (() => {
                    const x = window.innerWidth / 2;
                    const y = window.innerHeight / 2;
                    const el = document.elementFromPoint(x, y) || document.body;
                    ['mousedown', 'mouseup', 'click'].forEach(type => {
                        el.dispatchEvent(new MouseEvent(type, {
                            bubbles: true, cancelable: true, view: window,
                            clientX: x, clientY: y, button: 0
                        }));
                    });
                    try { el.click(); } catch(e) {}
                })();
            """)
            time.sleep(2)
            self.logger.info("Monetag triggered via center click")
        except Exception as e:
            self.logger.debug(f"Monetag trigger failed: {e}")

    # ============================================================
    # AGGRESSIVE AD CLICKING - IMPROVED with proper attempt counting
    # ============================================================
    def _click_ads_aggressive(self):
        """
        Multi-layer ad clicking with proper fallbacks.
        Attempts counted BEFORE each try, so we always see real attempts.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.action_chains import ActionChains

        max_clicks = self.MAX_AD_CLICKS_PER_SESSION
        self.logger.info(f"Aggressive clicking: up to {max_clicks} clicks")

        clicked = 0
        containers = []
        iframes = []

        # ============================================================
        # Collect all ad elements upfront
        # ============================================================
        try:
            containers = self.client.driver.find_elements(
                By.CSS_SELECTOR, 'div[id^="container-"]'
            )
            self.logger.info(f"Found {len(containers)} containers")
        except Exception as e:
            self.logger.debug(f"Container search failed: {e}")

        try:
            iframes = self.client.driver.find_elements(
                By.CSS_SELECTOR,
                'iframe[src*="highrevenueformat"], '
                'iframe[src*="effectivecpmnetwork"], '
                'iframe[src*="highperformanceformat"], '
                'iframe[src*="profitableratecpmnetwork"]'
            )
            self.logger.info(f"Found {len(iframes)} iframes")
        except Exception as e:
            self.logger.debug(f"Iframe search failed: {e}")

        # ============================================================
        # Strategy 1: Real ActionChains click on containers
        # ============================================================
        for idx, c in enumerate(containers[:3]):
            if clicked >= max_clicks:
                break

            self.click_attempts += 1
            try:
                if not c.is_displayed():
                    self.logger.debug(f"Container {idx} not displayed")
                    continue

                self.client.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center', behavior:'smooth'});", c
                )
                time.sleep(random.uniform(0.8, 1.5))

                # Try ActionChains first
                try:
                    actions = ActionChains(self.client.driver)
                    actions.move_to_element(c)
                    actions.pause(random.uniform(0.2, 0.4))
                    actions.click(c)
                    actions.perform()
                    clicked += 1
                    self.ads_clicked += 1
                    self.logger.info(f"[S1] ActionChains click on container-{idx}")
                    time.sleep(random.uniform(2.0, 4.0))
                    self._close_extra_tabs()
                    continue
                except Exception as e:
                    self.logger.debug(f"ActionChains failed on container: {e}")

                # Fallback: CDP click on container center
                try:
                    rect = self.client.driver.execute_script(
                        "return arguments[0].getBoundingClientRect();", c
                    )
                    cx = rect['left'] + rect['width'] / 2
                    cy = rect['top'] + rect['height'] / 2
                    if self._cdp_click_at(cx, cy):
                        clicked += 1
                        self.ads_clicked += 1
                        self.logger.info(f"[S1] CDP click on container-{idx}")
                        time.sleep(random.uniform(2.0, 4.0))
                        self._close_extra_tabs()
                except Exception as e:
                    self.logger.debug(f"CDP click failed on container: {e}")

            except Exception as e:
                self.logger.debug(f"Container {idx} error: {e}")

        # ============================================================
        # Strategy 2: Real click on iframes
        # ============================================================
        for idx, f in enumerate(iframes[:3]):
            if clicked >= max_clicks:
                break

            self.click_attempts += 1
            try:
                if not f.is_displayed():
                    continue

                self.client.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", f
                )
                time.sleep(random.uniform(0.6, 1.2))

                # Try ActionChains
                try:
                    actions = ActionChains(self.client.driver)
                    actions.move_to_element(f)
                    actions.pause(random.uniform(0.2, 0.4))
                    actions.click(f)
                    actions.perform()
                    clicked += 1
                    self.ads_clicked += 1
                    self.logger.info(f"[S2] ActionChains click on iframe-{idx}")
                    time.sleep(random.uniform(2.0, 4.0))
                    self._close_extra_tabs()
                    continue
                except Exception as e:
                    self.logger.debug(f"ActionChains failed on iframe: {e}")

                # Fallback: CDP click
                try:
                    rect = self.client.driver.execute_script(
                        "return arguments[0].getBoundingClientRect();", f
                    )
                    cx = rect['left'] + rect['width'] / 2
                    cy = rect['top'] + rect['height'] / 2
                    if self._cdp_click_at(cx, cy):
                        clicked += 1
                        self.ads_clicked += 1
                        self.logger.info(f"[S2] CDP click on iframe-{idx}")
                        time.sleep(random.uniform(2.0, 4.0))
                        self._close_extra_tabs()
                except Exception as e:
                    self.logger.debug(f"CDP click failed on iframe: {e}")

            except Exception as e:
                self.logger.debug(f"Iframe {idx} error: {e}")

        # ============================================================
        # Strategy 3: CDP click on any ad-like element (loop)
        # ============================================================
        safety_counter = 0
        while clicked < max_clicks and safety_counter < 10:
            safety_counter += 1
            self.click_attempts += 1
            try:
                pos = self.client.driver.execute_script("""
                    (() => {
                        const sels = [
                            'ins.adsbygoogle',
                            'div[id^="container-"]',
                            'iframe[src*="highrevenueformat"]',
                            'iframe[src*="effectivecpmnetwork"]',
                            'iframe[src*="highperformanceformat"]',
                        ];
                        const all = [];
                        for (const sel of sels) {
                            document.querySelectorAll(sel).forEach(el => {
                                const rect = el.getBoundingClientRect();
                                if (rect.width >= 50 && rect.height >= 30 &&
                                    rect.top >= 0 && rect.top <= window.innerHeight) {
                                    all.push({
                                        x: rect.left + rect.width / 2,
                                        y: rect.top + rect.height / 2,
                                        tag: el.tagName
                                    });
                                }
                            });
                        }
                        if (all.length === 0) return null;
                        return all[Math.floor(Math.random() * all.length)];
                    })();
                """)

                if not pos:
                    self.logger.debug("No visible ad element for CDP")
                    break

                if self._cdp_click_at(pos['x'], pos['y']):
                    clicked += 1
                    self.ads_clicked += 1
                    self.logger.info(
                        f"[S3] CDP click at ({int(pos['x'])}, {int(pos['y'])}) on {pos['tag']}"
                    )
                    time.sleep(random.uniform(2.0, 4.0))
                    self._close_extra_tabs()
                else:
                    time.sleep(1.0)

            except Exception as e:
                self.logger.debug(f"CDP strategy error: {e}")
                break

        # ============================================================
        # Strategy 4: JS mass click (fallback)
        # ============================================================
        if clicked < max_clicks:
            self.click_attempts += 1
            try:
                js_mass = """
                (() => {
                    const containers = document.querySelectorAll(
                        'div[id^="container-"], ins.adsbygoogle'
                    );
                    let total = 0;
                    containers.forEach(c => {
                        const rect = c.getBoundingClientRect();
                        if (rect.width < 50 || rect.height < 30) return;
                        c.scrollIntoView({block: 'center'});
                        const x = rect.left + rect.width / 2;
                        const y = rect.top + rect.height / 2;
                        const targets = [
                            document.elementFromPoint(x, y),
                            c.querySelector('iframe'),
                            c.querySelector('a'),
                            c.firstElementChild,
                            c,
                        ].filter(t => t);
                        targets.forEach(t => {
                            ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(evt => {
                                t.dispatchEvent(new PointerEvent(evt, {
                                    bubbles: true, cancelable: true, view: window,
                                    clientX: x, clientY: y, button: 0,
                                    pointerType: 'touch', isPrimary: true
                                }));
                                t.dispatchEvent(new MouseEvent(evt, {
                                    bubbles: true, cancelable: true, view: window,
                                    clientX: x, clientY: y, button: 0
                                }));
                            });
                            try { t.click(); total++; } catch(e) {}
                        });
                    });
                    return total;
                })();
                """
                result = self.client.driver.execute_script(js_mass)
                if result and result > 0:
                    clicked += 1
                    self.ads_clicked += 1
                    self.logger.info(f"[S4] JS mass click: {result} elements")
                    time.sleep(random.uniform(2.0, 4.0))
                    self._close_extra_tabs()
            except Exception as e:
                self.logger.debug(f"JS mass click failed: {e}")

        self.logger.info(
            f"Total clicks: {clicked} | Attempts: {self.click_attempts}"
        )

    def _close_extra_tabs(self):
        try:
            handles = self.client.driver.window_handles
            if len(handles) > 1:
                main = handles[0]
                for handle in handles[1:]:
                    try:
                        self.client.driver.switch_to.window(handle)
                        time.sleep(random.uniform(1.5, 3.0))
                        try:
                            self.client.driver.execute_script("window.scrollBy(0, 400);")
                            time.sleep(1.0)
                        except Exception:
                            pass
                        self.client.driver.close()
                    except Exception:
                        continue
                try:
                    self.client.driver.switch_to.window(main)
                except Exception:
                    pass
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
                pixels = random.randint(300, 700)
                self.client.driver.execute_script(
                    f"window.scrollBy({{top: {pixels}, behavior: 'smooth'}});"
                )
                time.sleep(random.uniform(0.7, 1.8))
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

                    self._human_mouse_move(link)
                    self.client.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", link
                    )
                    time.sleep(random.uniform(0.8, 1.5))
                    link.click()
                    time.sleep(random.uniform(4.0, 8.0))

                    self.client.driver.execute_script("window.scrollBy(0, 500);")
                    time.sleep(random.uniform(2.0, 4.0))

                    # Click ads on new page
                    self._click_ads_aggressive()

                    clicked += 1
                    self.internal_clicks += 1
                    self.client.driver.back()
                    time.sleep(random.uniform(2.0, 4.0))
                except Exception:
                    continue
        except Exception:
            pass

    # ============================================================
    # DWELL with periodic real clicks
    # ============================================================
    def _dwell(self):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.action_chains import ActionChains

        try:
            duration = random.randint(self.DWELL_TIME_MIN, self.DWELL_TIME_MAX)
            self.logger.info(f"Dwelling {duration}s with periodic real clicks...")
            start = time.time()
            last_click = 0

            while time.time() - start < duration:
                time.sleep(random.uniform(3, 7))

                # Scroll
                try:
                    self.client.driver.execute_script(
                        f"window.scrollBy({{top: {random.randint(200, 600)}, behavior: 'smooth'}});"
                    )
                except Exception:
                    pass

                # Periodic real click every CLICK_DURING_DWELL_INTERVAL seconds
                if time.time() - last_click > self.CLICK_DURING_DWELL_INTERVAL:
                    try:
                        containers = self.client.driver.find_elements(
                            By.CSS_SELECTOR, 'div[id^="container-"]'
                        )
                        for c in containers[:2]:
                            try:
                                if not c.is_displayed():
                                    continue
                                actions = ActionChains(self.client.driver)
                                actions.move_to_element(c)
                                actions.pause(random.uniform(0.1, 0.3))
                                actions.click(c)
                                actions.perform()
                                self.ads_clicked += 1
                                self.logger.info("Dwell real click on container")
                                time.sleep(random.uniform(1.5, 3.0))
                                self._close_extra_tabs()
                                break
                            except Exception:
                                continue
                    except Exception:
                        pass
                    last_click = time.time()

            self.dwell_time = int(time.time() - start)
        except Exception as e:
            self.logger.debug(f"Dwell error: {e}")
            self.dwell_time = 90

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
            f"Closed ({reason}) | ads={self.ads_clicked} attempts={self.click_attempts}"
        )
