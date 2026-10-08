import os
import random
import scrapy  # type: ignore[reportMissingImports]
from datetime import datetime

class TrafficSpider(scrapy.Spider):
    name = 'traffic_bot'
    
    custom_settings = {
        'ADDONS': {
            'scrapy_zyte_api.Addon': 500,
        },
        'DOWNLOADER_MIDDLEWARES': {
            'middlewares.proxy_rotator.FreeProxyRotatorMiddleware': 543,
            'middlewares.zyte_middleware.ZyteMiddleware': 544,
        },
        'FREE_PROXY_LIST_URL': 'https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/all/data.txt',
        'ZYTE_API_KEY': os.environ.get('ZYTE_API_KEY', ''),
        'ROTATING_PROXY_PAGE_RETRY_TIMES': 5,
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    def __init__(self, target_url=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # التأكد من صحة الرابط والتراجع للرابط الافتراضي في حال كان الممرر فارغاً
        if target_url and target_url.strip():
            self.target_url = target_url.strip()
        else:
            self.target_url = 'https://www.forjo.tech/'

    def start_requests(self):
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        ]
        
        self.logger.info(f"بدء إرسال الطلب إلى: {self.target_url}")
        yield scrapy.Request(
            url=self.target_url,
            callback=self.parse,
            headers={'User-Agent': random.choice(user_agents)},
            meta={'use_zyte': False}
        )

    def parse(self, response):
        self.logger.info(f"تمت الزيارة بنجاح! كود الاستجابة: {response.status}")
        
        # استخراج العناوين والروابط الموجودة في الصفحة
        links = response.css('a::attr(href)').getall()
        
        yield {
            'type': 'log',
            'site': self.target_url,
            'status': response.status,
            'links_found': len(links),
            'timestamp': datetime.utcnow().isoformat()
        }