# spiders/traffic_spider.py
import random
import scrapy
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse


class TrafficSpider(scrapy.Spider):
    name = 'traffic_bot'

    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'middlewares.fingerprint_rotator.FingerprintRotatorMiddleware': 542,
            'middlewares.proxy_rotator.FreeProxyRotatorMiddleware': 555,
        },
    }

    AD_SELECTORS = [
        'ins.adsbygoogle', 'iframe[id*="google_ads"]', 'iframe[src*="doubleclick"]',
        'iframe[src*="googlesyndication"]', 'div[id^="ad-"]',
        'div[class*="advertisement"]', 'div[class*="ads-"]',
        'div[data-ad-slot]', 'div[data-ad-client]',
        'a[href*="adsterra"]', 'a[href*="monetag"]', 'a[href*="propellerads"]',
        'a[href*="mgid"]', 'a[href*="taboola"]', 'a[href*="outbrain"]',
        '.adsense', '.ad-banner', '[class*="banner-ad"]',
    ]

    FIELD_SELECTORS = {
        'email': ['input[type="email"]', 'input[name*="email" i]', 'input[id*="email" i]'],
        'name': ['input[name*="name" i]', 'input[id*="name" i]', 'input[placeholder*="name" i]'],
        'message': ['textarea[name*="message" i]', 'textarea[id*="message" i]'],
        'subject': ['input[name*="subject" i]', 'input[id*="subject" i]'],
        'phone': ['input[type="tel"]', 'input[name*="phone" i]'],
    }

    def __init__(self, target_url=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_url = (target_url or '').strip() or 'https://www.forjo.tech/'
        self.visited_urls = set()
        self.ads_clicked = 0
        self.forms_filled = 0
        self.proxy_used = None

    def start_requests(self):
        if not self.target_url.startswith(('http://', 'https://')):
            self.target_url = 'https://' + self.target_url

        self.logger.info(f"🎬 Starting traffic bot for: {self.target_url}")

        yield scrapy.Request(
            url=self.target_url,
            callback=self.parse_main_page,
            errback=self.handle_error,
            headers={'User-Agent': self.get_random_user_agent()},
            meta={},
            dont_filter=True,
        )

    def closed(self, reason):
        self.logger.info(
            f"🏁 Closed ({reason}) | ads={self.ads_clicked} forms={self.forms_filled}"
        )

    def parse_main_page(self, response):
        self.visited_urls.add(self.target_url)
        self.proxy_used = response.meta.get('proxy', 'direct')

        ad_requests, ads_count = self.extract_and_click_ads(response)
        form_requests, forms_count = self.extract_and_fill_forms(response)

        for req in ad_requests:
            yield req
        for req in form_requests:
            yield req

        for link in self.extract_internal_links(response)[:3]:
            if link not in self.visited_urls:
                self.visited_urls.add(link)
                yield scrapy.Request(
                    url=link,
                    callback=self.parse_internal_page,
                    errback=self.handle_error,
                    headers={'User-Agent': self.get_random_user_agent()},
                    meta={},
                    dont_filter=True,
                )

        yield self.create_log_entry(response, ads_count, forms_count)

    def parse_internal_page(self, response):
        self.logger.info(f"📄 Visited: {response.url} | Status: {response.status}")

        ad_requests, ads_count = self.extract_and_click_ads(response)
        form_requests, forms_count = self.extract_and_fill_forms(response)

        for req in ad_requests:
            yield req
        for req in form_requests:
            yield req

        yield self.create_log_entry(response, ads_count, forms_count)

    def parse_ad_click(self, response):
        self.logger.info(f"🎯 Ad loaded: {response.url} | Status: {response.status}")
        yield {
            'type': 'ad_click',
            'url': response.url,
            'status': response.status,
            'parent_url': response.meta.get('parent_url', ''),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    def parse_form_submit(self, response):
        self.logger.info(f"📝 Form: {response.url} | Status: {response.status}")
        yield {
            'type': 'form_submit',
            'url': response.url,
            'status': response.status,
            'parent_url': response.meta.get('parent_url', ''),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    def handle_error(self, failure):
        self.logger.error(f"❌ {failure.request.url} | {failure.value}")

    def extract_and_click_ads(self, response):
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
                            'ad_click': True,
                            'parent_url': response.url,
                            'proxy': response.meta.get('proxy'),
                        },
                        dont_filter=True,
                    ))
                except Exception:
                    continue

        return requests_, clicked

    def extract_and_fill_forms(self, response):
        requests_ = []
        filled = 0

        for form_index, form in enumerate(response.css('form')):
            try:
                form_data = self._build_form_data(form)
                if not form_data:
                    continue

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
                    meta={
                        'form_submit': True,
                        'parent_url': response.url,
                        'proxy': response.meta.get('proxy'),
                    },
                    dont_filter=True,
                ))
            except Exception:
                continue

        return requests_, filled

    def _build_form_data(self, form):
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
                break
        return form_data

    def extract_internal_links(self, response):
        links = []
        base_domain = urlparse(self.target_url).netloc
        skip_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.ico',
                     '.pdf', '.css', '.js', '.svg')

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
        agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1',
        ]
        return random.choice(agents)

    def generate_fake_email(self):
        names = ['john', 'jane', 'alex', 'sarah', 'mike', 'lisa']
        domains = ['gmail.com', 'yahoo.com', 'outlook.com']
        return f"{random.choice(names)}{random.randint(100, 9999)}@{random.choice(domains)}"

    def generate_fake_name(self):
        first = ['John', 'Jane', 'Alex', 'Sarah', 'Mike', 'Lisa']
        last = ['Smith', 'Brown', 'Davis', 'Wilson', 'Taylor']
        return f"{random.choice(first)} {random.choice(last)}"

    def generate_fake_message(self):
        return random.choice([
            "Great content! Keep up the good work.",
            "Very informative article, thanks for sharing.",
            "I enjoyed reading this, very helpful.",
            "Nice blog, subscribed to your newsletter.",
        ])

    def generate_fake_subject(self):
        return random.choice(['Inquiry', 'Feedback', 'Question', 'Support'])

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
            'mode': 'scrapy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
