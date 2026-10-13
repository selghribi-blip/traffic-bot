# utils/browserstack_client.py
import os
import time
import json
import random
import logging
import tempfile

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, WebDriverException,
    StaleElementReferenceException, ElementNotInteractableException,
)

logger = logging.getLogger(__name__)


class BezierMouse:
    @staticmethod
    def bezier_points(x1, y1, x2, y2, steps=25):
        cx1 = x1 + (x2 - x1) * random.uniform(0.2, 0.4) + random.randint(-50, 50)
        cy1 = y1 + (y2 - y1) * random.uniform(0.2, 0.4) + random.randint(-50, 50)
        cx2 = x1 + (x2 - x1) * random.uniform(0.6, 0.8) + random.randint(-50, 50)
        cy2 = y1 + (y2 - y1) * random.uniform(0.6, 0.8) + random.randint(-50, 50)
        points = []
        for i in range(steps + 1):
            t = i / steps
            x = ((1 - t) ** 3 * x1 + 3 * (1 - t) ** 2 * t * cx1 +
                 3 * (1 - t) * t ** 2 * cx2 + t ** 3 * x2)
            y = ((1 - t) ** 3 * y1 + 3 * (1 - t) ** 2 * t * cy1 +
                 3 * (1 - t) * t ** 2 * cy2 + t ** 3 * y2)
            points.append((int(x), int(y)))
        return points


class CDPSpoofer:
    @classmethod
    def apply(cls, driver, fp):
        try:
            if fp.get('timezone'):
                driver.execute_cdp_cmd('Emulation.setTimezoneOverride', {
                    'timezoneId': fp['timezone'],
                })
            if fp.get('locale'):
                driver.execute_cdp_cmd('Emulation.setLocaleOverride', {
                    'locale': fp['locale'],
                })
            if fp.get('user_agent'):
                driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    'userAgent': fp['user_agent'],
                    'platform': fp.get('platform', 'Win32'),
                })
            if fp.get('viewport'):
                vw, vh = fp['viewport']
                driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                    'width': vw, 'height': vh,
                    'deviceScaleFactor': 1, 'mobile': False,
                })
            driver.execute_cdp_cmd(
                'Page.addScriptToEvaluateOnNewDocument',
                {'source': cls._script(fp)},
            )
        except Exception as e:
            logger.debug(f"CDP spoofing partial: {e}")

    @staticmethod
    def _script(fp):
        wv = fp.get('webgl_vendor', '')
        wr = fp.get('webgl_renderer', '')
        hw = fp.get('hardware_concurrency', 8)
        dm = fp.get('device_memory', 8)
        langs = fp.get('langs', ['en-US', 'en'])
        platform = fp.get('platform', 'Win32')
        vendor = fp.get('vendor', 'Google Inc.')

        return f"""
        (() => {{
            Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});
            Object.defineProperty(navigator, 'platform', {{get: () => '{platform}'}});
            Object.defineProperty(navigator, 'vendor', {{get: () => '{vendor}'}});
            Object.defineProperty(navigator, 'language', {{get: () => '{langs[0]}'}});
            Object.defineProperty(navigator, 'languages', {{get: () => {json.dumps(langs)}}});
            Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {hw}}});
            Object.defineProperty(navigator, 'deviceMemory', {{get: () => {dm}}});
            Object.defineProperty(navigator, 'plugins', {{
                get: () => [
                    {{name: 'PDF Viewer'}},
                    {{name: 'Chrome PDF Viewer'}},
                    {{name: 'Chromium PDF Viewer'}},
                ],
            }});
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(p) {{
                if (p === 37445) return '{wv}';
                if (p === 37446) return '{wr}';
                return getParameter.call(this, p);
            }};
            const toDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function() {{
                const ctx = this.getContext('2d');
                if (ctx) {{
                    try {{
                        const imgData = ctx.getImageData(0, 0, this.width, this.height);
                        for (let i = 0; i < imgData.data.length; i += 100) {{
                            imgData.data[i] = imgData.data[i] ^ 1;
                        }}
                        ctx.putImageData(imgData, 0, 0);
                    }} catch(e) {{}}
                }}
                return toDataURL.apply(this, arguments);
            }};
            window.chrome = {{runtime: {{}}, loadTimes: function() {{}}, csi: function() {{}}}};
            const origQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (p) => (
                p.name === 'notifications'
                    ? Promise.resolve({{state: Notification.permission}})
                    : origQuery(p)
            );
        }})();
        """


