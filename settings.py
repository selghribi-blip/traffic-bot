# settings.py
import os

BOT_NAME = 'traffic_bot'

SPIDER_MODULES = ['spiders']
NEWSPIDER_MODULE = 'spiders'

ROBOTSTXT_OBEY = False

# ← احذف REQUEST_FINGERPRINTER_IMPLEMENTATION (مهجور)
# ← احذف TWISTED_REACTOR (يصبح افتراضيًا في Scrapy 2.12+)
#   إذا احتجته، استخدم:
# TWISTED_REACTOR = 'twisted.internet.asyncioreactor.AsyncioSelectorReactor'

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
# ← احذف 403 (سبب حلقات مع Zyte)
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]

DOWNLOAD_TIMEOUT = 60
DNS_TIMEOUT = 30

COOKIES_ENABLED = True
COOKIES_DEBUG = False

TELNETCONSOLE_ENABLED = False

# ---------------- Logging ----------------
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'

# ==================== Zyte API ====================
ZYTE_API_KEY = os.environ.get('ZYTE_API_KEY', '').strip()

# فعّل الـ addon تلقائيًا إذا المفتاح موجود
if ZYTE_API_KEY:
    USE_ZYTE_API = True
    ADDONS = {
        'scrapy_zyte_api.Addon': 0,          # ← أولوية 0 (قياسية)
    }
    ZYTE_API_TRANSPARENT_MODE = True          # ← اسمح لـ Zyte بالتعامل مع كل الطلبات
    ZYTE_API_AUTOMATIC_PARSING = False

    DOWNLOAD_HANDLERS = {
        'http':  'scrapy_zyte_api.ScrapyZyteAPIDownloadHandler',
        'https': 'scrapy_zyte_api.ScrapyZyteAPIDownloadHandler',
    }
else:
    USE_ZYTE_API = False
    ADDONS = {}
    ZYTE_API_TRANSPARENT_MODE = False
    ZYTE_API_AUTOMATIC_PARSING = False

# ---------------- Downloader Middlewares ----------------
# ← احذف ZyteMiddleware (الـ addon يتولاه الآن)
DOWNLOADER_MIDDLEWARES = {
    'middlewares.fingerprint_rotator.FingerprintRotatorMiddleware': 542,
    'middlewares.proxy_rotator.FreeProxyRotatorMiddleware': 543,
    # إذا Zyte مفعل: استخدم middleware الرسمي بدل المخصص
    **(
        {'scrapy_zyte_api.ScrapyZyteAPIDownloaderMiddleware': 1000}
        if USE_ZYTE_API else {}
    ),
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
# ← ارفع الحدود لأن الأخطاء الأولى عادية
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

# ---------------- Spider Middlewares ----------------
# ← احذف التعريف الصريح — اترك Scrapy يستخدم الافتراضية كاملة
# إذا أردت تخصيص واحد فقط، استخدم dict يبدأ بكل الافتراضية ثم عدّل
# الأفضل: احذف هذه الكتلة بالكامل

# ---------------- Depth ----------------
DEPTH_LIMIT = 3
DEPTH_STATS_VERBOSE = True
DEPTH_PRIORITY = 1

# ---------------- Scheduler ----------------
SCHEDULER_DISK_QUEUE = 'scrapy.squeues.PickleFifoDiskQueue'
SCHEDULER_MEMORY_QUEUE = 'scrapy.squeues.FifoMemoryQueue'
