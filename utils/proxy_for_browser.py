# utils/proxy_for_browser.py
# Browser proxy provider with STRICT classification
import os
import re
import random
import logging

logger = logging.getLogger(__name__)


class BrowserProxyProvider:
    """
    Reads manual_proxies.txt and prioritizes:
    1) Mobile proxies (4G/5G)
    2) Residential proxies (TrueProxies, Oxylabs, Bright Data, etc.)
    3) Datacenter proxies (ProxyScrape, Webshare, etc.)
    """

    # Strict mobile keywords — must be a separate word
    MOBILE_PATTERN = re.compile(
        r'(?:^|[^a-z0-9])(mobile|cellular|lte|4g|5g)(?:[^a-z0-9]|$)',
        re.IGNORECASE
    )

    # Known residential hosts (add more as needed)
    RESIDENTIAL_HOSTS = [
       #'resi-ipv4-1.gw.tprx.io',   # TrueProxies
        'pr.oxylabs.io',              # Oxylabs
       #'residentialboson.quantumproxies.io',   # QuantumProxies ← جديد
       #'resi.',                      # generic residential prefix
       #'residential.',
       #'resi-',                      # generic residential
    ]

    def __init__(self, path='manual_proxies.txt'):
        self.path = path
        self.all_proxies = []
        self.mobile_proxies = []
        self.residential_proxies = []
        self.socks5_proxies = []
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
                lower = line.lower()

                # 0) SOCKS5 (first)
                if lower.startswith('socks5://') or lower.startswith('socks5h://'):
                    self.socks5_proxies.append(line)
                    continue

                # 1) Mobile (strict)
                if self.MOBILE_PATTERN.search(lower):
                    self.mobile_proxies.append(line)
                    continue

                # 2) Residential: MUST match known residential host
                if self._is_residential(line):
                    self.residential_proxies.append(line)
                    continue

                # 3) Everything else = Datacenter
                self.datacenter_proxies.append(line)

        logger.info(
            f"BrowserProxyProvider: {len(self.all_proxies)} total | "
            f"{len(self.mobile_proxies)} Mobile | "
            f"{len(self.residential_proxies)} Residential | "
            f"{len(self.socks5_proxies)} SOCKS5 | "
            f"{len(self.datacenter_proxies)} Datacenter"
        )

        if self.residential_proxies:
            logger.info(f"✅ Residential proxies: {len(self.residential_proxies)}")
            for p in self.residential_proxies[:3]:
                endpoint = p.split('@')[-1] if '@' in p else p[:40]
                logger.info(f"   • {endpoint}")

        if not self.mobile_proxies and not self.residential_proxies:
            logger.warning(
                "⚠️ NO Mobile or Residential proxies! "
                "Adsterra ads will NOT show."
            )

    @classmethod
    def _is_residential(cls, proxy_line):
        """Only count as Residential if it matches known residential hosts."""
        lower = proxy_line.lower()
        for host in cls.RESIDENTIAL_HOSTS:
            if host.lower() in lower:
                return True
        return False

    def pick(self):
        if self.mobile_proxies:
            chosen = random.choice(self.mobile_proxies)
            endpoint = chosen.split('@')[-1] if '@' in chosen else chosen[:40]
            logger.info(f"✅ Using MOBILE proxy: {endpoint}")
            return self._format(chosen)

        if self.residential_proxies:
            chosen = random.choice(self.residential_proxies)
            endpoint = chosen.split('@')[-1] if '@' in chosen else chosen[:40]
            logger.info(f"✅ Using RESIDENTIAL proxy: {endpoint}")
            return self._format(chosen)

        if self.datacenter_proxies:
            chosen = random.choice(self.datacenter_proxies)
            logger.warning(f"⚠️ Using DATACENTER proxy (ads may NOT show): {chosen[:40]}")
            return self._format(chosen)

        logger.warning("❌ No proxy available - direct connection")
        return None

    @staticmethod
    def _format(raw):
        raw = raw.strip()
        if not raw:
            return None
        if '://' in raw:
            return raw
        if '@' in raw:
            return f"http://{raw}"
        parts = raw.split(':')
        if len(parts) == 4:
            ip, port, user, pwd = parts
            return f"http://{user}:{pwd}@{ip}:{port}"
        if len(parts) == 2:
            return f"http://{raw}"
        return f"http://{raw}"
