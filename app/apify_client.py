import os
from app.logger import logger

class ApifyClient:
    def __init__(self):
        self.api_token = os.getenv('APIFY_TOKEN')
        logger.info('Apify client ready')

apify_client = ApifyClient()
