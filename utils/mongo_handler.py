from pymongo import MongoClient
from datetime import datetime
import os
import json


class MongoHandler:
    def __init__(self):
        uri = os.getenv('MONGODB_URI')
        if not uri:
            raise ValueError("MONGODB_URI environment variable not set")
        self.client = MongoClient(uri)
        self.db = self.client['traffic_bot']
        self.visits = self.db['visits']
        self.ad_clicks = self.db['ad_clicks']
        self.form_submits = self.db['form_submits']
        self.proxies = self.db['proxies']
        self.errors = self.db['errors']
        self.sessions = self.db['sessions']
        self._create_indexes()

    def _create_indexes(self):
        self.visits.create_index([('timestamp', -1)])
        self.visits.create_index([('site', 1)])
        self.ad_clicks.create_index([('timestamp', -1)])
        self.form_submits.create_index([('timestamp', -1)])
        self.proxies.create_index([('proxy', 1)], unique=True)
        self.errors.create_index([('timestamp', -1)])
        self.sessions.create_index([('start_time', -1)])

    def log_visit(self, site_url, proxy_used, user_agent, ads_clicked, forms_filled, **kwargs):
        doc = {
            'site_url': site_url,
            'timestamp': datetime.utcnow(),
            'proxy_used': proxy_used,
            'user_agent': user_agent,
            'ads_clicked': ads_clicked,
            'forms_filled': forms_filled,
            'status': 'success',
            **kwargs
        }
        return self.visits.insert_one(doc)

    def log_ad_click(self, url, referer, status, proxy_used, user_agent):
        doc = {
            'url': url,
            'referer': referer,
            'status': status,
            'proxy_used': proxy_used,
            'user_agent': user_agent,
            'timestamp': datetime.utcnow(),
        }
        return self.ad_clicks.insert_one(doc)

    def log_form_submit(self, url, status, proxy_used, user_agent, form_data=None):
        doc = {
            'url': url,
            'status': status,
            'proxy_used': proxy_used,
            'user_agent': user_agent,
            'form_data': form_data or {},
            'timestamp': datetime.utcnow(),
        }
        return self.form_submits.insert_one(doc)

    def log_proxy(self, proxy, status, response_time=None, country=None):
        doc = {
            'proxy': proxy,
            'status': status,
            'response_time': response_time,
            'country': country,
            'last_checked': datetime.utcnow(),
        }
        try:
            self.proxies.update_one(
                {'proxy': proxy},
                {'$set': doc},
                upsert=True
            )
        except Exception:
            pass

    def log_error(self, error_type, message, url=None, proxy_used=None, traceback=None):
        doc = {
            'error_type': error_type,
            'message': message,
            'url': url,
            'proxy_used': proxy_used,
            'traceback': traceback,
            'timestamp': datetime.utcnow(),
        }
        return self.errors.insert_one(doc)

    def log_session(self, site_url, start_time, end_time, total_visits, total_ads_clicked, 
                    total_forms_filled, proxies_used, user_agents_used, status='completed'):
        doc = {
            'site_url': site_url,
            'start_time': start_time,
            'end_time': end_time,
            'duration_seconds': (end_time - start_time).total_seconds(),
            'total_visits': total_visits,
            'total_ads_clicked': total_ads_clicked,
            'total_forms_filled': total_forms_filled,
            'proxies_used': proxies_used,
            'user_agents_used': user_agents_used,
            'status': status,
        }
        return self.sessions.insert_one(doc)

    def get_stats(self, site_url=None, days=7):
        from datetime import timedelta
        since = datetime.utcnow() - timedelta(days=days)
        query = {'timestamp': {'$gte': since}}
        if site_url:
            query['site_url'] = site_url
        
        pipeline = [
            {'$match': query},
            {'$group': {
                '_id': None,
                'total_visits': {'$sum': 1},
                'total_ads_clicked': {'$sum': '$ads_clicked'},
                'total_forms_filled': {'$sum': '$forms_filled'},
                'unique_proxies': {'$addToSet': '$proxy_used'},
                'unique_user_agents': {'$addToSet': '$user_agent'},
            }}
        ]
        result = list(self.visits.aggregate(pipeline))
        return result[0] if result else {}

    def close(self):
        self.client.close()