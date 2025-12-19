# app/apify_client.py
import os
import asyncio
import re
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_log, after_log

from app.logger import logger

# Import memory_manager if it exists
try:
    from app.memory_manager import memory_manager
    HAS_MEMORY_MANAGER = True
except ImportError:
    HAS_MEMORY_MANAGER = False
    logger.warning("memory_manager not found - memory features disabled")

class ApifyClient:
    def __init__(self):
        """Initialize with retry-ready configuration"""
        self.api_token = os.getenv("APIFY_TOKEN")
        self.base_url = "https://api.apify.com/v2"
        
        if self.api_token:
            self.api_token = self.api_token.strip()
            logger.info("✅ Apify client initialized for scraper-engine/amazon-search-scraper")
        else:
            logger.critical("❌ APIFY_TOKEN not configured - Amazon scraping will fail")
            self.api_token = None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError, ConnectionError)),
        before=before_log(logger, "INFO"),
        after=after_log(logger, "INFO")
    )
    async def scrape_amazon_products(
        self, 
        keyword: str, 
        max_products: int = 50,
        client_id: Optional[str] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None
    ) -> Dict:
        """
        Scrape Amazon products using scraper-engine/amazon-search-scraper
        Returns: {
            "success": bool,
            "products": List[product_dict],
            "error": str (if failed),
            "client_id": str,
            "keyword": str
        }
        """
        if not self.api_token:
            return {
                "success": False,
                "error": "APIFY_TOKEN not configured",
                "products": [],
                "client_id": client_id,
                "keyword": keyword
            }
        
        logger.info(f"🔍 Starting Amazon scrape for keyword: '{keyword}'")
        logger.info(f"   Max products: {max_products}, Client: {client_id}")
        
        # Check cache first if available
        if HAS_MEMORY_MANAGER and client_id:
            cache_key = f"amazon_scrape:{keyword}:{max_products}"
            cached = await memory_manager.get_short_term_cache(cache_key)
            if cached:
                logger.info(f"📦 Returning cached results for '{keyword}'")
                cached["cached"] = True
                return cached
        
        # Prepare input for NEW actor: scraper-engine/amazon-search-scraper
        run_input = {
            "urls": [keyword],  # NEW: Uses "urls" array with keywords
            "maxResults": min(max_products, 100),
            "resultsPerPage": 20,
            "delayMs": 1500,
            "sortBy": "relevanceblender",
            "proxyConfiguration": {
                "useApifyProxy": True
            }
        }
        
        try:
            logger.info(f"🚀 Starting scraper-engine/amazon-search-scraper actor")
            
            # Start actor run with timeout
            run_response = await asyncio.wait_for(
                self._start_actor_run(run_input),
                timeout=120.0
            )
            
            if not run_response.get("success"):
                error_msg = run_response.get("error", "Unknown actor error")
                logger.error(f"❌ Actor start failed: {error_msg}")
                return {
                    "success": False,
                    "error": f"Actor error: {error_msg}",
                    "keyword": keyword,
                    "client_id": client_id,
                    "products": []
                }
            
            run_id = run_response["data"]["id"]
            logger.info(f"✅ Actor run started: {run_id}")
            
            # Wait for completion with timeout
            is_completed = await asyncio.wait_for(
                self._wait_for_completion(run_id, max_wait=300),
                timeout=350.0
            )
            
            if not is_completed:
                logger.warning(f"⚠️ Run {run_id} may have timed out or failed")
                # Still try to get partial results
            
            # Get dataset items with retry
            dataset_items = await self._get_dataset_items_with_retry(run_id)
            
            # Process and filter products
            processed_products = self._process_new_actor_products(dataset_items)
            
            # Apply price filtering if provided
            if price_min is not None and price_max is not None:
                original_count = len(processed_products)
                processed_products = [
                    p for p in processed_products 
                    if price_min <= p.get("price", 0) <= price_max
                ]
                logger.info(f"💰 Price filter {price_min}-{price_max}: {original_count} → {len(processed_products)} products")
            
            # Calculate statistics
            stats = self._calculate_scrape_stats(processed_products)
            
            logger.info(f"✅ Scraping complete for '{keyword}': Found {len(processed_products)} products")
            
            result = {
                "success": True,
                "keyword": keyword,
                "total_products": len(processed_products),
                "products": processed_products[:max_products],  # Limit to requested max
                "statistics": stats,
                "run_id": run_id,
                "scraper_used": "scraper-engine/amazon-search-scraper",
                "timestamp": datetime.now().isoformat(),
                "client_id": client_id,
                "price_filter_applied": price_min is not None and price_max is not None,
                "price_min": price_min,
                "price_max": price_max
            }
            
            # Cache results
            if HAS_MEMORY_MANAGER and client_id:
                cache_key = f"amazon_scrape:{keyword}:{max_products}"
                await memory_manager.set_short_term_cache(cache_key, result, ttl=86400)
                await self._store_in_client_memory(client_id, keyword, result)
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"⏰ Scraping timeout for keyword: '{keyword}'")
            return {
                "success": False,
                "error": "Scraping timeout (300+ seconds) - Amazon may be blocking",
                "keyword": keyword,
                "client_id": client_id,
                "products": []
            }
        except Exception as e:
            logger.error(f"❌ Apify scraping failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "keyword": keyword,
                "client_id": client_id,
                "products": []
            }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=5)
    )
    async def _start_actor_run(self, run_input: Dict) -> Dict:
        """Start the scraper-engine/amazon-search-scraper actor run"""
        if not self.api_token:
            return {"success": False, "error": "No API token"}
        
        url = f"{self.base_url}/acts/scraper-engine~amazon-search-scraper/runs"
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=90)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=run_input) as response:
                    if response.status == 201:
                        data = await response.json()
                        return {"success": True, "data": data}
                    elif response.status == 402:
                        logger.error("💳 Insufficient Apify credits")
                        return {"success": False, "error": "Insufficient Apify credits"}
                    elif response.status == 400:
                        error_text = await response.text()
                        logger.error(f"❌ Bad request to actor: {error_text}")
                        # Try to parse error for better message
                        try:
                            error_data = json.loads(error_text)
                            error_msg = error_data.get("error", {}).get("message", error_text)
                        except:
                            error_msg = error_text
                        return {"success": False, "error": f"Actor rejected input: {error_msg}"}
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to start actor: {response.status} - {error_text}")
                        return {"success": False, "error": f"HTTP {response.status}"}
        except aiohttp.ClientError as e:
            logger.error(f"🌐 Network error starting actor: {e}")
            raise  # This will trigger retry
        except Exception as e:
            logger.error(f"⚠️ Actor start error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _wait_for_completion(self, run_id: str, max_wait: int = 300) -> bool:
        """Wait for actor run to complete with polling"""
        if not self.api_token:
            return False
        
        check_url = f"{self.base_url}/actor-runs/{run_id}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"⏳ Waiting for run {run_id} to complete (max {max_wait}s)...")
        
        for attempt in range(max_wait // 15):  # Check every 15 seconds
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(check_url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            status = data.get("data", {}).get("status")
                            
                            if status == "SUCCEEDED":
                                logger.info(f"✅ Run {run_id} completed successfully")
                                return True
                            elif status in ["FAILED", "TIMED-OUT", "ABORTED"]:
                                logger.error(f"❌ Run {run_id} failed with status: {status}")
                                return False
                            elif status == "RUNNING":
                                if attempt % 4 == 0:  # Log every minute
                                    logger.info(f"🔄 Run {run_id} still running... ({attempt * 15}s)")
                
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.warning(f"⚠️ Status check error (attempt {attempt + 1}): {e}")
                await asyncio.sleep(15)
        
        logger.warning(f"⚠️ Run {run_id} not completed after {max_wait} seconds")
        return False
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=5)
    )
    async def _get_dataset_items_with_retry(self, run_id: str) -> List[Dict]:
        """Get dataset items with retry logic"""
        if not self.api_token:
            return []
        
        # First get run info to find dataset
        run_url = f"{self.base_url}/actor-runs/{run_id}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=45)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(run_url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"❌ Failed to get run info: {response.status}")
                        return []
                    
                    run_data = await response.json()
                    dataset_id = run_data.get("data", {}).get("defaultDatasetId")
                    
                    if not dataset_id:
                        logger.warning(f"⚠️ No dataset ID for run {run_id}")
                        return []
                    
                    # Now get dataset items
                    dataset_url = f"{self.base_url}/datasets/{dataset_id}/items"
                    async with session.get(dataset_url, headers=headers) as dataset_response:
                        if dataset_response.status == 200:
                            items = await dataset_response.json()
                            logger.info(f"📥 Retrieved {len(items)} items from dataset")
                            return items
                        else:
                            logger.error(f"❌ Failed to get dataset: {dataset_response.status}")
                            return []
            
        except aiohttp.ClientError as e:
            logger.error(f"🌐 Network error getting dataset: {e}")
            raise  # Trigger retry
        except Exception as e:
            logger.error(f"⚠️ Error getting dataset: {e}")
            return []
    
    def _process_new_actor_products(self, raw_products: List[Dict]) -> List[Dict]:
        """Process products from NEW actor format"""
        processed = []
        
        for item in raw_products:
            try:
                # Extract price from new format: "price": {"value": 25.19, "currency": "$"}
                price = 0.0
                price_data = item.get("price")
                if price_data and isinstance(price_data, dict):
                    price_value = price_data.get("value")
                    if price_value is not None:
                        try:
                            price = float(price_value)
                        except (ValueError, TypeError):
                            price = 0.0
                
                # Extract rating
                rating = item.get("stars")
                if rating is not None:
                    try:
                        rating = float(rating)
                    except (ValueError, TypeError):
                        rating = None
                
                # Extract review count
                review_count = item.get("reviewsCount", 0)
                if review_count is not None:
                    try:
                        review_count = int(review_count)
                    except (ValueError, TypeError):
                        review_count = 0
                
                # Only include products with title and valid price
                if price > 0 and item.get("title"):
                    product = {
                        "title": item.get("title", "").strip(),
                        "price": round(price, 2),
                        "rating": rating,
                        "review_count": review_count,
                        "asin": item.get("asin", ""),
                        "url": item.get("url", ""),
                        "image_url": item.get("thumbnailImage", ""),
                        "seller": item.get("seller", ""),  # Note: new actor doesn't provide seller
                        "description": item.get("description", "")[:500] if item.get("description") else "",
                        "brand": item.get("brand", ""),
                        "category": item.get("breadCrumbs", ""),  # Using breadCrumbs as category
                        "scraped_at": datetime.now().isoformat(),
                        "original_price": None,  # New actor doesn't provide original price
                        "currency": item.get("price", {}).get("currency", "$") if item.get("price") else "$"
                    }
                    processed.append(product)
            except Exception as e:
                logger.debug(f"⚠️ Skipping product due to error: {e}")
                continue
        
        logger.info(f"🔄 Processed {len(processed)} valid products from {len(raw_products)} raw items")
        return processed
    
    def _calculate_scrape_stats(self, products: List[Dict]) -> Dict:
        """Calculate statistics from scraped products"""
        if not products:
            return {
                "average_price": 0,
                "min_price": 0,
                "max_price": 0,
                "total_products": 0,
                "products_with_reviews": 0,
                "average_rating": 0
            }
        
        prices = [p["price"] for p in products if p["price"] > 0]
        ratings = [p["rating"] for p in products if p["rating"] is not None]
        products_with_reviews = sum(1 for p in products if p.get("review_count", 0) > 0)
        
        return {
            "average_price": round(sum(prices) / len(prices), 2) if prices else 0,
            "min_price": min(prices) if prices else 0,
            "max_price": max(prices) if prices else 0,
            "total_products": len(products),
            "products_with_reviews": products_with_reviews,
            "products_without_reviews": len(products) - products_with_reviews,
            "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
            "price_range": f"${min(prices) if prices else 0} - ${max(prices) if prices else 0}"
        }
    
    async def _store_in_client_memory(self, client_id: str, keyword: str, result: Dict):
        """Store scraping results in client memory"""
        if not HAS_MEMORY_MANAGER:
            return
            
        try:
            await memory_manager.add_client_search(
                client_id=client_id,
                keyword=keyword,
                results_count=len(result["products"]),
                stats=result["statistics"]
            )
            logger.debug(f"💾 Stored search in memory for client {client_id}")
        except Exception as e:
            logger.error(f"❌ Failed to store in client memory: {e}")
    
    async def quick_test(self, keyword: str = "laptop") -> bool:
        """Quick test to verify Apify connection works"""
        if not self.api_token:
            logger.error("❌ No APIFY_TOKEN configured")
            return False
        
        try:
            test_url = f"{self.base_url}/acts/scraper-engine~amazon-search-scraper"
            headers = {"Authorization": f"Bearer {self.api_token}"}
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(test_url, headers=headers) as response:
                    if response.status == 200:
                        logger.info("✅ Apify connection and actor access OK")
                        return True
                    else:
                        logger.error(f"❌ Cannot access actor: HTTP {response.status}")
                        return False
        except Exception as e:
            logger.error(f"❌ Apify test failed: {e}")
            return False

# Singleton instance with resilience
apify_client = ApifyClient()
logger.info("🔄 Apify client module loaded with scraper-engine/amazon-search-scraper")
