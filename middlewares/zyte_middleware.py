from scrapy_zyte_api import ZyteAPIDownloadHandler

class ZyteMiddleware:
    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.get('ZYTE_API_KEY'))

    def __init__(self, api_key):
        self.api_key = api_key

    def process_request(self, request, spider):
        if request.meta.get('use_zyte'):
            request.meta['zyte_api'] = {
                'httpResponseBody': True,
                'browserHtml': True,
                'javascript': True,
                'actions': [
                    {'action': 'wait', 'waitTimeout': 3},
                    {'action': 'scroll', 'direction': 'down'},
                ]
            }
        return None