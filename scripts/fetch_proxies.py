#!/usr/bin/env python3
"""
Free Proxy Fetcher and Tester
Fetches proxies from multiple GitHub sources and tests them
"""

import requests
import re
import threading
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

PROXY_SOURCES = [
    'https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/all/data.txt',
    'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
    'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt',
    'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt',
    'https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt',
    'https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt',
    'https://raw.githubusercontent.com/sunny9577/proxy-scraper/main/proxies.txt',
    'https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt',
    'https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt',
    'https://raw.githubusercontent.com/mmpx12/proxy-list/main/http.txt',
]

TEST_URLS = [
    'http://httpbin.org/ip',
    'https://httpbin.org/ip',
    'http://ip-api.com/json',
]

def fetch_proxies(sources=None):
    """Fetch proxies from multiple sources"""
    sources = sources or PROXY_SOURCES
    all_proxies = set()
    
    print(f"Fetching proxies from {len(sources)} sources...")
    
    for url in sources:
        try:
            print(f"  Fetching: {url}")
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                count = 0
                for line in response.text.strip().split('\n'):
                    line = line.strip()
                    if line and is_valid_proxy(line):
                        all_proxies.add(line)
                        count += 1
                print(f"    Found {count} valid proxies")
            else:
                print(f"    Failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"    Error: {e}")
    
    print(f"\nTotal unique proxies: {len(all_proxies)}")
    return list(all_proxies)

def is_valid_proxy(proxy):
    """Validate proxy format"""
    patterns = [
        r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}$',
        r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}:\w+:\w+$',
    ]
    return any(re.match(pattern, proxy) for pattern in patterns)

def test_proxy(proxy, timeout=10):
    """Test a single proxy"""
    proxies = {
        'http': f'http://{proxy}',
        'https': f'http://{proxy}',
    }
    
    for url in TEST_URLS:
        try:
            start = time.time()
            response = requests.get(url, proxies=proxies, timeout=timeout)
            elapsed = time.time() - start
            
            if response.status_code == 200:
                return {
                    'proxy': proxy,
                    'working': True,
                    'response_time': round(elapsed, 2),
                    'test_url': url,
                }
        except Exception:
            continue
    
    return {'proxy': proxy, 'working': False}

def test_proxies(proxies, max_workers=50, timeout=10):
    """Test multiple proxies concurrently"""
    print(f"\nTesting {len(proxies)} proxies with {max_workers} workers...")
    
    working = []
    failed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_proxy = {
            executor.submit(test_proxy, proxy, timeout): proxy 
            for proxy in proxies
        }
        
        for future in as_completed(future_to_proxy):
            result = future.result()
            if result['working']:
                working.append(result)
                print(f"  ✓ {result['proxy']} - {result['response_time']}s")
            else:
                failed += 1
                if failed % 100 == 0:
                    print(f"  ✗ {failed} failed so far...")
    
    working.sort(key=lambda x: x['response_time'])
    print(f"\nResults: {len(working)} working, {failed} failed")
    return working

def save_proxies(proxies, filename='working_proxies.txt'):
    """Save working proxies to file"""
    with open(filename, 'w') as f:
        for p in proxies:
            f.write(f"{p['proxy']}\n")
    print(f"Saved {len(proxies)} proxies to {filename}")

def load_proxies(filename='working_proxies.txt'):
    """Load proxies from file"""
    try:
        with open(filename, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Free Proxy Fetcher and Tester')
    parser.add_argument('--fetch', action='store_true', help='Fetch proxies from sources')
    parser.add_argument('--test', action='store_true', help='Test proxies')
    parser.add_argument('--all', action='store_true', help='Fetch and test')
    parser.add_argument('--input', default='proxies.txt', help='Input proxy file')
    parser.add_argument('--output', default='working_proxies.txt', help='Output file')
    parser.add_argument('--workers', type=int, default=50, help='Max workers for testing')
    parser.add_argument('--timeout', type=int, default=10, help='Timeout per proxy')
    
    args = parser.parse_args()
    
    if args.all or args.fetch:
        proxies = fetch_proxies()
        if proxies:
            with open(args.input, 'w') as f:
                for p in proxies:
                    f.write(p + '\n')
            print(f"Saved raw proxies to {args.input}")
    
    if args.all or args.test:
        proxies = load_proxies(args.input)
        if proxies:
            working = test_proxies(proxies, max_workers=args.workers, timeout=args.timeout)
            save_proxies(working, args.output)
            
            # Print top 10 fastest
            print("\nTop 10 fastest proxies:")
            for p in working[:10]:
                print(f"  {p['proxy']} - {p['response_time']}s")
        else:
            print(f"No proxies found in {args.input}. Run with --fetch first.")
    
    if not (args.fetch or args.test or args.all):
        parser.print_help()

if __name__ == '__main__':
    main()