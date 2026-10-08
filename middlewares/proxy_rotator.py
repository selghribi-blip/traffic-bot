import random
import requests
import re
from scrapy import signals
from scrapy.exceptions import NotConfigured


class FreeProxyRotatorMiddleware:
    PROXY_SOURCES = [
        'https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/all/data.txt',
        'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
        'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt',
        'https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt',
        'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt',
        'https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt',
        'https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt',
        'https://raw.githubusercontent.com/sunny9577/proxy-scraper/main/proxies.txt',
    ]

    def __init__(self, proxy_list_url=None):
        self.proxy_list_url = proxy_list_url
        self.proxies = []
        self.last_fetch = 0
        self.fetch_interval = 3600
        self.load_proxies()

    @classmethod
    def from_crawler(cls, crawler):
        url = crawler.settings.get('FREE_PROXY_LIST_URL')
        return cls(url)

    def load_proxies(self):
        all_proxies = set()
        
        sources = [self.proxy_list_url] if self.proxy_list_url else self.PROXY_SOURCES
        
        for url in sources:
            try:
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    lines = response.text.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and self.is_valid_proxy(line):
                            all_proxies.add(line)
            except Exception as e:
                print(f"Failed to load proxies from {url}: {e}")

        self.proxies = list(all_proxies)
        random.shuffle(self.proxies)
        print(f"Loaded {len(self.proxies)} proxies")

    def is_valid_proxy(self, proxy):
        patterns = [
            r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}$',
            r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}:\w+:\w+$',
        ]
        return any(re.match(pattern, proxy) for pattern in patterns)

    def process_request(self, request, spider):
        if not self.proxies:
            self.load_proxies()
        
        if self.proxies and not request.meta.get('proxy'):
            proxy = random.choice(self.proxies)
            if ':' in proxy and proxy.count(':') == 1:
                request.meta['proxy'] = f'http://{proxy}'
            elif proxy.count(':') >= 2:
                parts = proxy.split(':')
                if len(parts) == 4:
                    request.meta['proxy'] = f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
                else:
                    request.meta['proxy'] = f'http://{proxy}'
            else:
                request.meta['proxy'] = f'http://{proxy}'
        
        return None

    def process_response(self, request, response, spider):
        if response.status >= 400 and 'proxy' in request.meta:
            proxy = request.meta.get('proxy')
            if proxy and proxy in self.proxies:
                self.proxies.remove(proxy)
                print(f"Removed failed proxy: {proxy}")
        return response