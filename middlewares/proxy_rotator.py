import random
import requests
from scrapy import signals
from scrapy.exceptions import NotConfigured

class FreeProxyRotatorMiddleware:
    def __init__(self, proxy_list_url):
        self.proxy_list_url = proxy_list_url
        self.proxies = []
        self.load_proxies()

    @classmethod
    def from_crawler(cls, crawler):
        url = crawler.settings.get('FREE_PROXY_LIST_URL')
        if not url:
            raise NotConfigured('FREE_PROXY_LIST_URL not set')
        return cls(url)

    def load_proxies(self):
        try:
            response = requests.get(self.proxy_list_url, timeout=10)
            self.proxies = [line.strip() for line in response.text.splitlines() if line.strip()]
        except Exception as e:
            print(f"Failed to load proxies: {e}")
            self.proxies = []

    def process_request(self, request, spider):
        if self.proxies and not request.meta.get('proxy'):
            proxy = random.choice(self.proxies)
            request.meta['proxy'] = f'http://{proxy}'
        return None