class ResourceBlocker:
    BLOCK_ALWAYS = [
        'google-analytics.com', 'googletagmanager.com',
        'facebook.net', 'hotjar.com', 'clarity.ms',
    ]

    @classmethod
    def setup(cls, driver, mode='balanced'):
        if mode == 'off':
            return
        try:
            driver.execute_cdp_cmd('Network.enable', {})
            blocked = [f'*{d}*' for d in cls.BLOCK_ALWAYS]
            if mode == 'aggressive':
                blocked += [
                    '*.jpg*', '*.jpeg*', '*.png*', '*.gif*', '*.webp*',
                    '*.svg*', '*.ico*', '*.mp4*', '*.webm*', '*.mp3*',
                    '*.woff*', '*.woff2*', '*.ttf*', '*.otf*', '*.css*',
                ]
            driver.execute_cdp_cmd('Network.setBlockedURLs', {'urls': blocked})
        except Exception as e:
            logger.debug(f"Resource blocking failed: {e}")


class BrowserStackClient:
    AD_SELECTORS = [
        'ins.adsbygoogle', 'iframe[id*="google_ads"]',
        'iframe[src*="doubleclick"]', 'iframe[src*="googlesyndication"]',
        '.adsbygoogle', 'a[href*="adsterra"]', 'a[href*="monetag"]',
        'a[href*="propellerads"]', 'a[href*="effectivecpmnetwork"]',
        'a[href*="highperformanceformat"]', 'a[href*="mgid"]',
        'a[href*="taboola"]', 'a[href*="outbrain"]',
        'div[id^="ad-"]:not(:empty)', 'div[class*="advertisement"]:not(:empty)',
        'div[data-ad-slot]', 'div[data-ad-client]',
        '.ad-banner', '[class*="banner-ad"]',
    ]

    FORM_SELECTORS = [
        'form[action*="contact"]', 'form[action*="subscribe"]',
        'form[action*="newsletter"]', 'form[id*="contact"]',
        'form[id*="subscribe"]', 'form[class*="contact"]',
        'form[class*="subscribe"]', 'form[class*="newsletter"]',
        '.contact-form', '.subscribe-form', '.newsletter-form',
        '#contact-form', '#subscribe-form',
    ]

    CAPTCHA_SIGNALS = [
        'google.com/sorry', 'consent.google.com', 'captcha',
        'unusual traffic', 'detected unusual', 'our systems have detected',
        'please show you', '/sorry/index', 'are you a robot',
    ]

    VIEWPORTS = [(1920, 1080), (1366, 768), (1536, 864), (1440, 900), (1600, 900)]
    LOCALES = ['en-US', 'en-GB', 'fr-FR', 'de-DE', 'es-ES']
    TIMEZONES = {
        'en-US': 'America/New_York',
        'en-GB': 'Europe/London',
        'fr-FR': 'Europe/Paris',
        'de-DE': 'Europe/Berlin',
        'es-ES': 'Europe/Madrid',
    }

    def __init__(self, username=None, access_key=None):
        self.username = username or os.environ.get('BROWSERSTACK_USERNAME', '').strip()
        self.access_key = access_key or os.environ.get('BROWSERSTACK_ACCESS_KEY', '').strip()
        self.driver = None
        self.current_locale = 'en-US'

    def start_session(self, url, browser='chrome', os_name='Windows', os_version='11',
                      proxy=None, use_local=False, fp=None, record_video=False,
                      block_resources='balanced'):
        if not (self.username and self.access_key):
            raise RuntimeError("BrowserStack credentials missing")

        fp = fp or self._random_fp()

        options = Options()
        options.set_capability('browserName', browser)
        options.set_capability('browserVersion', 'latest')

        bstack_opts = {
            'os': os_name, 'osVersion': os_version, 'local': use_local,
            'projectName': 'Traffic Bot',
            'buildName': f'Traffic Bot - {os_name} {os_version}',
            'sessionName': f'Visit {url[:60]}',
            'debug': True, 'networkLogs': True, 'consoleLogs': 'info',
            'userName': self.username, 'accessKey': self.access_key,
        }
        if proxy:
            bstack_opts['proxy'] = proxy
        if record_video:
            bstack_opts['video'] = True

        options.set_capability('bstack:options', bstack_opts)

        logger.info(f"🖥️ BrowserStack: {browser} on {os_name} {os_version}")

        self.driver = webdriver.Remote(
            command_executor='https://hub-cloud.browserstack.com/wd/hub',
            options=options,
        )
        self.driver.set_page_load_timeout(90)
        self.driver.set_script_timeout(30)

        CDPSpoofer.apply(self.driver, fp)
        ResourceBlocker.setup(self.driver, mode=block_resources)

        self.current_locale = fp.get('locale', 'en-US')

        if fp.get('viewport'):
            try:
                vw, vh = fp['viewport']
                self.driver.set_window_size(vw, vh)
            except Exception:
                pass

        self.driver.get(url)
        self.wait_for_page_load(timeout=30)
        return self.driver

    def click_ads(self, ad_selectors=None, max_clicks=2):
        selectors = ad_selectors or self.AD_SELECTORS
        clicked = 0
        for selector in selectors:
            if clicked >= max_clicks:
                break
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if not elements:
                    continue
                element = random.choice(elements[:5])
                if not self._safe_click(element):
                    continue
                clicked += 1
                logger.info(f"🖱️ Clicked ad: {selector}")
                self.random_sleep(3.0, 7.0)
                self._close_extra_tabs()
            except Exception:
                continue
        return clicked

    def fill_form(self, form_data=None, form_selectors=None):
        selectors = form_selectors or self.FORM_SELECTORS
        filled = 0
        for fs in selectors:
            try:
                forms = self.driver.find_elements(By.CSS_SELECTOR, fs)
                for form in forms[:2]:
                    if self._fill_single_form(form, form_data):
                        filled += 1
                        logger.info(f"📝 Filled: {fs}")
            except Exception:
                continue
        return filled

    def _fill_single_form(self, form, form_data=None):
        data = form_data or self._generate_form_data()
        filled_any = False
        for field_sel, value in data.items():
            try:
                field = form.find_element(By.CSS_SELECTOR, field_sel)
                if not (field.is_displayed() and field.is_enabled()):
                    continue
                field.clear()
                self.human_type(field, value)
                filled_any = True
            except (NoSuchElementException, ElementNotInteractableException):
                continue
        if not filled_any:
            return False
        try:
            submit = form.find_element(
                By.CSS_SELECTOR,
                'button[type="submit"], input[type="submit"]',
            )
            if submit.is_displayed() and submit.is_enabled():
                self._safe_click(submit)
                self.random_sleep(2.0, 4.0)
                return True
        except Exception:
            pass
        return filled_any

    def human_type(self, element, text, min_delay=0.04, max_delay=0.20):
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(min_delay, max_delay))
            if random.random() < 0.02:
                element.send_keys(Keys.BACKSPACE)
                time.sleep(random.uniform(0.1, 0.3))
                element.send_keys(char)
                time.sleep(random.uniform(min_delay, max_delay))

    def bezier_mouse_move(self, target):
        try:
            loc = target.location
            sz = target.size
            tx = loc['x'] + sz['width'] // 2
            ty = loc['y'] + sz['height'] // 2
            sx = random.randint(0, 200)
            sy = random.randint(0, 200)
            points = BezierMouse.bezier_points(sx, sy, tx, ty, steps=20)
            body = self.driver.find_element(By.TAG_NAME, 'body')
            actions = ActionChains(self.driver)
            for x, y in points:
                try:
                    actions.move_to_element_with_offset(body, x, y)
                    actions.pause(random.uniform(0.005, 0.02))
                except Exception:
                    continue
            actions.perform()
            return True
        except Exception:
            return False

    def human_scroll(self, count=5):
        for i in range(count):
            pixels = random.randint(250, 750)
            if i < 2 or i >= count - 1:
                self.driver.execute_script(
                    f"window.scrollBy({{top: {pixels}, behavior: 'smooth'}});"
                )
                self.random_sleep(1.2, 2.5)
            else:
                self.driver.execute_script(
                    f"window.scrollBy({{top: {pixels * 2}, behavior: 'smooth'}});"
                )
                self.random_sleep(0.6, 1.2)
            if random.random() < 0.2:
                self.driver.execute_script(
                    f"window.scrollBy({{top: -{random.randint(100, 250)}, behavior: 'smooth'}});"
                )
                self.random_sleep(0.5, 1.0)

    def random_sleep(self, min_s, max_s):
        time.sleep(random.uniform(min_s, max_s))

    def _safe_click(self, element, max_retries=3):
        for attempt in range(max_retries):
            try:
                if not element.is_displayed():
                    return False
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                    element,
                )
                self.random_sleep(0.5, 1.2)
                try:
                    element.click()
                except ElementClickInterceptedException:
                    self.driver.execute_script("arguments[0].click();", element)
                return True
            except StaleElementReferenceException:
                time.sleep(0.5)
            except Exception:
                time.sleep(0.5)
        return False

    def _close_extra_tabs(self):
        try:
            if len(self.driver.window_handles) > 1:
                main = self.driver.window_handles[0]
                for handle in self.driver.window_handles[1:]:
                    self.driver.switch_to.window(handle)
                    self.random_sleep(1.5, 3.0)
                    self.driver.close()
                self.driver.switch_to.window(main)
        except Exception:
            pass

    def is_captcha_page(self):
        try:
            url = self.driver.current_url.lower()
            title = (self.driver.title or '').lower()
            try:
                source = self.driver.page_source.lower()[:5000]
            except Exception:
                source = ''
            for sig in self.CAPTCHA_SIGNALS:
                if sig in url or sig in title or sig in source:
                    return True
            return False
        except Exception:
            return False

    def wait_for_page_load(self, timeout=30):
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            pass

    def save_cookies(self, path='cookies.json'):
        try:
            with open(path, 'w') as f:
                json.dump(self.driver.get_cookies(), f)
        except Exception:
            pass

    def load_cookies(self, path='cookies.json'):
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                for c in json.load(f):
                    try:
                        self.driver.add_cookie(c)
                    except Exception:
                        pass
        except Exception:
            pass

    def _generate_form_data(self):
        locales_data = {
            'en-US': (['John', 'Jane', 'Alex'], ['Smith', 'Brown'],
                      ['Great content!', 'Very helpful.'], ['Inquiry', 'Question']),
            'fr-FR': (['Pierre', 'Marie'], ['Dupont', 'Martin'],
                      ['Excellent!', 'Très informatif.'], ['Demande', 'Question']),
            'de-DE': (['Hans', 'Anna'], ['Müller', 'Schmidt'],
                      ['Toller Inhalt!', 'Sehr informativ.'], ['Anfrage', 'Frage']),
        }
        locale = self.current_locale if self.current_locale in locales_data else 'en-US'
        fnames, lnames, msgs, subs = locales_data[locale]
        return {
            'input[type="email"]': self._fake_email(),
            'input[name*="name"]': f"{random.choice(fnames)} {random.choice(lnames)}",
            'textarea[name*="message"]': random.choice(msgs),
            'input[name*="subject"]': random.choice(subs),
            'input[type="tel"]': self._fake_phone(),
        }

    def _fake_email(self):
        domains = ['gmail.com', 'yahoo.com', 'outlook.com']
        names = ['john', 'jane', 'alex', 'sarah', 'mike']
        return f"{random.choice(names)}{random.randint(100, 9999)}@{random.choice(domains)}"

    def _fake_phone(self):
        countries = ['+212', '+33', '+44', '+1', '+49']
        return f"{random.choice(countries)}{random.randint(600000000, 999999999)}"

    def _random_fp(self):
        locale = random.choice(self.LOCALES)
        return {
            'locale': locale,
            'timezone': self.TIMEZONES[locale],
            'platform': 'Win32',
            'vendor': 'Google Inc.',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'viewport': random.choice(self.VIEWPORTS),
            'webgl_vendor': 'Google Inc. (NVIDIA)',
            'webgl_renderer': 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)',
            'hardware_concurrency': random.choice([4, 8, 12, 16]),
            'device_memory': random.choice([4, 8, 16]),
            'langs': [locale, locale.split('-')[0]],
        }

    def take_screenshot(self, filename=None):
        if not filename:
            filename = f"screenshot_{int(time.time())}.png"
        try:
            self.driver.save_screenshot(filename)
            return filename
        except Exception:
            return None

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None


