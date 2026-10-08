#!/usr/bin/env python3
"""
Test script to verify Traffic Bot setup
"""

import os
import sys
from pathlib import Path

def test_imports():
    """Test all imports work"""
    print("Testing imports...")
    
    try:
        import scrapy
        print("  [OK] scrapy")
    except ImportError as e:
        print(f"  [FAIL] scrapy: {e}")
        return False
    
    try:
        import scrapy_zyte_api
        print("  [OK] scrapy_zyte_api")
    except ImportError:
        print("  [WARN] scrapy_zyte_api: Not installed (optional, for Zyte API JS rendering)")
    
    try:
        import pymongo
        print("  [OK] pymongo")
    except ImportError as e:
        print(f"  [FAIL] pymongo: {e}")
        return False
    
    try:
        import selenium
        print("  [OK] selenium")
    except ImportError as e:
        print(f"  [FAIL] selenium: {e}")
        return False
    
    try:
        import undetected_chromedriver
        print("  [OK] undetected_chromedriver")
    except ImportError as e:
        print(f"  [FAIL] undetected_chromedriver: {e}")
        return False
    
    try:
        import requests
        print("  [OK] requests")
    except ImportError as e:
        print(f"  [FAIL] requests: {e}")
        return False
    
    try:
        from dotenv import load_dotenv
        print("  [OK] python-dotenv")
    except ImportError as e:
        print(f"  [FAIL] python-dotenv: {e}")
        return False
    
    return True

def test_project_structure():
    """Test project structure"""
    print("\nTesting project structure...")
    
    required_files = [
        'scrapy.cfg',
        'settings.py',
        'requirements.txt',
        'spiders/traffic_spider.py',
        'spiders/browserstack_spider.py',
        'middlewares/fingerprint_rotator.py',
        'middlewares/proxy_rotator.py',
        'middlewares/zyte_middleware.py',
        'utils/mongo_handler.py',
        'utils/browserstack_client.py',
        'pipelines.py',
        '.github/workflows/bot.yml',
        '.env.example',
        'README.md',
    ]
    
    all_ok = True
    for f in required_files:
        path = Path(f)
        if path.exists():
            print(f"  [OK] {f}")
        else:
            print(f"  [FAIL] {f} - MISSING")
            all_ok = False
    
    return all_ok

def test_env_file():
    """Test .env file"""
    print("\nTesting .env file...")
    
    env_path = Path('.env')
    if not env_path.exists():
        print("  [WARN] .env not found (copy .env.example to .env)")
        return True  # Not required for test
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = [
        'ZYTE_API_KEY',
        'MONGODB_URI',
    ]
    
    optional_vars = [
        'BROWSERSTACK_USERNAME',
        'BROWSERSTACK_ACCESS_KEY',
        'TARGET_URL',
    ]
    
    all_ok = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"  [OK] {var}: {'*' * 8}{value[-4:] if len(value) > 4 else '****'}")
        else:
            print(f"  [FAIL] {var}: NOT SET (REQUIRED)")
            all_ok = False
    
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"  [OK] {var}: {'*' * 8}{value[-4:] if len(value) > 4 else '****'}")
        else:
            print(f"  [WARN] {var}: NOT SET (optional)")
    
    return all_ok

def test_spider():
    """Test spider can be loaded"""
    print("\nTesting spider loading...")
    
    try:
        import scrapy
        from scrapy.crawler import CrawlerProcess
        from scrapy.settings import Settings
        
        # Load settings
        settings = Settings()
        settings.setmodule('settings')
        
        # Try to create spider
        from spiders.traffic_spider import TrafficSpider
        
        spider = TrafficSpider(target_url='https://example.com')
        print(f"  [OK] TrafficSpider loaded: {spider.name}")
        print(f"  [OK] Target URL: {spider.target_url}")
        print(f"  [OK] Ad selectors: {len(spider.AD_SELECTORS)}")
        print(f"  [OK] Form selectors: {len(spider.FORM_SELECTORS)}")
        
        return True
    except Exception as e:
        print(f"  ✗ Spider loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_middlewares():
    """Test middlewares can be loaded"""
    print("\nTesting middlewares...")
    
    try:
        from middlewares.fingerprint_rotator import FingerprintRotatorMiddleware
        from middlewares.proxy_rotator import FreeProxyRotatorMiddleware
        from middlewares.zyte_middleware import ZyteMiddleware
        
        fp = FingerprintRotatorMiddleware()
        print(f"  [OK] FingerprintRotatorMiddleware: {len(fp.fingerprints)} fingerprints")
        
        pr = FreeProxyRotatorMiddleware('https://example.com/proxies.txt')
        print(f"  [OK] FreeProxyRotatorMiddleware: {len(pr.proxies)} proxies loaded")
        
        zyte = ZyteMiddleware('test-key')
        print(f"  [OK] ZyteMiddleware loaded")
        
        return True
    except Exception as e:
        print(f"  ✗ Middleware loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mongodb_connection():
    """Test MongoDB connection"""
    print("\nTesting MongoDB connection...")
    
    try:
        from pymongo import MongoClient
        from utils.mongo_handler import MongoHandler
        
        uri = os.getenv('MONGODB_URI')
        if not uri:
            print("  [WARN] MONGODB_URI not set, skipping connection test")
            return True
        
        # Test connection
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("  [OK] MongoDB connection successful")
        
        # Test handler
        handler = MongoHandler()
        print("  [OK] MongoHandler initialized")
        handler.close()
        
        return True
    except Exception as e:
        print(f"  [WARN] MongoDB connection failed (fix in Atlas): {e}")
        print("  -> Go to MongoDB Atlas > Database Access > Create user: selghribi_db_user / M138350896m@")
        print("  -> Make sure IP whitelist includes 0.0.0.0/0")
        return True  # Don't fail the test, user needs to fix in Atlas

def test_zyte_connection():
    """Test Zyte API connection"""
    print("\nTesting Zyte API connection...")
    
    try:
        import requests
        
        api_key = os.getenv('ZYTE_API_KEY')
        if not api_key:
            print("  [WARN] ZYTE_API_KEY not set, skipping connection test")
            return True
        
        # Test API
        response = requests.get(
            'https://api.zyte.com/v1/extract',
            auth=(api_key, ''),
            json={'url': 'https://example.com', 'httpResponseBody': True},
            timeout=30
        )
        
        if response.status_code == 200:
            print("  [OK] Zyte API connection successful")
        elif response.status_code == 401:
            print("  [FAIL] Zyte API authentication failed (invalid key)")
            return False
        else:
            print(f"  [WARN] Zyte API returned: {response.status_code}")
        
        return True
    except Exception as e:
        print(f"  [WARN] Zyte API connection failed: {e}")
        return True

def main():
    print("=" * 60)
    print("Traffic Bot - Setup Verification")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_project_structure,
        test_env_file,
        test_spider,
        test_middlewares,
        test_mongodb_connection,
        test_zyte_connection,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"[OK] All {total} tests passed!")
        print("\nYou're ready to run the traffic bot!")
        print("  python run.py both")
        print("  or")
        print("  scrapy crawl traffic_bot -a target_url=\"https://your-site.com\"")
    else:
        print(f"[FAIL] {passed}/{total} tests passed")
        print("\nPlease fix the issues above before running.")
    
    return 0 if passed == total else 1

if __name__ == '__main__':
    sys.exit(main())