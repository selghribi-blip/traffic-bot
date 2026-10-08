from utils.mongo_handler import MongoHandler
from itemadapter import ItemAdapter


class MongoPipeline:
    def __init__(self):
        self.mongo_handler = None
        self.session_start = None
        self.stats = {
            'visits': 0,
            'ads_clicked': 0,
            'forms_filled': 0,
            'proxies_used': set(),
            'user_agents_used': set(),
        }

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        crawler.signals.connect(pipeline.spider_opened, signal='spider_opened')
        crawler.signals.connect(pipeline.spider_closed, signal='spider_closed')
        return pipeline

    def spider_opened(self, spider):
        try:
            self.mongo_handler = MongoHandler()
            self.session_start = spider.crawler.stats.get_value('start_time')
            spider.logger.info("MongoDB pipeline opened")
        except Exception as e:
            spider.logger.error(f"Failed to connect to MongoDB: {e}")
            self.mongo_handler = None

    def spider_closed(self, spider, reason):
        if self.mongo_handler and self.session_start:
            from datetime import datetime
            try:
                self.mongo_handler.log_session(
                    site_url=getattr(spider, 'target_url', 'unknown'),
                    start_time=self.session_start,
                    end_time=datetime.utcnow(),
                    total_visits=self.stats['visits'],
                    total_ads_clicked=self.stats['ads_clicked'],
                    total_forms_filled=self.stats['forms_filled'],
                    proxies_used=list(self.stats['proxies_used']),
                    user_agents_used=list(self.stats['user_agents_used']),
                    status=reason
                )
                spider.logger.info(f"Session logged to MongoDB: {self.stats}")
            except Exception as e:
                spider.logger.error(f"Failed to log session: {e}")
            finally:
                self.mongo_handler.close()

    def process_item(self, item, spider):
        if not self.mongo_handler:
            return item
        
        adapter = ItemAdapter(item)
        item_type = adapter.get('type')
        
        try:
            if item_type == 'visit':
                self.stats['visits'] += 1
                self.stats['ads_clicked'] += adapter.get('ads_clicked', 0)
                self.stats['forms_filled'] += adapter.get('forms_filled', 0)
                if adapter.get('proxy_used'):
                    self.stats['proxies_used'].add(adapter.get('proxy_used'))
                if adapter.get('user_agent'):
                    self.stats['user_agents_used'].add(adapter.get('user_agent'))
                
                self.mongo_handler.log_visit(
                    site_url=adapter.get('site'),
                    proxy_used=adapter.get('proxy_used', 'direct'),
                    user_agent=adapter.get('user_agent', ''),
                    ads_clicked=adapter.get('ads_clicked', 0),
                    forms_filled=adapter.get('forms_filled', 0),
                    url=adapter.get('url'),
                    status=adapter.get('status'),
                    visited_pages=adapter.get('visited_pages', 1),
                    total_ads_clicked=adapter.get('total_ads_clicked', 0),
                    total_forms_filled=adapter.get('total_forms_filled', 0),
                )
            
            elif item_type == 'ad_click':
                self.mongo_handler.log_ad_click(
                    url=adapter.get('url'),
                    referer=adapter.get('referer', ''),
                    status=adapter.get('status'),
                    proxy_used=adapter.get('proxy_used', 'direct'),
                    user_agent=adapter.get('user_agent', ''),
                )
            
            elif item_type == 'form_submit':
                self.mongo_handler.log_form_submit(
                    url=adapter.get('url'),
                    status=adapter.get('status'),
                    proxy_used=adapter.get('proxy_used', 'direct'),
                    user_agent=adapter.get('user_agent', ''),
                    form_data={},
                )
            
            elif item_type == 'browserstack_visit':
                self.stats['visits'] += 1
                self.stats['ads_clicked'] += adapter.get('ads_clicked', 0)
                self.stats['forms_filled'] += adapter.get('forms_filled', 0)
                
                self.mongo_handler.log_visit(
                    site_url=adapter.get('url'),
                    proxy_used='browserstack',
                    user_agent='browserstack',
                    ads_clicked=adapter.get('ads_clicked', 0),
                    forms_filled=adapter.get('forms_filled', 0),
                    url=adapter.get('url'),
                    status=adapter.get('status'),
                    browser=adapter.get('browser'),
                )
        
        except Exception as e:
            spider.logger.error(f"MongoDB pipeline error: {e}")
            if self.mongo_handler:
                self.mongo_handler.log_error(
                    error_type='pipeline_error',
                    message=str(e),
                    url=adapter.get('url'),
                )
        
        return item