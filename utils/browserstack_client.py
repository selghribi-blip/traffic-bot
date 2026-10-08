from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import time
import random
import os


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
        '.adsense',
        '.ad-banner',
        '[class*="banner-ad"]',
    ]

    FORM_SELECTORS = [
        'form[action*="contact"]',
        'form[action*="subscribe"]',
        'form[action*="newsletter"]',
        'form[id*="contact"]',
        'form[id*="subscribe"]',
        'form[class*="contact"]',
        'form[class*="subscribe"]',
        'form[class*="newsletter"]',
        '.contact-form',
        '.subscribe-form',
        '.newsletter-form',
        '#contact-form',
        '#subscribe-form',
    ]

    FIELD_SELECTORS = {
        'email': ['input[type="email"]', 'input[name*="email"]', 'input[id*="email"]'],
        'name': ['input[name*="name"]', 'input[id*="name"]', 'input[placeholder*="name" i]'],
        'message': ['textarea[name*="message"]', 'textarea[id*="message"]', 'textarea[placeholder*="message" i]'],
        'subject': ['input[name*="subject"]', 'input[id*="subject"]'],
        'phone': ['input[type="tel"]', 'input[name*="phone"]', 'input[id*="phone"]'],
    }

    def __init__(self, username, access_key):
        self.username = username
        self.access_key = access_key
        self.driver = None

    def start_session(self, url, browser='chrome', os_name='Windows', os_version='11'):
        options = Options()
        options.set_capability('browserName', browser)
        options.set_capability('browserVersion', 'latest')
        options.set_capability('bstack:options', {
            'os': os_name,
            'osVersion': os_version,
            'local': True,
            'seleniumVersion': '4.18.0',
            'projectName': 'Traffic Bot',
            'buildName': f'Traffic Bot - {os_name} {os_version} - {browser}',
            'sessionName': f'Visit {url}',
            'debug': True,
            'networkLogs': True,
            'consoleLogs': 'info',
        })
        
        self.driver = webdriver.Remote(
            command_executor=f'https://{self.username}:{self.access_key}@hub-cloud.browserstack.com/wd/hub',
            options=options
        )
        self.driver.set_page_load_timeout(60)
        self.driver.get(url)
        return self.driver

    def click_ads(self, ad_selectors=None):
        selectors = ad_selectors or self.AD_SELECTORS
        clicked = 0
        
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements[:3]:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                            time.sleep(random.uniform(0.5, 1.5))
                            element.click()
                            time.sleep(random.uniform(2, 4))
                            clicked += 1
                            print(f"Clicked ad: {selector}")
                    except (ElementClickInterceptedException, TimeoutException):
                        continue
            except Exception as e:
                print(f"Error clicking ads with selector {selector}: {e}")
        
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
                        for field_selector, value in data.items():
                            try:
                                field = form.find_element(By.CSS_SELECTOR, field_selector)
                                if field.is_displayed() and field.is_enabled():
                                    field.clear()
                                    time.sleep(0.3)
                                    field.send_keys(value)
                                    time.sleep(0.3)
                            except NoSuchElementException:
                                continue
                        
                        try:
                            submit = form.find_element(By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]')
                            if submit.is_displayed() and submit.is_enabled():
                                submit.click()
                                time.sleep(random.uniform(2, 4))
                                filled += 1
                                print(f"Filled and submitted form: {form_selector}")
                        except NoSuchElementException:
                            pass
                    except Exception as e:
                        print(f"Error filling form {form_selector}: {e}")
            except Exception as e:
                print(f"Error finding forms with selector {form_selector}: {e}")
        
        return filled

    def generate_form_data(self):
        return {
            'input[type="email"]': self.generate_fake_email(),
            'input[name*="name"]': self.generate_fake_name(),
            'textarea[name*="message"]': self.generate_fake_message(),
            'input[name*="subject"]': self.generate_fake_subject(),
            'input[type="tel"]': self.generate_fake_phone(),
        }

    def generate_fake_email(self):
        domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'protonmail.com']
        names = ['john', 'jane', 'alex', 'sarah', 'mike', 'lisa', 'david', 'emma', 'chris', 'amy']
        nums = random.randint(100, 9999)
        return f"{random.choice(names)}{nums}@{random.choice(domains)}"

    def generate_fake_name(self):
        first = ['John', 'Jane', 'Alex', 'Sarah', 'Mike', 'Lisa', 'David', 'Emma', 'Chris', 'Amy']
        last = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Wilson', 'Taylor']
        return f"{random.choice(first)} {random.choice(last)}"

    def generate_fake_message(self):
        messages = [
            "Great content! Keep up the good work.",
            "Very informative article, thanks for sharing.",
            "I enjoyed reading this, very helpful.",
            "Nice blog, subscribed to your newsletter.",
            "Interesting perspective on this topic.",
            "Thanks for the valuable information.",
            "Well written and easy to understand.",
            "Looking forward to more posts like this.",
        ]
        return random.choice(messages)

    def generate_fake_subject(self):
        subjects = ['Inquiry', 'Feedback', 'Question', 'Collaboration', 'General Question', 'Support']
        return random.choice(subjects)

    def generate_fake_phone(self):
        return f"+212{random.randint(600000000, 699999999)}"

    def scroll_page(self, scroll_count=5):
        for i in range(scroll_count):
            self.driver.execute_script("window.scrollBy(0, window.innerHeight);")
            time.sleep(random.uniform(1, 2))

    def wait_for_page_load(self, timeout=30):
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            pass

    def take_screenshot(self, filename=None):
        if not filename:
            filename = f"screenshot_{int(time.time())}.png"
        self.driver.save_screenshot(filename)
        return filename

    def get_page_source(self):
        return self.driver.page_source

    def execute_script(self, script):
        return self.driver.execute_script(script)

    def close(self):
        if self.driver:
            self.driver.quit()


class LocalBrowserClient:
    def __init__(self):
        self.driver = None

    def start_session(self, url, headless=True):
        options = Options()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            import undetected_chromedriver as uc
            self.driver = uc.Chrome(options=options)
        except ImportError:
            self.driver = webdriver.Chrome(options=options)
        
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            '''
        })
        
        self.driver.set_page_load_timeout(60)
        self.driver.get(url)
        return self.driver

    def click_ads(self, ad_selectors=None):
        client = BrowserStackClient('', '')
        client.driver = self.driver
        return client.click_ads(ad_selectors)

    def fill_form(self, form_data=None, form_selectors=None):
        client = BrowserStackClient('', '')
        client.driver = self.driver
        return client.fill_form(form_data, form_selectors)

    def scroll_page(self, scroll_count=5):
        client = BrowserStackClient('', '')
        client.driver = self.driver
        return client.scroll_page(scroll_count)

    def wait_for_page_load(self, timeout=30):
        client = BrowserStackClient('', '')
        client.driver = self.driver
        return client.wait_for_page_load(timeout)

    def take_screenshot(self, filename=None):
        if not filename:
            filename = f"screenshot_{int(time.time())}.png"
        self.driver.save_screenshot(filename)
        return filename

    def get_page_source(self):
        return self.driver.page_source

    def close(self):
        if self.driver:
            self.driver.quit()