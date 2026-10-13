# middlewares/fingerprint_rotator.py
# Fingerprint Rotator - 21 coherent fingerprints
# ============================================
import random
import logging
from scrapy import signals

logger = logging.getLogger(__name__)


class FingerprintRotatorMiddleware:
    FINGERPRINTS = [
        # Windows + Chrome
        {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'platform': 'Win32', 'vendor': 'Google Inc.',
            'webgl_vendor': 'Google Inc. (NVIDIA)',
            'webgl_renderer': 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)',
            'viewport': (1920, 1080), 'timezone': 'America/New_York',
            'locale': 'en-US', 'langs': ['en-US', 'en'],
            'sec_ch_ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec_ch_ua_platform': '"Windows"', 'sec_ch_ua_mobile': '?0',
            'hardware_concurrency': 8, 'device_memory': 8,
        },
        {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'platform': 'Win32', 'vendor': 'Google Inc.',
            'webgl_vendor': 'Google Inc. (Intel)',
            'webgl_renderer': 'ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)',
            'viewport': (1536, 864), 'timezone': 'Europe/London',
            'locale': 'en-GB', 'langs': ['en-GB', 'en'],
            'sec_ch_ua': '"Google Chrome";v="130", "Chromium";v="130", "Not_A Brand";v="24"',
            'sec_ch_ua_platform': '"Windows"', 'sec_ch_ua_mobile': '?0',
            'hardware_concurrency': 4, 'device_memory': 8,
        },
        {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'platform': 'Win32', 'vendor': 'Google Inc.',
            'webgl_vendor': 'Google Inc. (AMD)',
            'webgl_renderer': 'ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0)',
            'viewport': (1920, 1080), 'timezone': 'Europe/Paris',
            'locale': 'fr-FR', 'langs': ['fr-FR', 'fr', 'en'],
            'sec_ch_ua': '"Google Chrome";v="129", "Chromium";v="129", "Not_A Brand";v="24"',
            'sec_ch_ua_platform': '"Windows"', 'sec_ch_ua_mobile': '?0',
            'hardware_concurrency': 12, 'device_memory': 16,
        },
        {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'platform': 'Win32', 'vendor': 'Google Inc.',
            'webgl_vendor': 'Google Inc. (NVIDIA)',
            'webgl_renderer': 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0)',
            'viewport': (1366, 768), 'timezone': 'Europe/Berlin',
            'locale': 'de-DE', 'langs': ['de-DE', 'de', 'en'],
            'sec_ch_ua': '"Google Chrome";v="128", "Chromium";v="128", "Not_A Brand";v="24"',
            'sec_ch_ua_platform': '"Windows"', 'sec_ch_ua_mobile': '?0',
            'hardware_concurrency': 4, 'device_memory': 8,
        },
        # macOS + Chrome
        {
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'platform': 'MacIntel', 'vendor': 'Google Inc.',
            'webgl_vendor': 'Google Inc. (Apple)',
            'webgl_renderer': 'ANGLE (Apple, Apple M1, OpenGL 4.1)',
            'viewport': (1440, 900), 'timezone': 'America/Los_Angeles',
            'locale': 'en-US', 'langs': ['en-US', 'en'],
            'sec_ch_ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec_ch_ua_platform': '"macOS"', 'sec_ch_ua_mobile': '?0',
            'hardware_concurrency': 8, 'device_memory': 8,
        },
        {
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'platform': 'MacIntel', 'vendor': 'Google Inc.',
            'webgl_vendor': 'Google Inc. (Apple)',
            'webgl_renderer': 'ANGLE (Apple, Apple M2, OpenGL 4.1)',
            'viewport': (1680, 1050), 'timezone': 'Europe/Madrid',
            'locale': 'es-ES', 'langs': ['es-ES', 'es', 'en'],
            'sec_ch_ua': '"Google Chrome";v="130", "Chromium";v="130", "Not_A Brand";v="24"',
            'sec_ch_ua_platform': '"macOS"', 'sec_ch_ua_mobile': '?0',
            'hardware_concurrency': 10, 'device_memory': 16,
        },
        {
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'platform': 'MacIntel', 'vendor': 'Google Inc.',
            'webgl_vendor': 'Google Inc. (Apple)',
            'webgl_renderer': 'ANGLE (Apple, Apple M3, OpenGL 4.1)',
            'viewport': (1920, 1080), 'timezone': 'America/Chicago',
            'locale': 'en-US', 'langs': ['en-US', 'en'],
            'sec_ch_ua': '"Google Chrome";v="129", "Chromium";v="129", "Not_A Brand";v="24"',
            'sec_ch_ua_platform': '"macOS"', 'sec_ch_ua_mobile': '?0',
            'hardware_concurrency': 12, 'device_memory': 16,
        },
        # macOS + Safari
        {
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
            'platform': 'MacIntel', 'vendor': 'Apple Computer, Inc.',
            'webgl_vendor': 'Apple Inc.', 'webgl_renderer': 'Apple M1',
            'viewport': (1440, 900), 'timezone': 'America/Los_Angeles',
            'locale': 'en-US', 'langs': ['en-US', 'en'],
            'sec_ch_ua': None, 'sec_ch_ua_platform': None, 'sec_ch_ua_mobile': None,
            'hardware_concurrency': 8, 'device_memory': 8,
        },
        {
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15',
            'platform': 'MacIntel', 'vendor': 'Apple Computer, Inc.',
            'webgl_vendor': 'Apple Inc.', 'webgl_renderer': 'Apple M2',
            'viewport': (1512, 982), 'timezone': 'Europe/Paris',
            'locale': 'fr-FR', 'langs': ['fr-FR', 'fr', 'en'],
            'sec_ch_ua': None, 'sec_ch_ua_platform': None, 'sec_ch_ua_mobile': None,
            'hardware_concurrency': 8, 'device_memory': 8,
        },
        # Windows + Firefox
        {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
            'platform': 'Win32', 'vendor': '',
            'webgl_vendor': 'Mozilla', 'webgl_renderer': 'Mozilla',
            'viewport': (1920, 1080), 'timezone': 'America/New_York',
            'locale': 'en-US', 'langs': ['en-US', 'en'],
            'sec_ch_ua': None, 'sec_ch_ua_platform': None, 'sec_ch_ua_mobile': None,
            'hardware_concurrency': 8, 'device_memory': 8,
        },
        {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
            'platform': 'Win32', 'vendor': '',
            'webgl_vendor': 'Mozilla', 'webgl_renderer': 'Mozilla',
            'viewport': (1366, 768), 'timezone': 'Europe/London',
            'locale': 'en-GB', 'langs': ['en-GB', 'en'],
            'sec_ch_ua': None, 'sec_ch_ua_platform': None, 'sec_ch_ua_mobile': None,
            'hardware_concurrency': 4, 'device_memory': 8,
        },
        {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',
            'platform': 'Win32', 'vendor': '',
            'webgl_vendor': 'Mozilla', 'webgl_renderer': 'Mozilla',
            'viewport': (1536, 864), 'timezone': 'Europe/Berlin',
            'locale': 'de-DE', 'langs': ['de-DE', 'de', 'en'],
            'sec_ch_ua': None, 'sec_ch_ua_platform': None, 'sec_ch_ua_mobile': None,
            'hardware_concurrency': 8, 'device_memory': 8,
        },
        # macOS + Firefox
        {
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0',
            'platform': 'MacIntel', 'vendor': '',
            'webgl_vendor': 'Mozilla', 'webgl_renderer': 'Mozilla',
            'viewport': (1440, 900), 'timezone': 'America/Los_Angeles',
            'locale': 'en-US', 'langs': ['en-US', 'en'],
            'sec_ch_ua': None, 'sec_ch_ua_platform': None, 'sec_ch_ua_mobile': None,
            'hardware_concurrency': 8, 'device_memory': 8,
        },
        # Linux + Chrome
        {
            'user_agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'platform': 'Linux x86_64', 'vendor': 'Google Inc.',
            'webgl_vendor': 'Google Inc. (Intel)',
            'webgl_renderer': 'ANGLE (Intel, Mesa Intel(R) UHD Graphics 620 (KBL GT2), OpenGL 4.6)',
            'viewport': (1920, 1080), 'timezone': 'Europe/London',
            'locale': 'en-GB', 'langs': ['en-GB', 'en'],
            'sec_ch_ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec_ch_ua_platform': '"Linux"', 'sec_ch_ua_mobile': '?0',
            'hardware_concurrency': 4, 'device_memory': 8,
        },
        {
            'user_agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0',
            'platform': 'Linux x86_64', 'vendor': '',
            'webgl_vendor': 'Mozilla', 'webgl_renderer': 'Mozilla',
            'viewport': (1920, 1080), 'timezone': 'Europe/Berlin',
            'locale': 'de-DE', 'langs': ['de-DE', 'de'],
            'sec_ch_ua': None, 'sec_ch_ua_platform': None, 'sec_ch_ua_mobile': None,
            'hardware_concurrency': 8, 'device_memory': 8,
        },
        # iPhone
        {
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1',
            'platform': 'iPhone', 'vendor': 'Apple Computer, Inc.',
            'webgl_vendor': 'Apple Inc.', 'webgl_renderer': 'Apple GPU',
            'viewport': (390, 844), 'timezone': 'America/New_York',
            'locale': 'en-US', 'langs': ['en-US', 'en'],
            'sec_ch_ua': None, 'sec_ch_ua_platform': None, 'sec_ch_ua_mobile': None,
            'hardware_concurrency': 6, 'device_memory': 4,
        },
        {
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1',
            'platform': 'iPhone', 'vendor': 'Apple Computer, Inc.',
            'webgl_vendor': 'Apple Inc.', 'webgl_renderer': 'Apple GPU',
            'viewport': (393, 852), 'timezone': 'Europe/Paris',
            'locale': 'fr-FR', 'langs': ['fr-FR', 'fr', 'en'],
            'sec_ch_ua': None, 'sec_ch_ua_platform': None, 'sec_ch_ua_mobile': None,
            'hardware_concurrency': 6, 'device_memory': 4,
        },
        # iPad
        {
            'user_agent': 'Mozilla/5.0 (iPad; CPU OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1',
            'platform': 'iPad', 'vendor': 'Apple Computer, Inc.',
            'webgl_vendor': 'Apple Inc.', 'webgl_renderer': 'Apple M2',
            'viewport': (820, 1180), 'timezone': 'Europe/Berlin',
            'locale': 'de-DE', 'langs': ['de-DE', 'de', 'en'],
            'sec_ch_ua': None, 'sec_ch_ua_platform': None, 'sec_ch_ua_mobile': None,
            'hardware_concurrency': 8, 'device_memory': 8,
        },
        # Android + Chrome
        {
            'user_agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
            'platform': 'Linux armv8l', 'vendor': 'Google Inc.',
            'webgl_vendor': 'Google Inc. (ARM)',
            'webgl_renderer': 'ANGLE (ARM, Mali-G715, OpenGL ES 3.2)',
            'viewport': (412, 915), 'timezone': 'America/New_York',
            'locale': 'en-US', 'langs': ['en-US', 'en'],
            'sec_ch_ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec_ch_ua_platform': '"Android"', 'sec_ch_ua_mobile': '?1',
            'hardware_concurrency': 8, 'device_memory': 8,
        },
        {
            'user_agent': 'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36',
            'platform': 'Linux armv8l', 'vendor': 'Google Inc.',
            'webgl_vendor': 'Google Inc. (Qualcomm)',
            'webgl_renderer': 'ANGLE (Qualcomm, Adreno (TM) 740, OpenGL ES 3.2)',
            'viewport': (360, 800), 'timezone': 'Europe/Paris',
            'locale': 'fr-FR', 'langs': ['fr-FR', 'fr', 'en'],
            'sec_ch_ua': '"Google Chrome";v="130", "Chromium";v="130", "Not_A Brand";v="24"',
            'sec_ch_ua_platform': '"Android"', 'sec_ch_ua_mobile': '?1',
            'hardware_concurrency': 8, 'device_memory': 8,
        },
        # Edge Windows
        {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
            'platform': 'Win32', 'vendor': 'Google Inc.',
            'webgl_vendor': 'Google Inc. (Intel)',
            'webgl_renderer': 'ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)',
            'viewport': (1920, 1080), 'timezone': 'America/New_York',
            'locale': 'en-US', 'langs': ['en-US', 'en'],
            'sec_ch_ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec_ch_ua_platform': '"Windows"', 'sec_ch_ua_mobile': '?0',
            'hardware_concurrency': 8, 'device_memory': 8,
        },
    ]

    def __init__(self, sticky=True):
        self.sticky = sticky
        self._current_fingerprint = None
        self._session_counter = 0

    @classmethod
    def from_crawler(cls, crawler):
        sticky = crawler.settings.getbool('FINGERPRINT_STICKY', True)
        mw = cls(sticky=sticky)
        crawler.signals.connect(mw.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(mw.spider_closed, signal=signals.spider_closed)
        return mw

    def spider_opened(self, spider):
        self._current_fingerprint = random.choice(self.FINGERPRINTS)
        logger.info(
            f"Fingerprint: {self._current_fingerprint['platform']} | "
            f"{self._current_fingerprint['locale']}"
        )

    def spider_closed(self, spider):
        logger.info(f"Fingerprint requests: {self._session_counter}")

    def process_request(self, request, spider):
        if request.meta.get('fingerprint'):
            fp = request.meta['fingerprint']
        elif self.sticky and self._current_fingerprint:
            fp = self._current_fingerprint
        else:
            fp = random.choice(self.FINGERPRINTS)
            request.meta['fingerprint'] = fp

        for h in ['User-Agent', 'Accept-Language', 'Accept-Encoding',
                  'Sec-CH-UA', 'Sec-CH-UA-Mobile', 'Sec-CH-UA-Platform']:
            request.headers.pop(h, None)

        request.headers['User-Agent'] = fp['user_agent']
        request.headers['Accept'] = (
            'text/html,application/xhtml+xml,application/xml;q=0.9,'
            'image/avif,image/webp,image/apng,*/*;q=0.8,'
            'application/signed-exchange;v=b3;q=0.7'
        )
        request.headers['Accept-Language'] = ','.join(
            [f"{lang};q={0.9 - i*0.1:.1f}" for i, lang in enumerate(fp['langs'])]
        )
        request.headers['Accept-Encoding'] = 'gzip, deflate, br, zstd'
        request.headers['Upgrade-Insecure-Requests'] = '1'
        request.headers['Sec-Fetch-Dest'] = 'document'
        request.headers['Sec-Fetch-Mode'] = 'navigate'
        request.headers['Sec-Fetch-Site'] = 'none'
        request.headers['Sec-Fetch-User'] = '?1'
        request.headers['Cache-Control'] = 'max-age=0'

        if fp.get('sec_ch_ua'):
            request.headers['Sec-CH-UA'] = fp['sec_ch_ua']
            request.headers['Sec-CH-UA-Mobile'] = fp['sec_ch_ua_mobile']
            request.headers['Sec-CH-UA-Platform'] = fp['sec_ch_ua_platform']

        self._session_counter += 1
        return None
