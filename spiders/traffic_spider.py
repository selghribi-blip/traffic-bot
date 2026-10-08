import os
import random
import scrapy
from datetime import datetime
from urllib.parse import urljoin, urlparse

class TrafficSpider(scrapy.Spider):
    name = 'traffic_bot'

    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'middlewares.proxy_rotator.FreeProxyRotatorMiddleware': 543,
            'middlewares.zyte_middleware.ZyteMiddleware': 544,
            'middlewares.fingerprint_rotator.FingerprintRotatorMiddleware': 542,
        },
        'FREE_PROXY_LIST_URL': 'https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/all/data.txt',
        'ZYTE_API_KEY': os.environ.get('ZYTE_API_KEY', ''),
        'ROTATING_PROXY_PAGE_RETRY_TIMES': 5,
        'DOWNLOAD_DELAY': 3,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'CONCURRENT_REQUESTS': 2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 3,
        'AUTOTHROTTLE_MAX_DELAY': 15,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
    }

    # محددات الإعلانات
    AD_SELECTORS = [
        'ins.adsbygoogle', 'iframe[id*="google_ads"]', 'iframe[src*="doubleclick"]',
        'iframe[src*="googlesyndication"]', 'div[id^="ad-"]', 'div[class*="advertisement"]',
        'div[class*="ads-"]', 'div[data-ad-slot]', 'div[data-ad-client]',
        'a[href*="adsterra"]', 'a[href*="monetag"]', 'a[href*="propellerads"]',
        'a[href*="mgid"]', 'a[href*="taboola"]', 'a[href*="outbrain"]',
        'script[src*="adsterra"]', 'script[src*="monetag"]', '.adsense',
        '.ad-banner', '[class*="banner-ad"]',
    ]

    # محددات حقول النماذج للبحث عنها بذكاء
    FIELD_SELECTORS = {
        'email': ['input[type="email"]', 'input[name*="email" i]', 'input[id*="email" i]'],
        'name': ['input[name*="name" i]', 'input[id*="name" i]', 'input[placeholder*="name" i]'],
        'message': ['textarea[name*="message" i]', 'textarea[id*="message" i]', 'textarea[placeholder*="message" i]'],
        'subject': ['input[name*="subject" i]', 'input[id*="subject" i]'],
        'phone': ['input[type="tel"]', 'input[name*="phone" i]', 'input[id*="phone" i]'],
    }

    def __init__(self, target_url=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_url = target_url.strip() if target_url and target_url.strip() else 'https://www.forjo.tech/'
        self.visited_urls = set()
        self.ads_clicked = 0
        self.forms_filled = 0
        self.proxy_used = None
        self.user_agent = None

    def start_requests(self):
        self.user_agent = self.get_random_user_agent()
        self.logger.info(f"Starting traffic bot for: {self.target_url}")
        
        yield scrapy.Request(
            url=self.target_url,
            callback=self.parse_main_page,
            headers={'User-Agent': self.user_agent},
            meta={
                'use_zyte': True,
                'zyte_api': {
                    'browserHtml': True,
                    'javascript': True,
                    'actions': [
                        {'action': 'wait', 'waitTimeout': 5},
                        {'action': 'scroll', 'direction': 'down', 'pixels': 1000},
                        {'action': 'wait', 'waitTimeout': 3},
                        {'action': 'scroll', 'direction': 'down', 'pixels': 1000},
                        {'action': 'wait', 'waitTimeout': 2},
                    ]
                }
            },
            dont_filter=True
        )

    def get_random_user_agent(self):
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
        ]
        return random.choice(user_agents)

    def parse_main_page(self, response):
        self.visited_urls.add(self.target_url)
        self.proxy_used = response.meta.get('proxy', 'direct')

        self.logger.info(f"Visited: {self.target_url} | Status: {response.status}")

        ads_clicked = self.extract_and_click_ads(response)
        forms_filled = self.extract_and_fill_forms(response)
        internal_links = self.extract_internal_links(response)

        for link in internal_links[:3]:
            if link not in self.visited_urls:
                self.visited_urls.add(link)
                yield scrapy.Request(
                    url=link,
                    callback=self.parse_internal_page,
                    headers={'User-Agent': self.get_random_user_agent(), 'Referer': response.url},
                    meta={
                        'use_zyte': True,
                        'zyte_api': {
                            'browserHtml': True,
                            'javascript': True,
                            'actions': [
                                {'action': 'wait', 'waitTimeout': 3},
                                {'action': 'scroll', 'direction': 'down', 'pixels': 500},
                            ],
                        }
                    },
                    dont_filter=True
                )

        yield self.create_log_entry(response, ads_clicked, forms_filled)

    def parse_internal_page(self, response):
        self.logger.info(f"Visited internal: {response.url} | Status: {response.status}")
        
        ads_clicked = self.extract_and_click_ads(response)
        forms_filled = self.extract_and_fill_forms(response)
        
        yield self.create_log_entry(response, ads_clicked, forms_filled)

    def extract_and_click_ads(self, response):
        clicked = 0
        for selector in self.AD_SELECTORS:
            elements = response.css(selector)
            for element in elements:
                try:
                    # محاولة استخراج الرابط من مصادر متعددة
                    ad_url = element.css('::attr(href)').get() or \
                             element.css('::attr(src)').get() or \
                             element.css('::attr(data-url)').get() or \
                             element.css('::attr(data-href)').get()

                    # التأكد من أن الرابط ليس كود JS فارغ
                    if ad_url and not ad_url.startswith('javascript:'):
                        full_url = urljoin(response.url, ad_url)
                        self.logger.info(f"Found ad URL: {full_url}")
                        clicked += 1

                        # تصحيح: تفعيل Zyte و JS لمحاكاة فتح الإعلان كأنه متصفح حقيقي لتجاوز الحماية
                        yield scrapy.Request(
                            url=full_url,
                            callback=self.parse_ad_click,
                            headers={'User-Agent': self.get_random_user_agent(), 'Referer': response.url},
                            meta={
                                'use_zyte': True, 
                                'ad_click': True,
                                'zyte_api': {
                                    'browserHtml': True,
                                    'javascript': True,
                                    'actions': [
                                        {'action': 'wait', 'waitTimeout': 3},
                                        {'action': 'scroll', 'direction': 'down', 'pixels': 300}
                                    ]
                                }
                            },
                            dont_filter=True
                        )
                except Exception as e:
                    self.logger.debug(f"Ad click error: {e}")
        return clicked

    def parse_ad_click(self, response):
        self.logger.info(f"Ad successfully loaded: {response.url} | Status: {response.status}")
        yield {
            'type': 'ad_click',
            'url': response.url,
            'status': response.status,
            'timestamp': datetime.utcnow().isoformat()
        }

    def extract_and_fill_forms(self, response):
        filled = 0
        # تصحيح: البحث عن جميع النماذج في الصفحة بدلاً من محددات قد لا تعمل
        for form_index, form in enumerate(response.css('form')):
            try:
                form_data = {}
                for field_type, selectors in self.FIELD_SELECTORS.items():
                    for selector in selectors:
                        field = form.css(selector)
                        if field:
                            # تصحيح: استخراج خاصية name لتكوين الـ Payload الصحيح للـ Request
                            name_attr = field.css('::attr(name)').get()
                            if name_attr:
                                if field_type == 'email':
                                    form_data[name_attr] = self.generate_fake_email()
                                elif field_type == 'name':
                                    form_data[name_attr] = self.generate_fake_name()
                                elif field_type == 'message':
                                    form_data[name_attr] = self.generate_fake_message()
                                elif field_type == 'subject':
                                    form_data[name_attr] = self.generate_fake_subject()
                                elif field_type == 'phone':
                                    form_data[name_attr] = self.generate_fake_phone()
                                break # الانتقال للنوع التالي من الحقول بمجرد إيجاد الحقل الحالي

                if form_data:
                    self.logger.info(f"Found form to fill at index {form_index}")
                    filled += 1

                    # تصحيح: استخدام FormRequest.from_response لالتقاط الحقول المخفية (مثل CSRF Tokens)
                    yield scrapy.FormRequest.from_response(
                        response,
                        formnumber=form_index,
                        formdata=form_data,
                        callback=self.parse_form_submit,
                        headers={'User-Agent': self.get_random_user_agent(), 'Referer': response.url},
                        meta={'use_zyte': True, 'form_submit': True}, # تصحيح: إبقاء Zyte مفعل لتجاوز الـ Anti-Bot
                        dont_filter=True
                    )
            except Exception as e:
                self.logger.debug(f"Form fill error: {e}")
        return filled

    def parse_form_submit(self, response):
        self.logger.info(f"Form submitted: {response.url} | Status: {response.status}")
        yield {
            'type': 'form_submit',
            'url': response.url,
            'status': response.status,
            'timestamp': datetime.utcnow().isoformat()
        }

    def extract_internal_links(self, response):
        links = []
        base_domain = urlparse(self.target_url).netloc
        for href in response.css('a::attr(href)').getall():
            try:
                full_url = urljoin(response.url, href)
                parsed = urlparse(full_url)
                if parsed.netloc == base_domain and full_url not in self.visited_urls:
                    if not any(full_url.endswith(ext) for ext in ['.jpg', '.png', '.pdf', '.css', '.js', '.svg']):
                        links.append(full_url)
            except Exception:
                continue
        return links

    # الدوال المساعدة لتوليد البيانات العشوائية (كما هي بدون تغيير)
    def generate_fake_email(self):
        return f"{random.choice(['john', 'jane', 'alex', 'sarah'])}{random.randint(100, 9999)}@gmail.com"

    def generate_fake_name(self):
        return f"{random.choice(['John', 'Jane', 'Alex', 'Sarah'])} {random.choice(['Smith', 'Brown', 'Davis'])}"

    def generate_fake_message(self):
        return random.choice(["Great content!", "Very informative article.", "Looking forward to more posts."])

    def generate_fake_subject(self):
        return random.choice(['Inquiry', 'Feedback', 'Question'])

    def generate_fake_phone(self):
        return f"+212{random.randint(600000000, 699999999)}"

    def create_log_entry(self, response, ads_clicked, forms_filled):
        self.ads_clicked += ads_clicked
        self.forms_filled += forms_filled
        return {
            'type': 'visit',
            'url': response.url,
            'status': response.status,
            'proxy_used': self.proxy_used,
            'ads_clicked': ads_clicked,
            'forms_filled': forms_filled,
            'timestamp': datetime.utcnow().isoformat(),
        }

    def closed(self, reason):
        self.logger.info(f"Spider closed. Total ads clicked: {self.ads_clicked} | Forms filled: {self.forms_filled}")