# spiders/browserstack_spider.py
# Advanced Adsterra + Monetag with human-like behavior
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
    # Aggressive settings for max clicks
    # ============================================================
    AD_CLICK_PROBABILITY = 1.0
    MAX_AD_CLICKS_PER_SESSION = 5
    DWELL_TIME_MIN = 90
    DWELL_TIME_MAX = 150
    INTERNAL_LINKS_MIN = 2
    INTERNAL_LINKS_MAX = 4
    SCROLL_MIN = 8
    SCROLL_MAX = 15
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

            # 1) Initial scroll to trigger lazy-loaded ads
            self._random_scroll()

            # 2) Poll for ad elements (up to 40s)
            self.ads_detected_in_dom = self._wait_for_ads()

            # 3) Trigger Monetag (any click)
            self._trigger_monetag()

            # 4) Aggressive ad clicking
            self._click_ads_aggressive()

            # 5) Fill forms
            self.forms_filled = self.client.fill_form()

            # 6) Internal links (triggers ad refresh)
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
                f"attempts={self.click_attempts} detected={self.ads_detected_in_dom} "
                f"dwell={self.dwell_time}s scrolls={self.scroll_count}"
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
            'proxy_used': self.proxy_used,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    # ============================================================
    # Human-like mouse movement
    # ============================================================
    def _human_mouse_move(self, target_element):
        from selenium.webdriver.common.action_chains import ActionChains
        try:
            actions = ActionChains(self.client.driver)
            actions.move_to_element_with_offset(target_element, random.randint(-10, 10), random.randint(-10, 10))
            actions.pause(random.uniform(0.2, 0.5))
            actions.move_to_element(target_element)
            actions.perform()
            time.sleep(random.uniform(0.1, 0.3))
        except Exception as e:
            self.logger.debug(f"Human mouse move failed: {e}")

    # ============================================================
    # WAIT FOR ADS (Polling)
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
    # AGGRESSIVE AD CLICKING (8 strategies)
    # ============================================================
    def _click_ads_aggressive(self):
        from selenium.webdriver.common.by import By

        max_clicks = self.MAX_AD_CLICKS_PER_SESSION
        self.logger.info(f"Aggressive ad clicking: up to {max_clicks} clicks")

        clicked = 0

        # --- Script 1: Adsterra Native Bar ---
        js_native = """
        (() => {
            const containers = document.querySelectorAll('[id^="container-"]');
            if (containers.length === 0) return null;
            const c = containers[Math.floor(Math.random() * containers.length)];
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
                ['mousedown','mouseup','click'].forEach(evt => {
                    t.dispatchEvent(new MouseEvent(evt, {
                        bubbles: true, cancelable: true, view: window,
                        clientX: x, clientY: y, button: 0
                    }));
                });
                try { t.click(); } catch(e) {}
            }
            return 'native-' + c.id;
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
            ['mousedown','mouseup','click'].forEach(evt => {
                b.dispatchEvent(new MouseEvent(evt, {
                    bubbles: true, cancelable: true, view: window,
                    clientX: x, clientY: y, button: 0
                }));
            });
            try { b.click(); } catch(e) {}
            const el = document.elementFromPoint(x, y);
            if (el && el !== b) {
                try { el.click(); } catch(e) {}
            }
            return 'banner';
        })();
        """

        # --- Script 3: AdSense ---
        js_adsense = """
        (() => {
            const ins = document.querySelectorAll('ins.adsbygoogle');
            if (ins.length === 0) return null;
            const ad = ins[Math.floor(Math.random() * ins.length)];
            ad.scrollIntoView({block: 'center', behavior: 'smooth'});
            const rect = ad.getBoundingClientRect();
            const x = rect.left + rect.width / 2;
            const y = rect.top + rect.height / 2;
            const targets = [
                ad.querySelector('iframe'),
                document.elementFromPoint(x, y),
                ad,
            ].filter(t => t);
            for (const t of targets) {
                ['mousedown','mouseup','click'].forEach(evt => {
                    t.dispatchEvent(new MouseEvent(evt, {
                        bubbles: true, cancelable: true, view: window,
                        clientX: x, clientY: y, button: 0
                    }));
                });
                try { t.click(); } catch(e) {}
            }
            return 'adsense';
        })();
        """

        # --- Script 4: Any ad iframe ---
        js_any_iframe = """
        (() => {
            const iframes = Array.from(document.querySelectorAll('iframe')).filter(f => {
                const rect = f.getBoundingClientRect();
                return rect.width >= 50 && rect.height >= 30 &&
                       rect.width <= 900 && rect.height <= 800;
            });
            if (iframes.length === 0) return null;
            const b = iframes[Math.floor(Math.random() * iframes.length)];
            b.scrollIntoView({block: 'center'});
            const rect = b.getBoundingClientRect();
            const x = rect.left + rect.width / 2;
            const y = rect.top + rect.height / 2;
            ['mousedown','mouseup','click'].forEach(evt => {
                b.dispatchEvent(new MouseEvent(evt, {
                    bubbles: true, cancelable: true, view: window,
                    clientX: x, clientY: y, button: 0
                }));
            });
            try { b.click(); } catch(e) {}
            return 'iframe';
        })();
        """

        # --- Script 5: Any element with 'ad' ---
        js_any_ad = """
        (() => {
            const all = document.querySelectorAll('[class*="ad"],[id*="ad"],[class*="banner"],[class*="sponsor"]');
            if (all.length === 0) return null;
            const el = all[Math.floor(Math.random() * all.length)];
            const rect = el.getBoundingClientRect();
            if (rect.width < 100 || rect.height < 30) return null;
            el.scrollIntoView({block: 'center'});
            const x = rect.left + rect.width / 2;
            const y = rect.top + rect.height / 2;
            ['mousedown','mouseup','click'].forEach(evt => {
                el.dispatchEvent(new MouseEvent(evt, {
                    bubbles: true, cancelable: true, view: window,
                    clientX: x, clientY: y, button: 0
                }));
            });
            try { el.click(); } catch(e) {}
            return 'generic-ad';
        })();
        """

        # --- Script 6: Any link (Popunder) ---
        js_any_link = """
        (() => {
            const links = Array.from(document.querySelectorAll('a')).filter(a => {
                const href = a.getAttribute('href') || '';
                return href && !href.startsWith('#') && !href.startsWith('javascript:');
            });
            if (links.length === 0) return null;
            const link = links[Math.floor(Math.random() * links.length)];
            link.scrollIntoView({block: 'center'});
            const rect = link.getBoundingClientRect();
            const x = rect.left + rect.width / 2;
            const y = rect.top + rect.height / 2;
            ['mousedown','mouseup','click'].forEach(evt => {
                link.dispatchEvent(new MouseEvent(evt, {
                    bubbles: true, cancelable: true, view: window,
                    clientX: x, clientY: y, button: 0
                }));
            });
            return 'any-link';
        })();
        """

        # --- Script 7: Body center click ---
        js_body_click = """
        (() => {
            const x = window.innerWidth / 2;
            const y = window.innerHeight / 2;
            const el = document.elementFromPoint(x, y) || document.body;
            ['mousedown','mouseup','click'].forEach(evt => {
                el.dispatchEvent(new MouseEvent(evt, {
                    bubbles: true, cancelable: true, view: window,
                    clientX: x, clientY: y, button: 0
                }));
            });
            try { el.click(); } catch(e) {}
            return 'body-center';
        })();
        """

        # --- Script 8: Mass click ---
        js_mass_click = """
        (() => {
            const selectors = [
                'ins.adsbygoogle',
                'div[id^="container-"]',
                'iframe[src*="adsterra"]',
                'iframe[src*="monetag"]',
                'a[href*="adsterra"]',
                'a[href*="monetag"]',
                'a[href*="profitablerate"]',
                'a[href*="highrevenueformat"]',
            ];
            let clicked = 0;
            for (const sel of selectors) {
                const elements = document.querySelectorAll(sel);
                elements.forEach(el => {
                    try {
                        el.click();
                        clicked++;
                    } catch(e) {}
                });
            }
            return clicked > 0 ? 'mass-' + clicked : null;
        })();
        """

        strategies = [
            ('native', js_native),
            ('banners', js_banners),
            ('adsense', js_adsense),
            ('any_iframe', js_any_iframe),
            ('any_ad', js_any_ad),
            ('any_link', js_any_link),
            ('body_click', js_body_click),
            ('mass_click', js_mass_click),
        ]

        for round_num in range(3):
            if clicked >= max_clicks:
                break

            random.shuffle(strategies)
            for strategy_name, script_code in strategies:
                if clicked >= max_clicks:
                    break

                self.click_attempts += 1
                try:
                    if strategy_name in ['native', 'banners', 'adsense']:
                        try:
                            if strategy_name == 'native':
                                el = self.client.driver.find_element(By.CSS_SELECTOR, '[id^="container-"]')
                            elif strategy_name == 'banners':
                                el = self.client.driver.find_element(By.CSS_SELECTOR, 'iframe[src*="highrevenueformat"], iframe[src*="effectivecpmnetwork"]')
                            else:
                                el = self.client.driver.find_element(By.CSS_SELECTOR, 'ins.adsbygoogle')
                            self._human_mouse_move(el)
                        except Exception:
                            pass

                    result = self.client.driver.execute_script(script_code)
                    if result:
                        clicked += 1
                        self.ads_clicked += 1
                        self.logger.info(
                            f"[Round {round_num+1}] Clicked via {strategy_name}: {result}"
                        )

                        time.sleep(random.uniform(3.0, 6.0))
                        self._close_extra_tabs()
                        time.sleep(random.uniform(2.0, 4.0))

                        try:
                            self.client.driver.execute_script(
                                "window.scrollBy({top: 400, behavior: 'smooth'});"
                            )
                        except Exception:
                            pass
                        time.sleep(random.uniform(1.5, 3.0))

                except Exception as e:
                    self.logger.debug(f"[Round {round_num+1}] {strategy_name} failed: {e}")

        self.logger.info(
            f"Total clicks: {clicked} | Attempts: {self.click_attempts}"
        )

    def _close_extra_tabs(self):
        try:
            handles = self.client.driver.window_handles
            if len(handles) > 1:
                main = handles[0]
                for handle in handles[1:]:
                    self.client.driver.switch_to.window(handle)
                    time.sleep(random.uniform(2.0, 4.0))
                    try:
                        self.client.driver.execute_script("window.scrollBy(0, 300);")
                        time.sleep(1.5)
                    except Exception:
                        pass
                    self.client.driver.close()
                self.client.driver.switch_to.window(main)
                self.logger.info(f"Closed {len(handles) - 1} extra tabs")
        except Exception as e:
            self.logger.debug(f"Tab close error: {e}")

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
                    time.sleep(random.uniform(3.0, 6.0))

                    self.client.driver.execute_script("""
                        (() => {
                            const iframes = document.querySelectorAll('iframe');
                            for (const f of iframes) {
                                try { f.click(); } catch(e) {}
                            }
                        })();
                    """)
                    time.sleep(2.0)

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
            self.logger.info(f"Dwelling {duration}s...")
            start = time.time()
            while time.time() - start < duration:
                time.sleep(random.uniform(5, 12))
                if random.random() < 0.7:
                    try:
                        self.client.driver.execute_script(
                            f"window.scrollBy({{top: {random.randint(200, 500)}, behavior: 'smooth'}});"
                        )
                    except Exception:
                        pass

                if random.random() < 0.3:
                    try:
                        self.client.driver.execute_script("""
                            (() => {
                                const ads = document.querySelectorAll(
                                    'ins.adsbygoogle, div[id^="container-"], iframe[src*="highrevenueformat"]'
                                );
                                if (ads.length > 0) {
                                    const ad = ads[Math.floor(Math.random() * ads.length)];
                                    try { ad.click(); } catch(e) {}
                                }
                            })();
                        """)
                    except Exception:
                        pass

            self.dwell_time = int(time.time() - start)
        except Exception:
            self.dwell_time = 90

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
            f"Closed ({reason}) | ads={self.ads_clicked} attempts={self.click_attempts}"
        )