class LocalBrowserClient(BrowserStackClient):
    def __init__(self):
        super().__init__()
        self._profile_dir = None

    def start_session(self, url, headless=True, proxy=None, fp=None,
                      block_resources='balanced'):
        fp = fp or self._random_fp()
        options = Options()
        vw, vh = fp.get('viewport', (1920, 1080))
        locale = fp.get('locale', 'en-US')

        if headless:
            options.add_argument('--headless=new')

        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-setuid-sandbox')
        options.add_argument(f'--window-size={vw},{vh}')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')
        options.add_argument(f'--lang={locale}')
        options.add_argument('--log-level=3')

        chrome_bin = os.environ.get('CHROME_BIN', '/usr/local/bin/google-chrome')
        if os.path.exists(chrome_bin):
            options.binary_location = chrome_bin

        if proxy:
            options.add_argument(f'--proxy-server={proxy}')

        self._profile_dir = tempfile.mkdtemp(prefix='chrome_profile_')
        options.add_argument(f'--user-data-dir={self._profile_dir}')

        cd_path = os.environ.get('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')

        try:
            if os.path.exists(cd_path):
                service = Service(executable_path=cd_path)
                self.driver = webdriver.Chrome(service=service, options=options)
            else:
                self.driver = webdriver.Chrome(options=options)
            logger.info(f"✅ Chrome started ({vw}x{vh}, {locale})")
        except Exception as e:
            logger.error(f"❌ Chrome failed: {e}")
            raise

        CDPSpoofer.apply(self.driver, fp)
        ResourceBlocker.setup(self.driver, mode=block_resources)

        self.current_locale = locale
        self.driver.set_page_load_timeout(60)
        self.driver.set_script_timeout(30)
        self.driver.get(url)
        self.wait_for_page_load(timeout=30)
        return self.driver
