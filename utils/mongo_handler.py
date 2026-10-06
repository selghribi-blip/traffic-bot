from pymongo import MongoClient
from datetime import datetime
import os

class MongoHandler:
    def __init__(self):
        uri = os.getenv('MONGODB_URI')
        if not uri:
            raise ValueError("MONGODB_URI environment variable not set")
        self.client = MongoClient(uri)
        self.db = self.client['traffic_bot']
        self.collection = self.db['visits']

    def log_visit(self, site_url, proxy_used, user_agent, ads_clicked, forms_filled):
        self.collection.insert_one({
            'site_url': site_url,
            'timestamp': datetime.utcnow(),
            'proxy_used': proxy_used,
            'user_agent': user_agent,
            'ads_clicked': ads_clicked,
            'forms_filled': forms_filled,
            'status': 'success'
        })