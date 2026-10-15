# pipelines.py
import os
import time
import logging
import hashlib
from datetime import datetime, timezone
from collections import defaultdict, Counter

from pymongo import MongoClient, UpdateOne, InsertOne
from pymongo.errors import BulkWriteError
from itemadapter import ItemAdapter

from scrapy import signals
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


def _sanitize_mongo_uri(uri):
    """Strip whitespace, quotes, newlines from URI."""
    if not uri:
        return ''
    uri = str(uri).strip()
    # Remove surrounding quotes
    if (uri.startswith('"') and uri.endswith('"')) or \
       (uri.startswith("'") and uri.endswith("'")):
        uri = uri[1:-1]
    # Remove ALL whitespace/newlines
    uri = ''.join(uri.split())
    return uri


class MongoPipeline:
    BATCH_SIZE = 50
    BATCH_TIMEOUT = 10
    CONNECTION_TIMEOUT_MS = 8000

    TTL_VISITS = 90 * 24 * 3600
    TTL_ADS = 180 * 24 * 3600
    TTL_FORMS = 180 * 24 * 3600
    TTL_ERRORS = 30 * 24 * 3600
    TTL_SESSIONS = 365 * 24 * 3600
    TTL_HOURLY = 30 * 24 * 3600
    TTL_DAILY = 3 * 365 * 24 * 3600

    def __init__(self, mongo_uri, database='traffic_bot'):
        self.mongo_uri = mongo_uri
        self.database = database
        self.client = None
        self.db = None
        self._buffers = defaultdict(list)
        self._last_flush = time.time()
        self._session_id = None
        self._session_stats = {
            'visits': 0, 'ads_clicked': 0, 'forms_filled': 0, 'errors': 0,
            'by_status': Counter(), 'by_mode': Counter(),
            'start_time': None, 'end_time': None,
        }

    @classmethod
    def from_crawler(cls, crawler):
        raw_uri = crawler.settings.get('MONGODB_URI') or os.environ.get('MONGODB_URI', '')
        uri = _sanitize_mongo_uri(raw_uri)

        if not uri or not uri.startswith(('mongodb://', 'mongodb+srv://')):
            logger.warning("MONGODB_URI invalid or empty - pipeline disabled")
            if uri:
                logger.warning(f"   Received length: {len(uri)} | first 30: {uri[:30]}")
            raise NotConfigured("MONGODB_URI invalid")

        logger.info(f"MONGODB_URI OK (length: {len(uri)})")
        db_name = crawler.settings.get('MONGODB_DATABASE', 'traffic_bot')
        p = cls(uri, db_name)
        crawler.signals.connect(p.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(p.spider_closed, signal=signals.spider_closed)
        return p

    def spider_opened(self, spider):
        self._session_id = f"{spider.name}_{int(time.time())}"
        self._session_stats['start_time'] = datetime.now(timezone.utc)
        try:
            self.client = MongoClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=self.CONNECTION_TIMEOUT_MS,
                maxPoolSize=50,
                retryWrites=True,
                w=1,
                connectTimeoutMS=10000,
                socketTimeoutMS=30000,
            )
            self.client.admin.command('ping')
            self.db = self.client[self.database]
            self._ensure_indexes()
            logger.info(f"MongoDB connected: {self.database} | Session: {self._session_id}")
        except Exception as e:
            logger.error(f"MongoDB init failed: {e}")
            raise

    def _ensure_indexes(self):
        try:
            self.db.visits.create_index('timestamp', expireAfterSeconds=self.TTL_VISITS)
            self.db.visits.create_index('session_id')
            self.db.visits.create_index([('url', 1), ('timestamp', -1)])
            self.db.ad_clicks.create_index('timestamp', expireAfterSeconds=self.TTL_ADS)
            self.db.form_submits.create_index('timestamp', expireAfterSeconds=self.TTL_FORMS)
            self.db.errors.create_index('timestamp', expireAfterSeconds=self.TTL_ERRORS)
            self.db.sessions.create_index('session_id', unique=True)
            self.db.sessions.create_index('timestamp', expireAfterSeconds=self.TTL_SESSIONS)
            self.db.stats_hourly.create_index('hour', unique=True)
            self.db.stats_hourly.create_index('timestamp', expireAfterSeconds=self.TTL_HOURLY)
            self.db.stats_daily.create_index('date', unique=True)
            self.db.stats_daily.create_index('timestamp', expireAfterSeconds=self.TTL_DAILY)
            logger.info("Indexes created")
        except Exception as e:
            logger.warning(f"Index warning: {e}")

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        t = adapter.get('type', 'unknown')
        try:
            if t == 'visit':
                self._handle_visit(adapter)
            elif t == 'browserstack_visit':
                self._handle_bs_visit(adapter)
            elif t == 'ad_click':
                self._handle_ad(adapter)
            elif t == 'form_submit':
                self._handle_form(adapter)
            self._maybe_flush()
        except Exception as e:
            logger.error(f"process_item failed: {e}")
        return item

    def _handle_visit(self, adapter):
        url = adapter.get('url', '')
        status = adapter.get('status', 0)
        mode = adapter.get('mode', 'scrapy')
        doc = {
            'session_id': self._session_id,
            'url': url, 'status': status, 'mode': mode,
            'proxy_used': adapter.get('proxy_used'),
            'ads_clicked': adapter.get('ads_clicked', 0),
            'forms_filled': adapter.get('forms_filled', 0),
            'dwell_time': adapter.get('dwell_time', 0),
            'scroll_count': adapter.get('scroll_count', 0),
            'internal_clicks': adapter.get('internal_clicks', 0),
            'captcha': adapter.get('captcha', False),
            'timestamp': datetime.now(timezone.utc),
        }
        self._buffers['visits'].append(doc)
        self._session_stats['visits'] += 1
        self._session_stats['ads_clicked'] += doc['ads_clicked']
        self._session_stats['forms_filled'] += doc['forms_filled']
        self._session_stats['by_status'][str(status)] += 1
        self._session_stats['by_mode'][mode] += 1

    def _handle_bs_visit(self, adapter):
        doc = {
            'session_id': self._session_id,
            'url': adapter.get('url', ''),
            'status': adapter.get('status', 'unknown'),
            'mode': adapter.get('mode', 'browserstack'),
            'error': adapter.get('error'),
            'ads_clicked': adapter.get('ads_clicked', 0),
            'forms_filled': adapter.get('forms_filled', 0),
            'dwell_time': adapter.get('dwell_time', 0),
            'scroll_count': adapter.get('scroll_count', 0),
            'internal_clicks': adapter.get('internal_clicks', 0),
            'captcha': adapter.get('captcha', False),
            'proxy_used': adapter.get('proxy_used'),
            'timestamp': datetime.now(timezone.utc),
        }
        self._buffers['visits'].append(doc)
        self._session_stats['visits'] += 1
        self._session_stats['ads_clicked'] += doc['ads_clicked']
        self._session_stats['forms_filled'] += doc['forms_filled']
        self._session_stats['by_status'][str(doc['status'])] += 1
        self._session_stats['by_mode'][doc['mode']] += 1
        if doc['error']:
            self._buffers['errors'].append({
                'session_id': self._session_id,
                'url': doc['url'],
                'error': str(doc['error'])[:500],
                'mode': doc['mode'],
                'timestamp': datetime.now(timezone.utc),
            })
            self._session_stats['errors'] += 1

    def _handle_ad(self, adapter):
        self._buffers['ad_clicks'].append({
            'session_id': self._session_id,
            'ad_url': adapter.get('url', ''),
            'status': adapter.get('status', 0),
            'parent_url': adapter.get('parent_url', ''),
            'timestamp': datetime.now(timezone.utc),
        })
        self._session_stats['ads_clicked'] += 1

    def _handle_form(self, adapter):
        self._buffers['form_submits'].append({
            'session_id': self._session_id,
            'form_url': adapter.get('url', ''),
            'status': adapter.get('status', 0),
            'parent_url': adapter.get('parent_url', ''),
            'timestamp': datetime.now(timezone.utc),
        })
        self._session_stats['forms_filled'] += 1

    def _maybe_flush(self):
        for name, buf in self._buffers.items():
            if len(buf) >= self.BATCH_SIZE:
                self._flush(name)
                return
        if time.time() - self._last_flush > self.BATCH_TIMEOUT:
            self._flush_all()

    def _flush(self, name):
        buf = self._buffers.get(name, [])
        if not buf:
            return
        try:
            collection = getattr(self.db, name, None)
            if collection is None:
                return
            try:
                collection.insert_many(buf, ordered=False)
            except BulkWriteError as e:
                dup_errors = [d for d in e.details.get('writeErrors', [])
                              if d.get('code') == 11000]
                logger.debug(f"{len(dup_errors)} duplicates in {name}")
            self._buffers[name] = []
            self._last_flush = time.time()
        except Exception as e:
            logger.error(f"Flush '{name}' failed: {e}")

    def _flush_all(self):
        for name in list(self._buffers.keys()):
            self._flush(name)

    def spider_closed(self, spider, reason='finished'):
        self._flush_all()
        self._session_stats['end_time'] = datetime.now(timezone.utc)

        try:
            start = self._session_stats['start_time']
            end = self._session_stats['end_time']
            duration = (end - start).total_seconds() if start else 0

            self.db.sessions.update_one(
                {'session_id': self._session_id},
                {'$set': {
                    'session_id': self._session_id,
                    'reason': reason,
                    'timestamp': end,
                    'duration_seconds': duration,
                    'total_visits': self._session_stats['visits'],
                    'total_ads_clicked': self._session_stats['ads_clicked'],
                    'total_forms_filled': self._session_stats['forms_filled'],
                    'total_errors': self._session_stats['errors'],
                    'by_status': dict(self._session_stats['by_status']),
                    'by_mode': dict(self._session_stats['by_mode']),
                }},
                upsert=True,
            )
            logger.info(f"Session saved: {self._session_id}")
        except Exception as e:
            logger.error(f"Session save failed: {e}")

        if self.client:
            try:
                self.client.close()
            except Exception:
                pass

        logger.info(
            "\n"
            "============================================================\n"
            "PIPELINE REPORT\n"
            "============================================================\n"
            f"   Session:     {self._session_id}\n"
            f"   Visits:      {self._session_stats['visits']}\n"
            f"   Ads:         {self._session_stats['ads_clicked']}\n"
            f"   Forms:       {self._session_stats['forms_filled']}\n"
            f"   Errors:      {self._session_stats['errors']}\n"
            "============================================================"
        )


