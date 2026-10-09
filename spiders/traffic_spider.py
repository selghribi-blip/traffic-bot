# spiders/traffic_spider.py
import os
import random
import scrapy
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse


class TrafficSpider(scrapy.Spider):
    name = 'traffic_bot'

    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'middlewares.fingerprint_rotator.FingerprintRotatorMiddleware': 542,
            'middlewares.proxy_rotator.FreeProxyRotatorMiddleware': 543,
            'middlewares.zyte_middleware.ZyteMiddleware': 544,
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

    # ---------- Class-level constants ----------
    AD_SELECTORS = [
        'ins.adsbygoogle', 'iframe[id*="google_ads"]', 'iframe[src*="doubleclick"]',
        'iframe[src*="googlesyndication"]', 'div[id^="ad-"]', 'div[class*="advertisement"]',
        'div[class*="ads-"]', 'div[data-ad-slot]', 'div[data-ad-client]',
        'a[href*="adsterra"]', 'a[href*="monetag"]', 'a[href*="propellerads"]',
        'a[href*="mgid"]', 'a[href*="taboola"]', 'a[href*="outbrain"]',
        'script[src*="adsterra"]', 'script[src*="monetag"]', '.adsense',
        '.ad-banner', '[class*="banner-ad"]',
    ]

    FIELD_SELECTORS = {
        'email':   ['input[type="email"]', 'input[name*="email" i]', 'input[id*="email" i]'],
        'name':    ['input[name*="name" i]', 'input[id*="name" i]', 'input[placeholder*="name" i]'],
        'message': ['textarea[name*="message" i]', 'textarea[id*="message" i]', 'textarea[placeholder*="message" i]'],
        'subject': ['input[name*="subject" i]', 'input[id*="subject" i]'],
        'phone':   ['input[type="tel"]', 'input[name*="phone" i]', 'input[id*="phone" i]'],
    }

    # ---------- Lifecycle ----------
    def __init__(self, target_url=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_url = (target_url or '').strip() or 'https://www.forjo.tech/'
        self.visited_urls = set()
        self.ads_clicked = 0
        self.forms_filled = 0
        self.proxy_used = None

    def start_requests(self):
        target = self.target_url
        if not target.startswith(('http://', 'https://')):
            target = 'https://' + target
            self.logger.info(f"Protocol missing. Updated URL to: {target}")
        self.target_url = target

        current_ua = self.get_random_user_agent()
        self.logger.info(f"Starting traffic bot for: {self.target_url}")

        yield scrapy.Request(
            url=self.target_url,
            callback=self.parse_main_page,
            errback=self.handle_error,
            headers={'User-Agent': current_ua},
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
                    ],
                },
            },
            dont_filter=True,
        )

    def closed(self, reason):
        self.logger.info(
            f"Spider closed ({reason}). Total ads clicked: {self.ads_clicked} "
            f"| Forms filled: {self.forms_filled}"
        )

    # ---------- Main callbacks ----------
    def parse_main_page(self, response):
        self.visited_urls.add(self.target_url)
        self.proxy_used = response.meta.get('proxy', 'direct')

        # نستقبل tuple: (قائمة الطلبات, العدد)
        ad_requests, ads_count = self.extract_and_click_ads(response)
        form_requests, forms_count = self.extract_and_fill_forms(response)

        # تسليم طلبات الإعلانات والنماذج
        for req in ad_requests:
            yield req
        for req in form_requests:
            yield req

        # تسليم طلبات الروابط الداخلية
        for link in self.extract_internal_links(response)[:3]:
            if link not in self.visited_urls:
                self.visited_urls.add(link)
                yield scrapy.Request(
                    url=link,
                    callback=self.parse_internal_page,
                    errback=self.handle_error,
                    headers={'User-Agent': self.get_random_user_agent()},
                    meta={'use_zyte': True},
                    dont_filter=True,
                )

        # أخيرًا: عنصر الزيارة
        yield self.create_log_entry(response, ads_count, forms_count)

    def parse_internal_page(self, response):
        self.logger.info(f"Visited internal: {response.url} | Status: {response.status}")

        ad_requests, ads_count = self.extract_and_click_ads(response)
        form_requests, forms_count = self.extract_and_fill_forms(response)

        for req in ad_requests:
            yield req
        for req in form_requests:
            yield req

        yield self.create_log_entry(response, ads_count, forms_count)

    def parse_ad_click(self, response):
        self.logger.info(f"Ad successfully loaded: {response.url} | Status: {response.status}")
        yield {
            'type': 'ad_click',
            'url': response.url,
            'status': response.status,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    def parse_form_submit(self, response):
        self.logger.info(f"Form submitted: {response.url} | Status: {response.status}")
        yield {
            'type': 'form_submit',
            'url': response.url,
            'status': response.status,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    def handle_error(self, failure):
        self.logger.error(f"Request failed: {failure.request.url} | {failure.value}")

    # ---------- Helpers: return tuples, NO yield ----------
    def extract_and_click_ads(self, response):
        """يُعيد (قائمة الطلبات, عدد الإعلانات المكتشفة)."""
        requests_ = []
        clicked = 0

        for selector in self.AD_SELECTORS:
            for element in response.css(selector):
                try:
                    ad_url = (
                        element.css('::attr(href)').get()
                        or element.css('::attr(src)').get()
                        or element.css('::attr(data-url)').get()
                        or element.css('::attr(data-href)').get()
                    )
                    if not ad_url or ad_url.startswith('javascript:'):
                        continue

                    full_url = urljoin(response.url, ad_url)
                    self.logger.info(f"Found ad URL: {full_url}")
                    clicked += 1

                    requests_.append(scrapy.Request(
                        url=full_url,
                        callback=self.parse_ad_click,
                        errback=self.handle_error,
                        headers={
                            'User-Agent': self.get_random_user_agent(),
                            'Referer': response.url,
                        },
                        meta={
                            'use_zyte': True,
                            'ad_click': True,
                            'zyte_api': {
                                'browserHtml': True,
                                'javascript': True,
                                'actions': [
                                    {'action': 'wait', 'waitTimeout': 3},
                                    {'action': 'scroll', 'direction': 'down', 'pixels': 300},
                                ],
                            },
                        },
                        dont_filter=True,
                    ))
                except Exception as e:
                    self.logger.debug(f"Ad click error: {e}")

        return requests_, clicked

    def extract_and_fill_forms(self, response):
        """يُعيد (قائمة الطلبات, عدد النماذج المعبّأة)."""
        requests_ = []
        filled = 0

        for form_index, form in enumerate(response.css('form')):
            try:
                form_data = self._build_form_data(form)
                if not form_data:
                    continue

                self.logger.info(f"Found form to fill at index {form_index}")
                filled += 1

                requests_.append(scrapy.FormRequest.from_response(
                    response,
                    formnumber=form_index,
                    formdata=form_data,
                    callback=self.parse_form_submit,
                    errback=self.handle_error,
                    headers={
                        'User-Agent': self.get_random_user_agent(),
                        'Referer': response.url,
                    },
                    meta={'use_zyte': True, 'form_submit': True},
                    dont_filter=True,
                ))
            except Exception as e:
                self.logger.debug(f"Form fill error: {e}")

        return requests_, filled

    def _build_form_data(self, form):
        """يبني قاموس بيانات النموذج من الحقول المكتشفة."""
        form_data = {}
        for field_type, selectors in self.FIELD_SELECTORS.items():
            for selector in selectors:
                field = form.css(selector)
                if not field:
                    continue
                name_attr = field.css('::attr(name)').get()
                if not name_attr:
                    continue

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
                break  # انتقل لنوع الحقل التالي
        return form_data

    def extract_internal_links(self, response):
        links = []
        base_domain = urlparse(self.target_url).netloc
        skip_exts = (
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.ico',
            '.pdf', '.css', '.js', '.svg',
        )
        for href in response.css('a::attr(href)').getall():
            try:
                full_url = urljoin(response.url, href)
                parsed = urlparse(full_url)
                if parsed.netloc != base_domain:
                    continue
                if full_url in self.visited_urls:
                    continue
                if full_url.endswith(skip_exts):
                    continue
                links.append(full_url)
            except Exception:
                continue
        return links

    def get_random_user_agent(self):
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
        ]
        return random.choice(user_agents)

    # ---------- Fake data generators ----------
    def generate_fake_email(self):
        return f"{random.choice(['john', 'jane', 'alex', 'sarah'])}{random.randint(100, 9999)}@gmail.com"

    def generate_fake_name(self):
        return f"{random.choice(['John', 'Jane', 'Alex', 'Sarah'])} {random.choice(['Smith', 'Brown', 'Davis'])}"

    def generate_fake_message(self):
        return random.choice([
            "Great content!",
            "Very informative article.",
            "Looking forward to more posts.",
        ])

    def generate_fake_subject(self):
        return random.choice(['Inquiry', 'Feedback', 'Question'])

    def generate_fake_phone(self):
        return f"+212{random.randint(600000000, 699999999)}"

    # ---------- Log entry ----------
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
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
