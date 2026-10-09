# settings.py
import os

BOT_NAME = 'traffic_bot'

SPIDER_MODULES = ['spiders']
NEWSPIDER_MODULE = 'spiders'

# ---------------- Robots ----------------
ROBOTSTXT_OBEY = False

# ---------------- Encoding ----------------
FEED_EXPORT_ENCODING = 'utf-8'

# ---------------- Throttling ----------------
DOWNLOAD_DELAY = 3
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS = 2
CONCURRENT_REQUESTS_PER_DOMAIN = 1

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 3
AUTOTHROTTLE_MAX_DELAY = 15
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = False

# ---------------- Retries ----------------
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]

DOWNLOAD_TIMEOUT = 60
DNS_TIMEOUT = 30

# ---------------- Cookies ----------------
COOKIES_ENABLED = True
COOKIES_DEBUG = False

# ---------------- Console ----------------
TELNETCONSOLE_ENABLED = False

# ---------------- Logging ----------------
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'

# ==================== Zyte API ====================
# ملاحظة: تم تعطيل Zyte بالكامل بسبب عدم توافق
# scrapy-zyte-api مع Scrapy 2.18 (ImportError: create_instance)
# لا حاجة لـ ZYTE_API_KEY هنا
# نعتمد على FreeProxyRotator + FingerprintRotator فقط

ADDONS = {}

# ---------------- Downloader Middlewares ----------------
DOWNLOADER_MIDDLEWARES = {
    'middlewares.fingerprint_rotator.FingerprintRotatorMiddleware': 542,
    'middlewares.proxy_rotator.FreeProxyRotatorMiddleware': 543,
}

# ---------------- Proxies ----------------
FREE_PROXY_LIST_URL = os.environ.get(
    'FREE_PROXY_LIST_URL',
    'https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/all/data.txt',
)

ROTATING_PROXY_PAGE_RETRY_TIMES = 5
ROTATING_PROXY_BACKOFF_BASE = 300
ROTATING_PROXY_BACKOFF_CAP = 3600

# ---------------- Pipelines ----------------
ITEM_PIPELINES = {
    'pipelines.MongoPipeline': 300,
}

MONGODB_URI = os.environ.get('MONGODB_URI', '')
MONGODB_DATABASE = 'traffic_bot'

# ---------------- CloseSpider ----------------
CLOSESPIDER_PAGECOUNT = 50
CLOSESPIDER_ITEMCOUNT = 100
CLOSESPIDER_ERRORCOUNT = 30

EXTENSIONS = {
    'scrapy.extensions.closespider.CloseSpider': 500,
}

# ---------------- HTTP Cache ----------------
HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 3600
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504, 400, 401, 403, 404, 408, 429]
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

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
DEPTH_LIMIT = 3
DEPTH_STATS_VERBOSE = True
DEPTH_PRIORITY = 1

# ---------------- Scheduler ----------------
SCHEDULER_DISK_QUEUE = 'scrapy.squeues.PickleFifoDiskQueue'
SCHEDULER_MEMORY_QUEUE = 'scrapy.squeues.FifoMemoryQueue'

# ---------------- Target URL ----------------
TARGET_URL = os.environ.get('TARGET_URL', 'https://www.forjo.tech/')
