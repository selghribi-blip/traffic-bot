#!/usr/bin/env python3
"""
Traffic Bot - Quick Start Script
Run this script to easily start the traffic bot in different modes
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def check_env():
    """Check if .env file exists"""
    env_path = Path('.env')
    if not env_path.exists():
        print("❌ .env file not found!")
        print("   Copy .env.example to .env and fill in your credentials:")
        print("   cp .env.example .env")
        print("   nano .env")
        return False
    return True

def load_env():
    """Load environment variables from .env"""
    from dotenv import load_dotenv
    load_dotenv()

def run_scrapy(target_url, **kwargs):
    """Run Scrapy spider"""
    cmd = ['scrapy', 'crawl', 'traffic_bot', '-a', f'target_url={target_url}']
    
    if kwargs.get('output'):
        cmd.extend(['-O', kwargs['output']])
    
    if kwargs.get('log_level'):
        cmd.extend(['-L', kwargs['log_level']])
    
    if kwargs.get('pages'):
        cmd.extend(['-s', f'CLOSESPIDER_PAGECOUNT={kwargs["pages"]}'])
    
    print(f"🚀 Running Scrapy spider: {' '.join(cmd)}")
    return subprocess.run(cmd)

def run_browserstack(target_url, use_browserstack=True, **kwargs):
    """Run BrowserStack spider"""
    cmd = [
        'scrapy', 'crawl', 'browserstack_bot',
        '-a', f'target_url={target_url}',
        '-a', f'use_browserstack={str(use_browserstack).lower()}'
    ]
    
    if kwargs.get('output'):
        cmd.extend(['-O', kwargs['output']])
    
    if kwargs.get('log_level'):
        cmd.extend(['-L', kwargs['log_level']])
    
    mode = "BrowserStack" if use_browserstack else "Local Browser"
    print(f"🌐 Running {mode} spider: {' '.join(cmd)}")
    return subprocess.run(cmd)

def run_both(target_url, **kwargs):
    """Run both spiders"""
    print("=" * 60)
    print("Running BOTH Scrapy and BrowserStack spiders")
    print("=" * 60)
    
    # Run Scrapy first
    result1 = run_scrapy(target_url, **kwargs)
    
    print("\n" + "=" * 60)
    
    # Run BrowserStack
    use_bs = os.getenv('BROWSERSTACK_USERNAME') and os.getenv('BROWSERSTACK_ACCESS_KEY')
    result2 = run_browserstack(target_url, use_browserstack=use_bs, **kwargs)
    
    return result1, result2

def main():
    parser = argparse.ArgumentParser(description='Traffic Bot - Quick Start')
    parser.add_argument('mode', choices=['scrapy', 'browserstack', 'local', 'both'], 
                       default='both', nargs='?',
                       help='Run mode (default: both)')
    parser.add_argument('-u', '--url', default=None,
                       help='Target URL (default: from .env or forjo.tech)')
    parser.add_argument('-o', '--output', default=None,
                       help='Output file (JSON)')
    parser.add_argument('-l', '--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Log level')
    parser.add_argument('-p', '--pages', type=int, default=None,
                       help='Max pages to crawl')
    parser.add_argument('--no-browserstack', action='store_true',
                       help='Force local browser mode')
    
    args = parser.parse_args()
    
    # Check environment
    if not check_env():
        sys.exit(1)
    
    load_env()
    
    # Get target URL
    target_url = args.url or os.getenv('TARGET_URL', 'https://www.forjo.tech/')
    
    print(f"🎯 Target URL: {target_url}")
    print(f"⚙️  Mode: {args.mode}")
    print(f"📝 Log Level: {args.log_level}")
    if args.pages:
        print(f"📄 Max Pages: {args.pages}")
    print("-" * 60)
    
    # Run based on mode
    if args.mode == 'scrapy':
        result = run_scrapy(target_url, output=args.output, log_level=args.log_level, pages=args.pages)
        sys.exit(result.returncode)
    
    elif args.mode == 'browserstack':
        use_bs = not args.no_browserstack
        result = run_browserstack(target_url, use_browserstack=use_bs, 
                                 output=args.output, log_level=args.log_level)
        sys.exit(result.returncode)
    
    elif args.mode == 'local':
        result = run_browserstack(target_url, use_browserstack=False,
                                 output=args.output, log_level=args.log_level)
        sys.exit(result.returncode)
    
    elif args.mode == 'both':
        results = run_both(target_url, output=args.output, log_level=args.log_level, pages=args.pages)
        # Exit with error if any failed
        for r in results:
            if r.returncode != 0:
                sys.exit(r.returncode)

if __name__ == '__main__':
    main()