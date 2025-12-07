import os
import json
import requests
from typing import Dict, List, Optional
from app.logger import logger

class ApifyClient:
    def __init__(self):
        self.api_key = os.getenv("APIFY_API_KEY")
        self.base_url = "https://api.apify.com/v2"
        
    async def scrape_amazon_product(self, product_url: str) -> Optional[Dict]:
        """
        Scrape single Amazon product using Apify
        """
        try:
            if not self.api_key:
                logger.warning("Apify API key not set")
                return self._mock_product_data(product_url)
            
            # Trigger Apify Amazon scraper
            response = requests.post(
                f"{self.base_url}/acts/apify~amazon-scraper/run-sync-get-dataset-items",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "startUrls": [{"url": product_url}],
                    "maxItems": 1,
                    "extendOutputFunction": """async ({ data, item, page, request, customData, Apify }) => {
                        return {
                            url: request.url,
                            title: item.title,
                            price: item.price,
                            rating: item.rating,
                            reviews: item.reviews,
                            images: item.images,
                            description: item.description,
                            features: item.features,
                            bsr: item.bsr,
                            category: item.category
                        };
                    }"""
                },
                timeout=60
            )
            
            if response.status_code == 200:
                items = response.json()
                if items:
                    logger.info(f"✅ Scraped Amazon product: {product_url}")
                    return items[0]
            
            logger.warning(f"Apify scraping failed, using mock data for: {product_url}")
            return self._mock_product_data(product_url)
            
        except Exception as e:
            logger.error(f"Error scraping Amazon product: {e}")
            return self._mock_product_data(product_url)
    
    async def search_amazon_keyword(self, keyword: str, max_results: int = 50) -> List[Dict]:
        """
        Search Amazon for products by keyword
        """
        try:
            if not self.api_key:
                logger.warning("Apify API key not set, using mock data")
                return self._mock_keyword_search(keyword, max_results)
            
            response = requests.post(
                f"{self.base_url}/acts/apify~amazon-scraper/run-sync-get-dataset-items",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "searchKeywords": [keyword],
                    "maxItems": max_results,
                    "sort": "relevancerank",
                    "extendOutputFunction": """async ({ data, item, page, request, customData, Apify }) => {
                        return {
                            keyword: '{{keyword}}',
                            url: item.url,
                            title: item.title,
                            price: item.price,
                            rating: item.rating,
                            reviews: item.reviews,
                            bsr: item.bsr,
                            category: item.category,
                            sponsored: item.sponsored || false
                        };
                    }""".replace("{{keyword}}", keyword)
                },
                timeout=120
            )
            
            if response.status_code == 200:
                items = response.json()
                logger.info(f"✅ Found {len(items)} products for keyword: {keyword}")
                return items
            
            logger.warning(f"Apify search failed, using mock data for keyword: {keyword}")
            return self._mock_keyword_search(keyword, max_results)
            
        except Exception as e:
            logger.error(f"Error searching Amazon: {e}")
            return self._mock_keyword_search(keyword, max_results)
    
    async def get_product_reviews(self, product_url: str, max_reviews: int = 100) -> List[Dict]:
        """
        Get product reviews from Amazon
        """
        try:
            if not self.api_key:
                return self._mock_reviews()
            
            response = requests.post(
                f"{self.base_url}/acts/apify~amazon-reviews-scraper/run-sync-get-dataset-items",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "startUrls": [{"url": product_url}],
                    "maxItems": max_reviews,
                    "sort": "recent"
                },
                timeout=90
            )
            
            if response.status_code == 200:
                reviews = response.json()
                logger.info(f"✅ Retrieved {len(reviews)} reviews")
                return reviews
            
            return self._mock_reviews()
            
        except Exception as e:
            logger.error(f"Error getting reviews: {e}")
            return self._mock_reviews()
    
    def _mock_product_data(self, url: str) -> Dict:
        """Mock product data for testing"""
        return {
            "url": url,
            "title": "Premium Product",
            "price": 49.99,
            "rating": 4.5,
            "reviews": 128,
            "bsr": 1500,
            "category": "Electronics",
            "description": "High-quality product with excellent features",
            "features": ["Feature 1", "Feature 2", "Feature 3"],
            "images": ["https://example.com/image.jpg"]
        }
    
    def _mock_keyword_search(self, keyword: str, max_results: int) -> List[Dict]:
        """Mock keyword search results"""
        import random
        results = []
        
        for i in range(min(max_results, 10)):
            price = round(random.uniform(10, 100), 2)
            rating = round(random.uniform(3.5, 5.0), 1)
            reviews = random.randint(10, 500)
            bsr = random.randint(1000, 50000)
            
            results.append({
                "keyword": keyword,
                "url": f"https://amazon.com/dp/MOCK{i}",
                "title": f"{keyword.title()} Product {i+1}",
                "price": price,
                "rating": rating,
                "reviews": reviews,
                "bsr": bsr,
                "category": "Home & Kitchen",
                "sponsored": i < 2
            })
        
        return results
    
    def _mock_reviews(self) -> List[Dict]:
        """Mock reviews for testing"""
        import random
        reviews = []
        
        sentiments = ["positive", "neutral", "negative"]
        comments = [
            "Great product, highly recommend!",
            "Good value for money",
            "Could be better",
            "Exceeded my expectations",
            "Not what I expected",
            "Works perfectly",
            "Had some issues"
        ]
        
        for i in range(10):
            reviews.append({
                "rating": random.randint(1, 5),
                "title": f"Review {i+1}",
                "content": random.choice(comments),
                "sentiment": random.choice(sentiments),
                "helpful": random.randint(0, 50),
                "date": "2024-01-01"
            })
        
        return reviews

# Global instance
apify_client = ApifyClient()