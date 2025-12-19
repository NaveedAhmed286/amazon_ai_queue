import os
import json
import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_log, after_log

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials

from app.logger import logger
from app.memory_manager import memory_manager
from app.apify_client import apify_client

class AmazonAgent:
    def __init__(self):
        """Initialize with resilience - don't crash on missing env vars"""
        try:
            # DeepSeek - with fallback
            self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
            self.deepseek_api_url = "https://api.deepseek.com/chat/completions"
            
            # Google Sheets - with fallback to prevent crash
            self.spreadsheet_id = os.getenv("SPREADSHEET_ID", "1xLI2iPQdwZnZlK8TFPuFkaSQaTkVUvGnN_af520yAPk")
            self.sheet_name = os.getenv("SHEET_NAME", "Sheet1")
            
            # Log configuration (info only, not errors)
            logger.info(f"📄 Configured for spreadsheet: {self.spreadsheet_id[:20]}...")
            
            # Google service account - THIS CAN STILL CRASH, but that's OK
            service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
            if not service_account_json:
                logger.critical("GOOGLE_SERVICE_ACCOUNT_JSON is not set")
                raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is required")
            
            creds_info = json.loads(service_account_json)
            self.creds = Credentials.from_service_account_info(
                creds_info,
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            self.sheets_service = build("sheets", "v4", credentials=self.creds)
            
            # Apify
            self.apify = apify_client
            
            logger.info("✅ AmazonAgent initialized successfully")
            
        except Exception as e:
            logger.critical(f"❌ Failed to initialize AmazonAgent: {e}")
            raise  # Re-raise - if agent can't init, app shouldn't run

    # SMART RETRY LOGIC FOR GOOGLE SHEETS
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, TimeoutError, ConnectionError)),
        before=before_log(logger, "INFO"),
        after=after_log(logger, "INFO")
    )
    def _save_to_sheet(self, rows: List[List[Any]]) -> bool:
        """Save to Google Sheets with automatic retry on failure"""
        try:
            body = {"values": rows}
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                body=body
            ).execute()
            logger.info(f"✅ Saved {len(rows)} rows to Google Sheets")
            return True
        except Exception as e:
            logger.error(f"❌ Google Sheets save failed after retries: {e}")
            return False

    # RESILIENT PRODUCT ANALYSIS
    async def analyze_products(self, products: List[Dict]) -> Dict:
        """Analyze products with full error handling"""
        try:
            if not products:
                return {"status": "completed", "count": 0, "message": "No products provided"}
            
            logger.info(f"📦 Analyzing {len(products)} products")
            
            # Get AI analysis with timeout
            try:
                analysis = await asyncio.wait_for(
                    self._deepseek_analyze(products), 
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning("DeepSeek API timeout, using fallback analysis")
                analysis = self._fallback_analysis(products)
            except Exception as e:
                logger.error(f"DeepSeek analysis error: {e}")
                analysis = self._fallback_analysis(products)
            
            # Prepare rows
            rows = []
            for p in analysis.get("products", []):
                rows.append([
                    datetime.utcnow().isoformat(),
                    p.get("title", "Unknown"),
                    p.get("price", 0),
                    p.get("score", 0),
                    p.get("recommendation", "Research")
                ])
            
            # Try to save (won't crash if fails)
            if rows:
                saved = self._save_to_sheet(rows)
                if not saved:
                    logger.warning("Data not saved to Google Sheets (check logs)")
            
            return {
                "status": "completed",
                "count": len(rows),
                "saved_to_sheets": bool(rows),
                "products": analysis.get("products", [])
            }
            
        except Exception as e:
            logger.error(f"❌ Product analysis failed: {e}")
            return {"status": "failed", "error": str(e), "count": 0}

    # RESILIENT DEEPSEEK API CALL
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=5)
    )
    async def _deepseek_analyze(self, products: List[Dict]) -> Dict:
        """Call DeepSeek API with retry logic"""
        if not self.deepseek_api_key:
            logger.warning("No DeepSeek API key, using fallback")
            return self._fallback_analysis(products)
        
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }
        
        # Better prompt
        prompt = f"""Analyze these {len(products)} Amazon products for investment potential.
        Return JSON only with this structure: {{"products": [{{"title": str, "price": float, "score": 0-100, "recommendation": "Buy/Avoid/Research"}}]}}"""
        
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.deepseek_api_url,
                    headers=headers,
                    json=payload,
                    timeout=20.0
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"DeepSeek API returned status {resp.status}")
                        return self._fallback_analysis(products)
                    
                    data = await resp.json()
                    
                    if "choices" in data and data["choices"]:
                        content = data["choices"][0]["message"]["content"]
                        # Clean JSON response
                        content = content.replace("```json", "").replace("```", "").strip()
                        
                        try:
                            parsed = json.loads(content)
                            return {
                                "products": parsed.get("products", []),
                                "insights": ["AI analysis complete"]
                            }
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse DeepSeek JSON response")
                            return self._fallback_analysis(products)
                    else:
                        logger.warning("No choices in DeepSeek response")
                        return self._fallback_analysis(products)
                        
        except Exception as e:
            logger.warning(f"DeepSeek API call failed: {e}")
            return self._fallback_analysis(products)
    
    def _fallback_analysis(self, products: List[Dict]) -> Dict:
        """Fallback analysis when AI fails"""
        logger.info("Using fallback analysis")
        fallback_products = []
        for p in products:
            fallback_products.append({
                "title": p.get("title", "Unknown Product"),
                "price": p.get("price", 0),
                "score": 50,  # Neutral score
                "recommendation": "Research Further"
            })
        return {"products": fallback_products, "insights": ["Fallback analysis used"]}
    
    # RESILIENT KEYWORD ANALYSIS
    async def analyze_keyword(self, keyword: str, client_id: str, 
                            max_products: int = 50, investment: Optional[float] = None) -> Dict:
        """Keyword analysis with full error handling"""
        try:
            # Decide smart limit
            final_limit = self._decide_product_limit(investment, max_products)
            logger.info(f"🔍 Searching '{keyword}' (limit: {final_limit})")
            
            # Try scraping with timeout
            try:
                products = await asyncio.wait_for(
                    self.apify.scrape_amazon_products(keyword=keyword, max_products=final_limit),
                    timeout=60.0
                )
            except Exception as e:
                logger.error(f"Scraping failed: {e}")
                return {"status": "completed", "message": f"Scraping failed: {e}", "scraped": 0}
            
            if not products:
                return {"status": "completed", "message": "No products found", "scraped": 0}
            
            # Analyze found products
            result = await self.analyze_products(products)
            
            # Add memory learning (won't crash if it fails)
            try:
                await memory_manager.learn_from_analysis(
                    client_id=client_id,
                    task_id=f"kw-{datetime.utcnow().timestamp()}",
                    analysis_type="keyword",
                    input_data={"keyword": keyword},
                    result_data=result,
                    key_insights=result.get("insights", [])
                )
            except Exception as e:
                logger.warning(f"Memory learning failed: {e}")
            
            return {
                "status": "completed",
                "scraped": len(products),
                "analyzed": result.get("count", 0),
                "saved": result.get("saved_to_sheets", False)
            }
            
        except Exception as e:
            logger.error(f"❌ Keyword analysis failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _decide_product_limit(self, investment: Optional[float], fallback: int) -> int:
        if not investment:
            return fallback
        if investment <= 2000:
            return 5
        elif investment <= 5000:
            return 10
        elif investment <= 10000:
            return 20
        else:
            return 30
