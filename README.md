# Traffic Bot - Advanced Web Traffic Generator

A comprehensive, production-ready traffic bot that crawls websites, clicks ads, fills forms, rotates proxies, and changes browser fingerprints. Built with Scrapy, Zyte API, BrowserStack, and MongoDB.

## Features

- **Web Crawling**: Intelligent crawling with JavaScript rendering via Zyte API
- **Ad Clicking**: Automatically detects and clicks on ads (AdSense, Adsterra, Monetag, PropellerAds, MGID, Taboola, Outbrain, etc.)
- **Form Filling**: Finds and fills contact forms, newsletter subscriptions, and other forms with realistic data
- **Proxy Rotation**: Automatically fetches and rotates free proxies from multiple GitHub sources
- **Browser Fingerprint Rotation**: Rotates user agents, headers, viewport, screen resolution, timezone, WebGL, canvas, and audio fingerprints
- **Real Browser Automation**: Uses BrowserStack for real browser testing across multiple OS/browser combinations
- **Local Browser Fallback**: Uses undetected-chromedriver for local headless browser automation
- **MongoDB Logging**: Comprehensive logging of visits, ad clicks, form submissions, proxies, errors, and sessions
- **GitHub Actions Deployment**: Fully automated deployment with scheduled runs (every 4 hours)
- **Free Tier Friendly**: Uses GitHub Actions free tier, Zyte free tier, MongoDB Atlas free tier, BrowserStack free trial

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   GitHub Actions │────▶│   Scrapy Spider  │────▶│   Zyte API      │
│   (Scheduler)    │     │   (Crawler)      │     │   (JS Render)   │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
            ┌───────────┐ ┌───────────┐ ┌───────────┐
            │ Proxy     │ │ Fingerprint│ │ MongoDB   │
            │ Rotator   │ │ Rotator   │ │ Logger    │
            └───────────┘ └───────────┘ └───────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
            ┌───────────┐             ┌───────────┐
            │BrowserStack│            │  Local    │
            │ (Real Browser)         │  Browser  │
            └───────────┘             └───────────┘
```

## Quick Start

### 1. Prerequisites

- GitHub Account (for GitHub Actions)
- GitHub Student Pack (recommended for more free minutes)
- MongoDB Atlas Account (free tier: 512MB)
- Zyte Account (free tier: $5/month credit)
- BrowserStack Account (free trial: 100 minutes)
- Domain with Blogger + Adsterra/Monetag ads

### 2. Get Your API Keys

#### MongoDB Atlas
1. Go to https://cloud.mongodb.com/
2. Create a free cluster (M0 - 512MB)
3. Create a database user
4. Whitelist all IPs (0.0.0.0/0) for GitHub Actions
5. Get connection string: `mongodb+srv://user:pass@cluster.mongodb.net/db`

#### Zyte (Scrapy Cloud)
1. Go to https://app.zyte.com/
2. Sign up for free account
3. Get API key from dashboard
4. Free tier includes $5/month credit

#### BrowserStack
1. Go to https://www.browserstack.com/
2. Sign up for free trial
3. Get Username and Access Key from Account Settings
4. Free trial: 100 minutes of automated testing

#### GitHub Student Pack (Optional but Recommended)
1. Go to https://education.github.com/pack
2. Apply with your .edu email
3. Get additional GitHub Actions minutes, MongoDB Atlas credits, etc.

### 3. Local Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/traffic-bot.git
cd traffic-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env

# Run locally
scrapy crawl traffic_bot -a target_url="https://www.forjo.tech/"
```

### 4. GitHub Actions Deployment

1. **Push to GitHub**:
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/yourusername/traffic-bot.git
git push -u origin main
```

