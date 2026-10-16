# utils/proxy_auth.py
# Chrome extension generator for authenticated proxies
import os
import zipfile
import tempfile
import logging

logger = logging.getLogger(__name__)


def create_proxy_auth_extension(proxy_host, proxy_port, proxy_user, proxy_pass, scheme='http'):
    """
    Creates a Chrome extension zip that handles proxy authentication.
    Returns the path to the .zip file.
    """
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Chrome Proxy",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        },
        "minimum_chrome_version":"22.0.0"
    }
    """

    background_js = """
    var config = {
        mode: "fixed_servers",
        rules: {
            singleProxy: {
                scheme: "%s",
                host: "%s",
                port: parseInt(%s)
            },
            bypassList: ["localhost"]
        }
    };

    chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

    function callbackFn(details) {
        return {
            authCredentials: {
                username: "%s",
                password: "%s"
            }
        };
    }

    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {urls: ["<all_urls>"]},
        ['blocking']
    );
    """ % (scheme, proxy_host, proxy_port, proxy_user, proxy_pass)

    # Create temp directory for extension
    ext_dir = tempfile.mkdtemp(prefix='proxy_auth_ext_')
    manifest_path = os.path.join(ext_dir, 'manifest.json')
    background_path = os.path.join(ext_dir, 'background.js')

    with open(manifest_path, 'w') as f:
        f.write(manifest_json)
    with open(background_path, 'w') as f:
        f.write(background_js)

    # Zip it
    zip_path = os.path.join(ext_dir, 'proxy_auth_plugin.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zp:
        zp.write(manifest_path, 'manifest.json')
        zp.write(background_path, 'background.js')

    logger.info(f"Created proxy auth extension: {zip_path}")
    return zip_path


def parse_proxy_url(proxy_url):
    """
    Parses http://user:pass@host:port or socks5://user:pass@host:port
    Returns (scheme, host, port, user, pass) or None
    """
    if not proxy_url:
        return None

    try:
        # Extract scheme
        scheme = 'http'
        if '://' in proxy_url:
            scheme, proxy_url = proxy_url.split('://', 1)

        # Extract credentials
        user = pass_ = None
        if '@' in proxy_url:
            creds, proxy_url = proxy_url.rsplit('@', 1)
            if ':' in creds:
                user, pass_ = creds.split(':', 1)

        # Extract host:port
        if ':' in proxy_url:
            host, port = proxy_url.rsplit(':', 1)
        else:
            return None

        return {
            'scheme': scheme,
            'host': host,
            'port': port,
            'user': user,
            'pass': pass_,
        }
    except Exception as e:
        logger.error(f"Failed to parse proxy: {e}")
        return None
