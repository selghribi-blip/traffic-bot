# utils/browserstack_client.py
"""
BrowserStack + Local Browser Client
====================================
يدعم:
  - BrowserStack Automate (متصفحات حقيقية على أجهزة حقيقية)
  - Local Chrome/Chromium (بديل مجاني)

ملاحظة مهمة:
  BrowserStack يوفر بصمة متصفح حقيقية بالفعل (لا حاجة لـ FingerprintRotator).
  لكنه يحتاج بروكسي لتغيير IP (لتجنب حظر مراكز البيانات).
"""
import os
import time
import random
import tempfile
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, WebDriverException,
)

logger = logging.getLogger(__name__)


class BrowserStackClient:
    AD_SELECTORS = [
        'ins.adsbygoogle',
        'iframe[id*="google_ads"]',
        'iframe[src*="doubleclick"]',
        'iframe[src*="googlesyndication"]',
        'div[id^="ad-"]',
        'div[class*="advertisement"]',
        'div[class*="ads-"]',
        'div[data-ad-slot]',
        'div[data-ad-client]',
        'a[href*="adsterra"]',
        'a[href*="monetag"]',
        'a[href*="propellerads"]',
        'a[href*="mgid"]',
        'a[href*="taboola"]',
        'a[href*="outbrain"]',
        '.adsense', '.ad-banner', '[class*="banner-ad"]',
    ]

    FORM_SELECTORS = [
        'form[action*="contact"]', 'form[action*="subscribe"]',
        'form[action*="newsletter"]', 'form[id*="contact"]',
        'form[id*="subscribe"]', 'form[class*="contact"]',
        'form[class*="subscribe"]', 'form[class*="newsletter"]',
        '.contact-form', '.subscribe-form', '.newsletter-form',
        '#contact-form', '#subscribe-form',
    ]

    def __init__(self, username=None, access_key=None):
        self.username = username or os.environ.get('BROWSERSTACK_USERNAME', '')
        self.access_key = access_key or os.environ.get('BROWSERSTACK_ACCESS_KEY', '')
        self.driver = None

    # ---------- Session ----------
    def start_session(self, url, browser='chrome', os_name='Windows', os_version='11',
                      proxy=None, use_local=False):
        """
        يبدأ جلسة BrowserStack.
        use_local: لا تفعّله إلا إذا شغّلت BrowserStackLocal tunnel.
        """
        options = Options()
        options.set_capability('browserName', browser)
        options.set_capability('browserVersion', 'latest')

        bstack_opts = {
            'os': os_name,
            'osVersion': os_version,
            'local': use_local,          # ← false افتراضيًا
            'seleniumVersion': '4.18.0',
            'projectName': 'Traffic Bot',
            'buildName': f'Traffic Bot - {os_name} {os_version} - {browser}',
            'sessionName': f'Visit {url[:80]}',
            'debug': True,
            'networkLogs': True,
            'consoleLogs': 'info',
        }

        # بروكسي اختياري
        if proxy:
            bstack_opts['proxy'] = proxy

        options.set_capability('bstack:options', bstack_opts)

        # credentials عبر options (وليس في URL)
        options.set_capability('bstack:options', {
            **bstack_opts,
            'userName': self.username,
            'accessKey': self.access_key,
        })

        self.driver = webdriver.Remote(
            command_executor='https://hub-cloud.browserstack.com/wd/hub',
            options=options,
        )
        self.driver.set_page_load_timeout(60)
        self.driver.set_script_timeout(30)
        self.driver.get(url)
        self.wait_for_page_load(timeout=30)
        return self.driver

    # ---------- Actions ----------
    def click_ads(self, ad_selectors=None):
        selectors = ad_selectors or self.AD_SELECTORS
        clicked = 0
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements[:3]:
                    try:
                        if not (el.is_displayed() and el.is_enabled()):
                            continue
                        # scroll + click عبر JS لتجنّب Intercepted
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", el
                        )
                        time.sleep(random.uniform(0.5, 1.5))
                        try:
                            el.click()
                        except ElementClickInterceptedException:
                            self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(random.uniform(1.5, 3.0))
                        clicked += 1
                        logger.info(f"🖱️ Clicked ad: {selector}")
                    except Exception:
                        continue
            except Exception as e:
                logger.debug(f"Ad selector error ({selector}): {e}")
        return clicked

    def fill_form(self, form_data=None, form_selectors=None):
        selectors = form_selectors or self.FORM_SELECTORS
        filled = 0
        for form_selector in selectors:
            try:
                forms = self.driver.find_elements(By.CSS_SELECTOR, form_selector)
                for form in forms[:2]:
                    try:
                        data = form_data or self.generate_form_data()
                        filled_any = False
                        for field_sel, value in data.items():
                            try:
                                field = form.find_element(By.CSS_SELECTOR, field_sel)
                                if field.is_displayed() and field.is_enabled():
                                    field.clear()
                                    time.sleep(0.2)
                                    field.send_keys(value)
                                    time.sleep(0.2)
                                    filled_any = True
                            except NoSuchElementException:
                                continue

                        if not filled_any:
                            continue

                        # Submit
                        try:
                            submit = form.find_element(
                                By.CSS_SELECTOR,
                                'button[type="submit"], input[type="submit"]',
                            )
                            if submit.is_displayed() and submit.is_enabled():
                                submit.click()
                                time.sleep(random.uniform(2, 4))
                                filled += 1
                                logger.info(f"📝 Filled form: {form_selector}")
                        except NoSuchElementException:
                            pass
                    except Exception as e:
                        logger.debug(f"Form fill error: {e}")
            except Exception as e:
                logger.debug(f"Form selector error ({form_selector}): {e}")
        return filled

    def scroll_page(self, scroll_count=5):
        for _ in range(scroll_count):
            self.driver.execute_script("window.scrollBy(0, window.innerHeight);")
            time.sleep(random.uniform(1, 2))

    def wait_for_page_load(self, timeout=30):
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            pass

    # ---------- Data generators ----------
    def generate_form_data(self):
        return {
            'input[type="email"]': self.generate_fake_email(),
            'input[name*="name"]': self.generate_fake_name(),
            'textarea[name*="message"]': self.generate_fake_message(),
            'input[name*="subject"]': self.generate_fake_subject(),
            'input[type="tel"]': self.generate_fake_phone(),
        }

    def generate_fake_email(self):
        domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'protonmail.com']
        names = ['john', 'jane', 'alex', 'sarah', 'mike', 'lisa', 'david', 'emma']
        return f"{random.choice(names)}{random.randint(100,9999)}@{random.choice(domains)}"

    def generate_fake_name(self):
        first = ['John', 'Jane', 'Alex', 'Sarah', 'Mike', 'Lisa', 'David', 'Emma']
        last = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller']
        return f"{random.choice(first)} {random.choice(last)}"

    def generate_fake_message(self):
        msgs = [
            "Great content! Keep up the good work.",
            "Very informative article, thanks for sharing.",
            "I enjoyed reading this, very helpful.",
            "Nice blog, subscribed to your newsletter.",
            "Interesting perspective on this topic.",
        ]
        return random.choice(msgs)

    def generate_fake_subject(self):
        return random.choice(['Inquiry', 'Feedback', 'Question', 'Support'])

    def generate_fake_phone(self):
        return f"+212{random.randint(600000000, 699999999)}"

    # ---------- Cleanup ----------
    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None