2. **Add Secrets to GitHub Repository**:
   - Go to Settings > Secrets and variables > Actions
   - Add the following secrets:
     - `ZYTE_API_KEY`: Your Zyte API key
     - `MONGODB_URI`: Your MongoDB connection string
     - `BROWSERSTACK_USERNAME`: Your BrowserStack username
     - `BROWSERSTACK_ACCESS_KEY`: Your BrowserStack access key
     - `TARGET_URL`: Your target URL (e.g., https://www.forjo.tech/)

3. **Enable GitHub Actions**:
   - Go to Actions tab
   - Enable workflows
   - The bot will run automatically every 4 hours

4. **Manual Trigger**:
   - Go to Actions > Traffic Bot Runner > Run workflow
   - Choose run mode: `scrapy`, `browserstack`, `local`, or `both`
   - Optionally override target URL

## Configuration

### Environment Variables (.env)

| Variable | Description | Required |
|----------|-------------|----------|
| `ZYTE_API_KEY` | Zyte API key for JavaScript rendering | Yes |
| `MONGODB_URI` | MongoDB Atlas connection string | Yes |
| `BROWSERSTACK_USERNAME` | BrowserStack username | For BrowserStack mode |
| `BROWSERSTACK_ACCESS_KEY` | BrowserStack access key | For BrowserStack mode |
| `TARGET_URL` | Target website URL | No (default: forjo.tech) |
| `FREE_PROXY_LIST_URL` | Custom proxy list URL | No |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | No |
| `DOWNLOAD_DELAY` | Delay between requests (seconds) | No |
| `CONCURRENT_REQUESTS` | Concurrent requests | No |
| `RUN_MODE` | scrapy, browserstack, local, or both | No |

### Customizing Ad Selectors

Edit `spiders/traffic_spider.py` to add more ad network selectors:

```python
AD_SELECTORS = [
    # Add your ad network selectors here
    'a[href*="your-ad-network.com"]',
    'iframe[src*="your-ad-network.com"]',
    '.your-ad-class',
]
```

### Customizing Form Selectors

```python
FORM_SELECTORS = [
    'form[action*="your-form-endpoint"]',
    '#your-form-id',
    '.your-form-class',
]
```

## Free Proxy Sources

The bot automatically fetches proxies from these GitHub repositories:

- https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/all/data.txt
- https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt
- https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt
- https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt
- https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt

**To get residential proxies for free:**
1. Use the GitHub sources above (datacenter proxies)
2. For residential proxies, consider:
   - **Webshare.io**: 10 free proxies/month
   - **ProxyScrape**: Free residential proxy list
   - **GeoNode**: Free proxy list with residential IPs
   - **FreeProxyList.net**: Regular updates

## Browser Fingerprint Rotation

The bot rotates these fingerprint attributes:

- **User Agent**: 8 different browser/OS combinations
- **Headers**: Accept, Accept-Language, Accept-Encoding, Sec-Fetch-*, Sec-CH-UA-*
- **Viewport**: Random screen resolutions (1920x1080, 1366x768, 1440x900, etc.)
- **Timezone**: Random timezones (America/New_York, Europe/London, etc.)
- **Language**: Random languages (en-US, en-GB, fr-FR, de-DE)
- **Platform**: Win32, MacIntel, Linux x86_64, iPhone, iPad
- **WebGL**: Vendor and renderer strings
- **Canvas**: Random fingerprint noise
- **Audio**: Random audio context fingerprint

## MongoDB Collections

| Collection | Description |
|------------|-------------|
| `visits` | Page visits with proxy, UA, ads clicked, forms filled |
| `ad_clicks` | Individual ad click tracking |
| `form_submits` | Form submission tracking |
| `proxies` | Proxy performance tracking |
| `errors` | Error logging |
| `sessions` | Session summaries |

## Running Modes

### Scrapy Mode (Fast, Lightweight)
```bash
scrapy crawl traffic_bot -a target_url="https://your-site.com"
```
- Uses Zyte API for JavaScript rendering
- Rotates proxies and fingerprints
- Good for high-volume crawling

### BrowserStack Mode (Real Browsers)
```bash
scrapy crawl browserstack_bot -a target_url="https://your-site.com" -a use_browserstack=true
```
- Uses real browsers on real devices
- Supports Chrome, Firefox, Edge, Safari
- Windows 10/11, macOS, iOS, Android
- Best for ad networks that detect headless browsers

### Local Browser Mode (Free, No BrowserStack)
```bash
scrapy crawl browserstack_bot -a target_url="https://your-site.com" -a use_browserstack=false
```
- Uses undetected-chromedriver locally
- Headless Chrome with anti-detection
- Completely free, no external dependencies

## GitHub Actions Workflow

The workflow (`.github/workflows/bot.yml`) includes:

1. **Scheduled Runs**: Every 4 hours (0 */4 * * *)
2. **Manual Trigger**: With configurable parameters
3. **Three Parallel Jobs**:
   - Scrapy Spider (Zyte + Proxies)
   - BrowserStack Spider (Real browsers)
   - Local Browser Spider (Fallback)
4. **Results Aggregation**: Combines results from all jobs
5. **MongoDB Session Logging**: Stores session summaries
6. **Artifact Upload**: JSON results for 7 days
7. **Cleanup**: Removes old workflow runs

## Monitoring & Analytics

### View MongoDB Data
```bash
# Connect to MongoDB
mongosh "mongodb+srv://cluster.mongodb.net/traffic_bot" --username user

# Query visits
db.visits.find().sort({timestamp: -1}).limit(10)

# Get stats
db.visits.aggregate([
  {$match: {timestamp: {$gte: new Date(Date.now() - 7*24*60*60*1000)}}},
  {$group: {_id: null, visits: {$sum: 1}, ads: {$sum: "$ads_clicked"}, forms: {$sum: "$forms_filled"}}}
])
```

### GitHub Actions Logs
- Go to Actions tab
- Click on any run
- View logs for each job
- Download artifacts for detailed results

## Troubleshooting

### Common Issues

**1. Proxy Connection Failed**
- Proxies are free and unreliable
- Bot automatically retries with different proxies
- Increase `ROTATING_PROXY_PAGE_RETRY_TIMES` in settings.py

**2. Zyte API Quota Exceeded**
- Free tier: $5/month
- Reduce `CONCURRENT_REQUESTS` and increase `DOWNLOAD_DELAY`
- Use BrowserStack/local mode more

**3. BrowserStack Minutes Exhausted**
- Free trial: 100 minutes
- Switch to local browser mode
- Optimize test duration

**4. MongoDB Connection Failed**
- Check IP whitelist (add 0.0.0.0/0 for GitHub Actions)
- Verify connection string format
- Check username/password

**5. Ads Not Clicked**
- Ad selectors may need updating
- Check browser console for ad network names
- Add custom selectors to `AD_SELECTORS`

### Debug Mode
```bash
# Run with debug logging
scrapy crawl traffic_bot -a target_url="https://your-site.com" -L DEBUG

# Run single page without crawling
scrapy crawl traffic_bot -a target_url="https://your-site.com" -s CLOSESPIDER_PAGECOUNT=1
```

## Advanced Usage

### Custom Spider
Create a new spider for specific sites:
```python
# spiders/custom_spider.py
from spiders.traffic_spider import TrafficSpider

class CustomSpider(TrafficSpider):
    name = 'custom_bot'
    
    AD_SELECTORS = TrafficSpider.AD_SELECTORS + [
        'a[href*="custom-ad-network.com"]',
    ]
```

### Custom Pipeline
Add data processing in `pipelines.py`:
```python
class CustomPipeline:
    def process_item(self, item, spider):
        # Process item before MongoDB
        return item
```

### Scheduled Runs with Different URLs
Use GitHub Actions matrix strategy:
```yaml
strategy:
  matrix:
    url: [https://site1.com, https://site2.com, https://site3.com]
```

## Cost Optimization (Free Tier)

| Service | Free Tier | Optimization |
|---------|-----------|--------------|
| GitHub Actions | 2000 min/month (public) | Use scheduled runs, not manual |
| MongoDB Atlas | 512MB | Use TTL indexes for old data |
| Zyte | $5/month credit | Use transparent mode, cache responses |
| BrowserStack | 100 min trial | Use local browser for most runs |

## Security Notes

- Never commit `.env` file
- Use GitHub Secrets for all credentials
- Rotate API keys periodically
- Monitor MongoDB access logs
- This is for experimental/educational use only

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Test locally
5. Submit PR

## License

MIT License - Use for educational/experimental purposes only.

## Disclaimer

This tool is for educational and experimental purposes only. Use responsibly and in accordance with:
- Website Terms of Service
- Ad Network Policies
- Applicable Laws
- Robots.txt (though we set ROBOTSTXT_OBEY=False for testing)

The authors are not responsible for any misuse or policy violations.

---

## Support

For issues:
1. Check GitHub Actions logs
2. Check MongoDB error collection
3. Enable DEBUG logging
4. Create GitHub Issue with logs

## Credits

- Scrapy Framework
- Zyte API
- BrowserStack
- MongoDB Atlas
- Free Proxy Lists from GitHub Community