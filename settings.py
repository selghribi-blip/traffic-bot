# settings.py
import os

BOT_NAME = 'traffic_bot'
SPIDER_MODULES = ['spiders']
NEWSPIDER_MODULE = 'spiders'

ROBOTSTXT_OBEY = False
FEED_EXPORT_ENCODING = 'utf-8'

# ---------------- Throttling ----------------
DOWNLOAD_DELAY = 2
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = False

# ---------------- Retries ----------------
RETRY_ENABLED = True
RETRY_TIMES = 1
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]

DOWNLOAD_TIMEOUT = 45
DNS_TIMEOUT = 15

COOKIES_ENABLED = True
TELNETCONSOLE_ENABLED = False

# ---------------- Logging ----------------
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'

ADDONS = {}

# ---------------- Downloader Middlewares ----------------
DOWNLOADER_MIDDLEWARES = {
    'middlewares.fingerprint_rotator.FingerprintRotatorMiddleware': 542,
    'middlewares.proxy_rotator.FreeProxyRotatorMiddleware': 555,
}

# ---------------- Redirects ----------------
REDIRECT_ENABLED = True
REDIRECT_MAX_TIMES = 3
HTTPERROR_ALLOWED_CODES = [302, 403, 429]

# ---------------- Proxies ----------------
FREE_PROXY_LIST_URL = []
ROTATING_PROXY_PAGE_RETRY_TIMES = 3

# ---------------- Pipelines ----------------
ITEM_PIPELINES = {
    'pipelines.MongoPipeline': 300,
}

MONGODB_URI = os.environ.get('MONGODB_URI', '')
MONGODB_DATABASE = 'traffic_bot'

# ---------------- CloseSpider ----------------
CLOSESPIDER_PAGECOUNT = 200
CLOSESPIDER_ITEMCOUNT = 500
CLOSESPIDER_ERRORCOUNT = 100
CLOSESPIDER_TIMEOUT = 1800

EXTENSIONS = {
    'scrapy.extensions.closespider.CloseSpider': 500,
}

# ---------------- HTTP Cache ----------------
HTTPCACHE_ENABLED = False

# ---------------- Headers ----------------
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)

DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}

# ---------------- Depth ----------------
DEPTH_LIMIT = 5
DEPTH_STATS_VERBOSE = True
DEPTH_PRIORITY = 1

# ---------------- Scheduler ----------------
SCHEDULER_DISK_QUEUE = 'scrapy.squeues.PickleFifoDiskQueue'
SCHEDULER_MEMORY_QUEUE = 'scrapy.squeues.FifoMemoryQueue'

# ---------------- Target ----------------
TARGET_URL = os.environ.get('TARGET_URL', 'https://www.forjo.tech/')