class StatsAggregationPipeline:
    def __init__(self, mongo_uri, database='traffic_bot'):
        self.mongo_uri = mongo_uri
        self.database = database

    @classmethod
    def from_crawler(cls, crawler):
        raw_uri = crawler.settings.get('MONGODB_URI') or os.environ.get('MONGODB_URI', '')
        uri = _sanitize_mongo_uri(raw_uri)
        if not uri or not uri.startswith(('mongodb://', 'mongodb+srv://')):
            raise NotConfigured("MONGODB_URI invalid")
        p = cls(uri, crawler.settings.get('MONGODB_DATABASE', 'traffic_bot'))
        crawler.signals.connect(p.spider_closed, signal=signals.spider_closed)
        return p

    def spider_closed(self, spider, reason='finished'):
        try:
            client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=8000)
            db = client[self.database]
            self._aggregate(db)
            client.close()
        except Exception as e:
            logger.error(f"Aggregation failed: {e}")

    def _aggregate(self, db):
        now = datetime.now(timezone.utc)
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Hourly
        result = list(db.visits.aggregate([
            {'$match': {'timestamp': {'$gte': hour_start}}},
            {'$group': {
                '_id': None,
                'visits': {'$sum': 1},
                'ads': {'$sum': '$ads_clicked'},
                'forms': {'$sum': '$forms_filled'},
                'avg_dwell': {'$avg': '$dwell_time'},
            }},
        ]))
        if result:
            r = result[0]
            db.stats_hourly.update_one(
                {'hour': hour_start},
                {'$set': {
                    'hour': hour_start,
                    'timestamp': now,
                    'total_visits': r.get('visits', 0),
                    'total_ads': r.get('ads', 0),
                    'total_forms': r.get('forms', 0),
                    'avg_dwell': round(r.get('avg_dwell') or 0, 1),
                }},
                upsert=True,
            )

        # Daily
        result = list(db.visits.aggregate([
            {'$match': {'timestamp': {'$gte': day_start}}},
            {'$group': {
                '_id': None,
                'visits': {'$sum': 1},
                'ads': {'$sum': '$ads_clicked'},
                'forms': {'$sum': '$forms_filled'},
                'avg_dwell': {'$avg': '$dwell_time'},
            }},
        ]))
        if result:
            r = result[0]
            db.stats_daily.update_one(
                {'date': day_start},
                {'$set': {
                    'date': day_start,
                    'timestamp': now,
                    'total_visits': r.get('visits', 0),
                    'total_ads': r.get('ads', 0),
                    'total_forms': r.get('forms', 0),
                    'avg_dwell': round(r.get('avg_dwell') or 0, 1),
                }},
                upsert=True,
            )

        logger.info("Stats aggregation complete")
