import random
import json
from scrapy import signals
from scrapy.exceptions import NotConfigured


class FingerprintRotatorMiddleware:
    def __init__(self):
        self.fingerprints = self.generate_fingerprints()

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def generate_fingerprints(self):
        return [
            {
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept_language': 'en-US,en;q=0.9',
                'accept_encoding': 'gzip, deflate, br, zstd',
                'sec_ch_ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                'sec_ch_ua_mobile': '?0',
                'sec_ch_ua_platform': '"Windows"',
                'sec_fetch_dest': 'document',
                'sec_fetch_mode': 'navigate',
                'sec_fetch_site': 'none',
                'sec_fetch_user': '?1',
                'upgrade_insecure_requests': '1',
                'viewport': {'width': 1920, 'height': 1080},
                'screen': {'width': 1920, 'height': 1080, 'color_depth': 24},
                'timezone': 'America/New_York',
                'language': 'en-US',
                'platform': 'Win32',
                'webgl_vendor': 'Google Inc. (NVIDIA)',
                'webgl_renderer': 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0)',
                'canvas_fingerprint': random.randint(1000000000, 9999999999),
                'audio_fingerprint': random.uniform(100, 200),
            },
            {
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept_language': 'en-US,en;q=0.9',
                'accept_encoding': 'gzip, deflate, br, zstd',
                'sec_ch_ua': '"Chromium";v="123", "Google Chrome";v="123", "Not-A.Brand";v="99"',
                'sec_ch_ua_mobile': '?0',
                'sec_ch_ua_platform': '"Windows"',
                'sec_fetch_dest': 'document',
                'sec_fetch_mode': 'navigate',
                'sec_fetch_site': 'none',
                'sec_fetch_user': '?1',
                'upgrade_insecure_requests': '1',
                'viewport': {'width': 1366, 'height': 768},
                'screen': {'width': 1366, 'height': 768, 'color_depth': 24},
                'timezone': 'Europe/London',
                'language': 'en-GB',
                'platform': 'Win32',
                'webgl_vendor': 'Google Inc. (AMD)',
                'webgl_renderer': 'ANGLE (AMD, AMD Radeon RX 6800 Direct3D11 vs_5_0 ps_5_0)',
                'canvas_fingerprint': random.randint(1000000000, 9999999999),
                'audio_fingerprint': random.uniform(100, 200),
            },
            {
                'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept_language': 'en-US,en;q=0.9',
                'accept_encoding': 'gzip, deflate, br, zstd',
                'sec_ch_ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                'sec_ch_ua_mobile': '?0',
                'sec_ch_ua_platform': '"macOS"',
                'sec_fetch_dest': 'document',
                'sec_fetch_mode': 'navigate',
                'sec_fetch_site': 'none',
                'sec_fetch_user': '?1',
                'upgrade_insecure_requests': '1',
                'viewport': {'width': 1440, 'height': 900},
                'screen': {'width': 1440, 'height': 900, 'color_depth': 30},
                'timezone': 'America/Los_Angeles',
                'language': 'en-US',
                'platform': 'MacIntel',
                'webgl_vendor': 'Apple',
                'webgl_renderer': 'Apple GPU',
                'canvas_fingerprint': random.randint(1000000000, 9999999999),
                'audio_fingerprint': random.uniform(100, 200),
            },
            {
                'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'accept_language': 'en-US,en;q=0.9',
                'accept_encoding': 'gzip, deflate, br',
                'sec_fetch_dest': 'document',
                'sec_fetch_mode': 'navigate',
                'sec_fetch_site': 'none',
                'sec_fetch_user': '?1',
                'viewport': {'width': 1512, 'height': 982},
                'screen': {'width': 1512, 'height': 982, 'color_depth': 30},
                'timezone': 'Europe/Paris',
                'language': 'fr-FR',
                'platform': 'MacIntel',
                'webgl_vendor': 'Apple',
                'webgl_renderer': 'Apple M2',
                'canvas_fingerprint': random.randint(1000000000, 9999999999),
                'audio_fingerprint': random.uniform(100, 200),
            },
            {
                'user_agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept_language': 'en-US,en;q=0.9',
                'accept_encoding': 'gzip, deflate, br, zstd',
                'sec_ch_ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                'sec_ch_ua_mobile': '?0',
                'sec_ch_ua_platform': '"Linux"',
                'sec_fetch_dest': 'document',
                'sec_fetch_mode': 'navigate',
                'sec_fetch_site': 'none',
                'sec_fetch_user': '?1',
                'upgrade_insecure_requests': '1',
                'viewport': {'width': 1920, 'height': 1080},
                'screen': {'width': 1920, 'height': 1080, 'color_depth': 24},
                'timezone': 'UTC',
                'language': 'en-US',
                'platform': 'Linux x86_64',
                'webgl_vendor': 'Mesa',
                'webgl_renderer': 'Mesa Intel UHD Graphics 630',
                'canvas_fingerprint': random.randint(1000000000, 9999999999),
                'audio_fingerprint': random.uniform(100, 200),
            },
            {
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'accept_language': 'en-US,en;q=0.5',
                'accept_encoding': 'gzip, deflate, br, zstd',
                'sec_fetch_dest': 'document',
                'sec_fetch_mode': 'navigate',
                'sec_fetch_site': 'none',
                'sec_fetch_user': '?1',
                'upgrade_insecure_requests': '1',
                'viewport': {'width': 1920, 'height': 1080},
                'screen': {'width': 1920, 'height': 1080, 'color_depth': 24},
                'timezone': 'America/Chicago',
                'language': 'en-US',
                'platform': 'Win32',
                'webgl_vendor': 'Mozilla',
                'webgl_renderer': 'Mozilla',
                'canvas_fingerprint': random.randint(1000000000, 9999999999),
                'audio_fingerprint': random.uniform(100, 200),
            },
            {
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'accept_language': 'en-US,en;q=0.9',
                'accept_encoding': 'gzip, deflate, br',
                'sec_fetch_dest': 'document',
                'sec_fetch_mode': 'navigate',
                'sec_fetch_site': 'none',
                'sec_fetch_user': '?1',
                'viewport': {'width': 390, 'height': 844},
                'screen': {'width': 390, 'height': 844, 'color_depth': 30},
                'timezone': 'America/New_York',
                'language': 'en-US',
                'platform': 'iPhone',
                'webgl_vendor': 'Apple',
                'webgl_renderer': 'Apple GPU',
                'canvas_fingerprint': random.randint(1000000000, 9999999999),
                'audio_fingerprint': random.uniform(100, 200),
            },
            {
                'user_agent': 'Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'accept_language': 'en-US,en;q=0.9',
                'accept_encoding': 'gzip, deflate, br',
                'sec_fetch_dest': 'document',
                'sec_fetch_mode': 'navigate',
                'sec_fetch_site': 'none',
                'sec_fetch_user': '?1',
                'viewport': {'width': 820, 'height': 1180},
                'screen': {'width': 820, 'height': 1180, 'color_depth': 30},
                'timezone': 'Europe/Berlin',
                'language': 'de-DE',
                'platform': 'iPad',
                'webgl_vendor': 'Apple',
                'webgl_renderer': 'Apple M2',
                'canvas_fingerprint': random.randint(1000000000, 9999999999),
                'audio_fingerprint': random.uniform(100, 200),
            },
        ]

    def process_request(self, request, spider):
        if not request.meta.get('fingerprint'):
            fingerprint = random.choice(self.fingerprints)
            request.meta['fingerprint'] = fingerprint
            
            request.headers['User-Agent'] = fingerprint['user_agent']
            request.headers['Accept'] = fingerprint['accept']
            request.headers['Accept-Language'] = fingerprint['accept_language']
            request.headers['Accept-Encoding'] = fingerprint['accept_encoding']
            
            for key in ['sec_ch_ua', 'sec_ch_ua_mobile', 'sec_ch_ua_platform', 
                        'sec_fetch_dest', 'sec_fetch_mode', 'sec_fetch_site', 
                        'sec_fetch_user', 'upgrade_insecure_requests']:
                if key in fingerprint:
                    request.headers[key.replace('_', '-').title()] = fingerprint[key]
            
            if 'zyte_api' in request.meta:
                request.meta['zyte_api']['customHeaders'] = dict(request.headers)
        
        return None