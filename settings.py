import os

BOT_NAME = 'traffic_bot'

SPIDER_MODULES = ['spiders']
NEWSPIDER_MODULE = 'spiders'

ROBOTSTXT_OBEY = False

REQUEST_FINGERPRINTER_IMPLEMENTATION = '2.7'
TWISTED_REACTOR = 'twisted.internet.asyncioreactor.AsyncioSelectorReactor'

FEED_EXPORT_ENCODING = 'utf-8'

DOWNLOAD_DELAY = 3
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS = 2
CONCURRENT_REQUESTS_PER_DOMAIN = 1

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 3
AUTOTHROTTLE_MAX_DELAY = 15
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = False

RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429, 403]

DOWNLOAD_TIMEOUT = 60
DNS_TIMEOUT = 30

COOKIES_ENABLED = True
COOKIES_DEBUG = False

TELNETCONSOLE_ENABLED = False

LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'

ZYTE_API_KEY = os.environ.get('ZYTE_API_KEY', '')

# Zyte API Addon - only enable if compatible version
# Scrapy 2.19+ has compatibility issues with scrapy-zyte-api
# Set USE_ZYTE_API=true to enable (requires compatible versions)
USE_ZYTE_API = os.environ.get('USE_ZYTE_API', 'false').lower() == 'true'

if USE_ZYTE_API:
    ADDONS = {
        'scrapy_zyte_api.Addon': 500,
    }
    ZYTE_API_TRANSPARENT_MODE = False
    ZYTE_API_AUTOMATIC_PARSING = False
else:
    ADDONS = {}

ZYTE_API_TRANSPARENT_MODE = False
ZYTE_API_AUTOMATIC_PARSING = False

DOWNLOADER_MIDDLEWARES = {
    'middlewares.fingerprint_rotator.FingerprintRotatorMiddleware': 542,
    'middlewares.proxy_rotator.FreeProxyRotatorMiddleware': 543,
    'middlewares.zyte_middleware.ZyteMiddleware': 544,
}

FREE_PROXY_LIST_URL = os.environ.get('FREE_PROXY_LIST_URL', 'https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/all/data.txt')

ROTATING_PROXY_PAGE_RETRY_TIMES = 5
ROTATING_PROXY_BACKOFF_BASE = 300
ROTATING_PROXY_BACKOFF_CAP = 3600

ITEM_PIPELINES = {
    'pipelines.MongoPipeline': 300,
}

MONGODB_URI = os.environ.get('MONGODB_URI', '')
MONGODB_DATABASE = 'traffic_bot'

EXTENSIONS = {
    'scrapy.extensions.closespider.CloseSpider': 500,
}

CLOSESPIDER_PAGECOUNT = 20
CLOSESPIDER_ITEMCOUNT = 50
CLOSESPIDER_ERRORCOUNT = 10

HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 3600
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504, 400, 401, 403, 404, 408, 429]
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}

SPIDER_MIDDLEWARES = {
    'scrapy.spidermiddlewares.httperror.HttpErrorMiddleware': 50,
    'scrapy.spidermiddlewares.referer.RefererMiddleware': 700,
    'scrapy.spidermiddlewares.urllength.UrlLengthMiddleware': 800,
    'scrapy.spidermiddlewares.depth.DepthMiddleware': 900,
}

DEPTH_LIMIT = 3
DEPTH_STATS_VERBOSE = True
DEPTH_PRIORITY = 1
SCHEDULER_DISK_QUEUE = 'scrapy.squeues.PickleFifoDiskQueue'
SCHEDULER_MEMORY_QUEUE = 'scrapy.squeues.FifoMemoryQueue'