class LocalBrowserClient:
    """متصفح محلي عبر undetected-chromedriver مع مجلد مؤقت فريد."""

    def __init__(self):
        self.driver = None
        self._user_data_dir = None

    def start_session(self, url, headless=True, proxy=None):
        options = Options()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-setuid-sandbox')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # مجلد مؤقت فريد (سبب الفشل السابق: استخدام مجلد مشترك)
        self._user_data_dir = tempfile.mkdtemp(prefix='uc_chrome_')
        options.add_argument(f'--user-data-dir={self._user_data_dir}')

        # بروكسي اختياري
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')

        # محاولة undetected-chromedriver أولاً
        try:
            import undetected_chromedriver as uc
            self.driver = uc.Chrome(options=options, use_subprocess=True)
        except Exception as e:
            logger.warning(f"⚠️ uc.Chrome failed: {e}. Falling back to plain Chrome.")
            self.driver = webdriver.Chrome(options=options)

        # إخفاء navigator.webdriver
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            '''
        })

        self.driver.set_page_load_timeout(60)
        self.driver.get(url)
        return self.driver

    def click_ads(self, ad_selectors=None):
        return BrowserStackClient._click_ads_impl(self, ad_selectors)

    def fill_form(self, form_data=None, form_selectors=None):
        return BrowserStackClient._fill_form_impl(self, form_data, form_selectors)

    def scroll_page(self, scroll_count=5):
        for _ in range(scroll_count):
            self.driver.execute_script("window.scrollBy(0, window.innerHeight);")
            time.sleep(random.uniform(1, 2))

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None
