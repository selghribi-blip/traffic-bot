# utils/proxy_for_browser.py
# Browser proxy provider with mobile proxy priority
import os
import random
import logging

logger = logging.getLogger(__name__)


class BrowserProxyProvider:
    """
    Reads manual_proxies.txt and prioritizes:
    1) Mobile proxies (4G/5G) - Best for Adsterra
    2) Residential proxies - Good for Adsterra
    3) Datacenter proxies - Fallback
    """

    def __init__(self, path='manual_proxies.txt'):
        self.path = path
        self.all_proxies = []
        self.mobile_proxies = []
        self.residential_proxies = []
        self.datacenter_proxies = []
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

                # 1) Mobile proxies (4G/5G) - detect by keywords or ports
                # Mobile proxies usually use ports like 1080, 3129, or contain "mobile" in URL
                if any(kw in line.lower() for kw in ['mobile', '4g', '5g', 'lte', 'cellular']):
                    self.mobile_proxies.append(line)
                    continue

                # 2) Residential proxies (contain @ and http://)
                if line.startswith('http://') and '@' in line:
                    self.residential_proxies.append(line)
                    continue

                # 3) Datacenter proxies (ip:port:user:pass or ip:port)
                self.datacenter_proxies.append(line)

        logger.info(
            f"BrowserProxyProvider: {len(self.all_proxies)} total | "
            f"{len(self.mobile_proxies)} Mobile | "
            f"{len(self.residential_proxies)} Residential | "
            f"{len(self.datacenter_proxies)} Datacenter"
        )

    def pick(self):
        """
        Pick proxy with priority:
        1) Mobile (4G/5G) - Best for Adsterra
        2) Residential - Good
        3) Datacenter - Fallback
        """
        # 1) Mobile proxies (best for Adsterra)
        if self.mobile_proxies:
            chosen = random.choice(self.mobile_proxies)
            logger.info(f"Using Mobile proxy: {chosen.split('@')[-1] if '@' in chosen else chosen[:30]}")
            return self._format(chosen)

        # 2) Residential proxies
        if self.residential_proxies:
            chosen = random.choice(self.residential_proxies)
            logger.info(f"Using Residential proxy: {chosen.split('@')[-1] if '@' in chosen else chosen[:30]}")
            return self._format(chosen)

        # 3) Datacenter proxies (fallback)
        if self.datacenter_proxies:
            chosen = random.choice(self.datacenter_proxies)
            logger.warning(f"Using Datacenter proxy (fallback): {chosen[:30]}")
            return self._format(chosen)

        logger.warning("No proxy available - direct connection")
        return None

    @staticmethod
    def _format(raw):
        """Format proxy string for Selenium."""
        raw = raw.strip()
        if not raw:
            return None
        if '://' in raw:
            return raw
        if '@' in raw:
            return f"http://{raw}"

        parts = raw.split(':')
        # ip:port:user:pass -> http://user:pass@ip:port
        if len(parts) == 4:
            ip, port, user, pwd = parts
            return f"http://{user}:{pwd}@{ip}:{port}"
        # ip:port -> http://ip:port
        if len(parts) == 2:
            return f"http://{raw}"
        return f"http://{raw}"
