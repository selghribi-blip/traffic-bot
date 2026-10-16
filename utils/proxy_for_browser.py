# utils/proxy_for_browser.py
# Browser proxy provider with mobile priority + SOCKS5 detection
import os
import random
import logging

logger = logging.getLogger(__name__)


class BrowserProxyProvider:
    """
    Reads manual_proxies.txt and prioritizes:
    1) Mobile proxies (4G/5G) - Best for Adsterra
    2) Residential proxies - Good for Adsterra
    3) Datacenter proxies - Fallback (ads may NOT show)
    """

    def __init__(self, path='manual_proxies.txt'):
        self.path = path
        self.all_proxies = []
        self.mobile_proxies = []
        self.residential_proxies = []
        self.datacenter_proxies = []
        self.socks5_proxies = []     # ← جديد
        self._load()

    def _load(self):
        if not os.path.isfile(self.path):
            logger.warning(f"Proxy file not found: {self.path}")
            return

        with open(self.path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                self.all_proxies.append(line)
                lower = line.lower()

                # 0) SOCKS5 (before other checks)
                if lower.startswith('socks5://') or lower.startswith('socks5h://'):
                    self.socks5_proxies.append(line)
                    continue

                # 1) Mobile proxies (4G/5G)
                if any(kw in lower for kw in ['mobile', '4g', '5g', 'lte', 'cellular']):
                    self.mobile_proxies.append(line)
                    continue

                # 2) Residential proxies (http:// with auth)
                if line.startswith('http://') and '@' in line:
                    self.residential_proxies.append(line)
                    continue

                # 3) Datacenter (ip:port or ip:port:user:pass)
                self.datacenter_proxies.append(line)

        logger.info(
            f"BrowserProxyProvider: {len(self.all_proxies)} total | "
            f"{len(self.mobile_proxies)} Mobile | "
            f"{len(self.residential_proxies)} Residential | "
            f"{len(self.socks5_proxies)} SOCKS5 | "
            f"{len(self.datacenter_proxies)} Datacenter"
        )

        # Warn if no Mobile/Residential (critical for Adsterra)
        if not self.mobile_proxies and not self.residential_proxies:
            logger.warning(
                "⚠️ NO Mobile or Residential proxies found! "
                "Adsterra ads will NOT show with Datacenter proxies."
            )

    def pick(self):
        """
        Pick proxy by priority:
        1) Mobile (4G/5G) - Best for Adsterra
        2) Residential - Good
        3) Datacenter - Fallback (ads may not show)
        """
        # 1) Mobile proxies (best)
        if self.mobile_proxies:
            chosen = random.choice(self.mobile_proxies)
            endpoint = chosen.split('@')[-1] if '@' in chosen else chosen[:40]
            logger.info(f"✅ Using MOBILE proxy: {endpoint}")
            return self._format(chosen)

        # 2) Residential proxies
        if self.residential_proxies:
            chosen = random.choice(self.residential_proxies)
            endpoint = chosen.split('@')[-1] if '@' in chosen else chosen[:40]
            logger.info(f"✅ Using RESIDENTIAL proxy: {endpoint}")
            return self._format(chosen)

        # 3) Datacenter proxies (warning)
        if self.datacenter_proxies:
            chosen = random.choice(self.datacenter_proxies)
            logger.warning(
                f"⚠️ Using DATACENTER proxy (ads may NOT show): {chosen[:40]}"
            )
            return self._format(chosen)

        logger.warning("❌ No proxy available - direct connection")
        return None

    @staticmethod
    def _format(raw):
        """Format proxy string for Selenium."""
        raw = raw.strip()
        if not raw:
            return None

        # Already has scheme (http://, socks5://, socks5h://)
        if '://' in raw:
            return raw

        # user:pass@host:port → http://user:pass@host:port
        if '@' in raw:
            return f"http://{raw}"

        parts = raw.split(':')

        # ip:port:user:pass → http://user:pass@ip:port
        if len(parts) == 4:
            ip, port, user, pwd = parts
            return f"http://{user}:{pwd}@{ip}:{port}"

        # ip:port → http://ip:port
        if len(parts) == 2:
            return f"http://{raw}"

        return f"http://{raw}"
