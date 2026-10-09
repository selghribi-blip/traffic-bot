import os
import scrapy
from datetime import datetime
from utils.browserstack_client import BrowserStackClient, LocalBrowserClient


class BrowserStackSpider(scrapy.Spider):
    name = 'browserstack_bot'
    
    custom_settings = {
        'DOWNLOAD_DELAY': 5,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'CONCURRENT_REQUESTS': 1,
    }

    def __init__(self, target_url=None, use_browserstack=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_url = target_url.strip() if target_url and target_url.strip() else 'https://www.forjo.tech/'
        self.use_browserstack = use_browserstack.lower() == 'true' if isinstance(use_browserstack, str) else use_browserstack
        self.client = None
        self.ads_clicked = 0
        self.forms_filled = 0

    def start_requests(self):
        # 1. تحديد الرابط والتحقق منه بنفس الطريقة
        target = getattr(self, 'target_url', None)
        
        if not target:
            target = self.settings.get('TARGET_URL', 'https://www.forjo.tech/')
            self.logger.info(f"Using default URL: {target}")
        else:
            self.logger.info(f"URL passed from command line: {target}")

        if not target.startswith(('http://', 'https://')):
            target = 'https://' + target
            self.logger.info(f"Protocol missing. Updated URL to: {target}")

        self.target_url = target
        self.logger.info(f"Starting BrowserStack bot for: {self.target_url}")
        
        # 2. التحقق من إعدادات BrowserStack
        if getattr(self, 'use_browserstack', False):
            import os
            username = os.environ.get('BROWSERSTACK_USERNAME')
            access_key = os.environ.get('BROWSERSTACK_ACCESS_KEY')
            if not username or not access_key:
                self.logger.error("BrowserStack credentials not found, falling back to local browser")
                self.use_browserstack = False
        
        # 3. إرسال الطلب
        yield scrapy.Request(
            url=self.target_url,
            callback=self.parse_with_browser,
            dont_filter=True
        )


    def parse_with_browser(self, response):
        if self.use_browserstack:
            self.client = BrowserStackClient(
                os.environ.get('BROWSERSTACK_USERNAME'),
                os.environ.get('BROWSERSTACK_ACCESS_KEY')
            )
            browsers = [
                ('chrome', 'Windows', '11'),
                ('chrome', 'Windows', '10'),
                ('chrome', 'OS X', 'Ventura'),
                ('firefox', 'Windows', '11'),
                ('edge', 'Windows', '11'),
            ]
            browser, os_name, os_version = self.random_choice(browsers)
            self.client.start_session(self.target_url, browser, os_name, os_version)
        else:
            self.client = LocalBrowserClient()
            self.client.start_session(self.target_url, headless=True)
        
        try:
            self.client.wait_for_page_load()
            self.client.scroll_page(scroll_count=5)
            
            self.ads_clicked = self.client.click_ads()
            self.forms_filled = self.client.fill_form()
            
            self.client.take_screenshot(f'results_{int(datetime.utcnow().timestamp())}.png')
            
            yield {
                'type': 'browserstack_visit',
                'url': self.target_url,
                'status': 'success',
                'ads_clicked': self.ads_clicked,
                'forms_filled': self.forms_filled,
                'browser': 'browserstack' if self.use_browserstack else 'local',
                'timestamp': datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Browser automation error: {e}")
            yield {
                'type': 'browserstack_visit',
                'url': self.target_url,
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat(),
            }
        finally:
            self.client.close()

    def random_choice(self, seq):
        import random
        return random.choice(seq)

    def closed(self, reason):
        self.logger.info(f"BrowserStack spider closed: {reason}")
        self.logger.info(f"Total ads clicked: {self.ads_clicked}")
        self.logger.info(f"Total forms filled: {self.forms_filled}")
