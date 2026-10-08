import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

class Config:
    ZYTE_API_KEY = os.getenv('ZYTE_API_KEY', '')
    MONGODB_URI = os.getenv('MONGODB_URI', '')
    BROWSERSTACK_USERNAME = os.getenv('BROWSERSTACK_USERNAME', '')
    BROWSERSTACK_ACCESS_KEY = os.getenv('BROWSERSTACK_ACCESS_KEY', '')
    TARGET_URL = os.getenv('TARGET_URL', 'https://www.forjo.tech/')
    FREE_PROXY_LIST_URL = os.getenv('FREE_PROXY_LIST_URL', '')
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    DOWNLOAD_DELAY = int(os.getenv('DOWNLOAD_DELAY', '3'))
    CONCURRENT_REQUESTS = int(os.getenv('CONCURRENT_REQUESTS', '2'))
    
    BROWSERSTACK_BROWSER = os.getenv('BROWSERSTACK_BROWSER', 'chrome')
    BROWSERSTACK_OS = os.getenv('BROWSERSTACK_OS', 'Windows')
    BROWSERSTACK_OS_VERSION = os.getenv('BROWSERSTACK_OS_VERSION', '11')
    BROWSERSTACK_LOCAL = os.getenv('BROWSERSTACK_LOCAL', 'false').lower() == 'true'
    
    RUN_MODE = os.getenv('RUN_MODE', 'both')
    
    MAX_PAGES_PER_RUN = int(os.getenv('MAX_PAGES_PER_RUN', '20'))
    MAX_ADS_PER_RUN = int(os.getenv('MAX_ADS_PER_RUN', '50'))
    MAX_FORMS_PER_RUN = int(os.getenv('MAX_FORMS_PER_RUN', '10'))
    
    @classmethod
    def validate(cls):
        missing = []
        if not cls.ZYTE_API_KEY:
            missing.append('ZYTE_API_KEY')
        if not cls.MONGODB_URI:
            missing.append('MONGODB_URI')
        if cls.RUN_MODE in ['browserstack', 'both'] and not (cls.BROWSERSTACK_USERNAME and cls.BROWSERSTACK_ACCESS_KEY):
            missing.append('BROWSERSTACK_USERNAME and BROWSERSTACK_ACCESS_KEY')
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        return True
    
    @classmethod
    def get_scrapy_settings(cls):
        return {
            'ZYTE_API_KEY': cls.ZYTE_API_KEY,
            'MONGODB_URI': cls.MONGODB_URI,
            'FREE_PROXY_LIST_URL': cls.FREE_PROXY_LIST_URL,
            'LOG_LEVEL': cls.LOG_LEVEL,
            'DOWNLOAD_DELAY': cls.DOWNLOAD_DELAY,
            'CONCURRENT_REQUESTS': cls.CONCURRENT_REQUESTS,
        }

config = Config()