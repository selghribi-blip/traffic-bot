import scrapy
import random
from datetime import datetime

class TrafficSpider(scrapy.Spider):
    name = 'traffic_bot'
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'middlewares.proxy_rotator.FreeProxyRotatorMiddleware': 543,
            'middlewares.zyte_middleware.ZyteMiddleware': 544,
        },
        'FREE_PROXY_LIST_URL': 'https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/all/data.txt',
        'ZYTE_API_KEY': '${ZYTE_API_KEY}',
        'ROTATING_PROXY_PAGE_RETRY_TIMES': 5,
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    def __init__(self, target_url=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_url = target_url or 'https://www.forjo.tech/'
        self.ads_clicked = 0
        self.forms_filled = 0

    def start_requests(self):
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        ]
        yield scrapy.Request(self.target_url, callback=self.parse, headers={'User-Agent': random.choice(user_agents)}, meta={'use_zyte': False})

    def parse(self, response):
        ad_selectors = ['a[href*="adsterra"]', 'a[href*="monetag"]', 'a[target="_blank"]', 'iframe[src*="ad"]']
        for selector in ad_selectors:
            elements = response.css(selector)
            for element in elements:
                ad_url = element.attrib.get('href') or element.attrib.get('src')
                if ad_url:
                    self.ads_clicked += 1
                    yield scrapy.Request(ad_url, callback=self.parse_ad, dont_filter=True, meta={'use_zyte': True})

        yield {
            'type': 'log',
            'site': self.target_url,
            'ads_clicked': self.ads_clicked,
            'timestamp': datetime.utcnow().isoformat()
        }

    def parse_ad(self, response):
        self.logger.info(f"Ad clicked: {response.url} - Status: {response.status}")
        yield {'type': 'ad_click', 'url': response.url, 'status': response.status}