import os
import random
import scrapy
from datetime import datetime
from urllib.parse import urljoin, urlparse


class TrafficSpider(scrapy.Spider):
    name = 'traffic_bot'

    custom_settings = {
        # 'ADDONS': {
        #     'scrapy_zyte_api.Addon': 500,
        # },  # Disabled due to Scrapy 2.19+ compatibility
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
        'script[src*="adsterra"]',
        'script[src*="monetag"]',
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
        self.logger.info(f"User-Agent: {self.user_agent}")

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
                    ],
                    'screenshot': True,
                }
            },
            dont_filter=True
        )

    def get_random_user_agent(self):
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0',
            'Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
        ]
        return random.choice(user_agents)

    def parse_main_page(self, response):
        self.visited_urls.add(self.target_url)
        self.proxy_used = response.meta.get('proxy', 'direct')

        self.logger.info(f"Visited: {self.target_url} | Status: {response.status} | Proxy: {self.proxy_used}")

        ads_clicked = self.extract_and_click_ads(response)
        forms_filled = self.extract_and_fill_forms(response)
        internal_links = self.extract_internal_links(response)

        for link in internal_links[:3]:
            if link not in self.visited_urls:
                self.visited_urls.add(link)
                yield scrapy.Request(
                    url=link,
                    callback=self.parse_internal_page,
                    headers={'User-Agent': self.get_random_user_agent()},
                    meta={
                        'use_zyte': True,
                        'zyte_api': {
                            'browserHtml': True,
                            'javascript': True,
                            'actions': [
                                {'action': 'wait', 'waitTimeout': 3},
                                {'action': 'scroll', 'direction': 'down', 'pixels': 500},
                                {'action': 'wait', 'waitTimeout': 2},
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

        self.ads_clicked += ads_clicked
        self.forms_filled += forms_filled

        yield self.create_log_entry(response, ads_clicked, forms_filled)

    def extract_and_click_ads(self, response):
        clicked = 0
        for selector in self.AD_SELECTORS:
            elements = response.css(selector)
            for element in elements:
                try:
                    href = element.css('::attr(href)').get()
                    src = element.css('::attr(src)').get()
                    data_url = element.css('::attr(data-url)').get()
                    data_href = element.css('::attr(data-href)').get()

                    ad_url = href or src or data_url or data_href
                    if ad_url:
                        full_url = urljoin(response.url, ad_url)
                        self.logger.info(f"Found ad: {full_url}")
                        clicked += 1

                        yield scrapy.Request(
                            url=full_url,
                            callback=self.parse_ad_click,
                            headers={'User-Agent': self.get_random_user_agent()},
                            meta={'use_zyte': False, 'ad_click': True},
                            dont_filter=True
                        )
                except Exception as e:
                    self.logger.debug(f"Ad click error: {e}")
        return clicked

    def parse_ad_click(self, response):
        self.logger.info(f"Ad clicked: {response.url} | Status: {response.status}")
        yield {
            'type': 'ad_click',
            'url': response.url,
            'status': response.status,
            'referer': response.request.headers.get('Referer', b'').decode(),
            'timestamp': datetime.utcnow().isoformat()
        }

    def extract_and_fill_forms(self, response):
        filled = 0
        for form_selector in self.FORM_SELECTORS:
            forms = response.css(form_selector)
            for form in forms:
                try:
                    action = form.css('::attr(action)').get()
                    method = form.css('::attr(method)').get('GET').upper()

                    form_data = {}
                    for field_type, selectors in self.FIELD_SELECTORS.items():
                        for selector in selectors:
                            field = form.css(selector)
                            if field:
                                if field_type == 'email':
                                    form_data[selector] = self.generate_fake_email()
                                elif field_type == 'name':
                                    form_data[selector] = self.generate_fake_name()
                                elif field_type == 'message':
                                    form_data[selector] = self.generate_fake_message()
                                elif field_type == 'subject':
                                    form_data[selector] = self.generate_fake_subject()
                                elif field_type == 'phone':
                                    form_data[selector] = self.generate_fake_phone()
                                break

                    if form_data:
                        form_url = urljoin(response.url, action) if action else response.url
                        self.logger.info(f"Found form at: {form_url}")
                        filled += 1

                        if method == 'POST':
                            yield scrapy.FormRequest(
                                url=form_url,
                                formdata={k: v for k, v in form_data.items()},
                                callback=self.parse_form_submit,
                                headers={'User-Agent': self.get_random_user_agent()},
                                meta={'use_zyte': False, 'form_submit': True},
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
                    if not any(full_url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.css', '.js', '.ico', '.svg', '.woff', '.woff2']):
                        links.append(full_url)
            except Exception:
                continue
        return links

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

    def create_log_entry(self, response, ads_clicked, forms_filled):
        self.ads_clicked += ads_clicked
        self.forms_filled += forms_filled

        return {
            'type': 'visit',
            'url': response.url,
            'site': self.target_url,
            'status': response.status,
            'proxy_used': self.proxy_used,
            'user_agent': self.user_agent,
            'ads_clicked': ads_clicked,
            'forms_filled': forms_filled,
            'total_ads_clicked': self.ads_clicked,
            'total_forms_filled': self.forms_filled,
            'visited_pages': len(self.visited_urls),
            'timestamp': datetime.utcnow().isoformat(),
            'response_headers': dict(response.headers),
        }

    def closed(self, reason):
        self.logger.info(f"Spider closed: {reason}")
        self.logger.info(f"Total ads clicked: {self.ads_clicked}")
        self.logger.info(f"Total forms filled: {self.forms_filled}")
        self.logger.info(f"Total pages visited: {len(self.visited_urls)}")