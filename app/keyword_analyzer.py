import os
import json
from datetime import datetime
from typing import Dict, List
import requests
from app.logger import logger

class KeywordAnalyzer:
    def __init__(self):
        self.apify_api_key = os.getenv("APIFY_API_KEY")
    
    async def analyze(self, keyword: str, max_products: int = 50) -> Dict:
        """Analyze keyword for profitability"""
        logger.info(f"Analyzing keyword: {keyword}")
        
        try:
            # Search for products with this keyword
            products = await self._search_amazon(keyword, max_products)
            
            if not products:
                return {
                    "keyword": keyword,
                    "error": "No products found",
                    "recommendation": "Try different keyword"
                }
            
            # Analyze the market
            analysis = await self._analyze_market(products, keyword)
            
            return {
                "keyword": keyword,
                "products_found": len(products),
                "market_analysis": analysis,
                "opportunity_score": self._calculate_opportunity_score(analysis),
                "recommendations": self._generate_keyword_recommendations(analysis),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Keyword analysis error: {e}")
            return {
                "keyword": keyword,
                "error": str(e),
                "status": "failed"
            }
    
    async def _search_amazon(self, keyword: str, max_products: int) -> List[Dict]:
        """Search Amazon for products"""
        # Use Apify or Amazon API
        # For now, return mock data
        logger.info(f"Mock search for: {keyword}")
        
        return [
            {
                "title": f"Premium {keyword}",
                "price": 49.99,
                "rating": 4.5,
                "reviews": 128,
                "bsr": 1500,
                "url": f"https://amazon.com/dp/MOCK001"
            },
            {
                "title": f"Basic {keyword}",
                "price": 19.99,
                "rating": 4.0,
                "reviews": 89,
                "bsr": 4500,
                "url": f"https://amazon.com/dp/MOCK002"
            }
        ]
    
    async def _analyze_market(self, products: List[Dict], keyword: str) -> Dict:
        """Analyze market for keyword"""
        prices = [p.get("price", 0) for p in products if p.get("price")]
        ratings = [p.get("rating", 0) for p in products if p.get("rating")]
        reviews = [p.get("reviews", 0) for p in products if p.get("reviews")]
        
        if not prices:
            return {"error": "No price data"}
        
        # Calculate statistics
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        
        # Find price gaps
        price_gaps = self._find_price_gaps(prices)
        
        # Assess competition
        competition_level = self._assess_competition(len(products), avg_price)
        
        return {
            "average_price": round(avg_price, 2),
            "price_range": f"${min_price:.2f} - ${max_price:.2f}",
            "average_rating": sum(ratings) / len(ratings) if ratings else 0,
            "total_reviews": sum(reviews) if reviews else 0,
            "product_count": len(products),
            "competition_level": competition_level,
            "price_gaps": price_gaps,
            "market_saturation": self._calculate_saturation(len(products))
        }
    
    def _find_price_gaps(self, prices: List[float]) -> List[Dict]:
        """Find gaps in price distribution"""
        if len(prices) < 3:
            return []
        
        sorted_prices = sorted(prices)
        gaps = []
        
        for i in range(len(sorted_prices) - 1):
            current = sorted_prices[i]
            next_price = sorted_prices[i + 1]
            gap = next_price - current
            
            # If gap is significant (>20% of lower price)
            if gap > current * 0.2:
                gaps.append({
                    "low": round(current, 2),
                    "high": round(next_price, 2),
                    "gap_size": round(gap, 2),
                    "opportunity_price": round(current + gap/2, 2)
                })
        
        return gaps
    
    def _assess_competition(self, product_count: int, avg_price: float) -> str:
        """Assess competition level"""
        if product_count < 10:
            return "Low"
        elif product_count < 30:
            return "Medium"
        elif product_count < 100:
            return "High"
        else:
            return "Very High"
    
    def _calculate_saturation(self, product_count: int) -> str:
        """Calculate market saturation"""
        if product_count < 20:
            return "Underserved"
        elif product_count < 50:
            return "Moderate"
        else:
            return "Saturated"
    
    def _calculate_opportunity_score(self, analysis: Dict) -> int:
        """Calculate opportunity score (1-100)"""
        score = 50
        
        # Adjust based on competition
        competition = analysis.get("competition_level", "Medium")
        if competition == "Low":
            score += 30
        elif competition == "Medium":
            score += 10
        elif competition == "High":
            score -= 10
        else:
            score -= 30
        
        # Adjust based on price gaps
        price_gaps = analysis.get("price_gaps", [])
        if price_gaps:
            score += len(price_gaps) * 5
        
        # Adjust based on saturation
        saturation = analysis.get("market_saturation", "Moderate")
        if saturation == "Underserved":
            score += 20
        elif saturation == "Saturated":
            score -= 20
        
        return min(max(score, 1), 100)
    
    def _generate_keyword_recommendations(self, analysis: Dict) -> List[str]:
        """Generate keyword recommendations"""
        recommendations = []
        score = analysis.get("opportunity_score", 50)
        competition = analysis.get("competition_level", "Medium")
        
        if score >= 70:
            recommendations.append("Excellent opportunity - Low competition, good margins")
        elif score >= 50:
            recommendations.append("Good opportunity - Moderate competition")
        else:
            recommendations.append("Challenging market - High competition")
        
        price_gaps = analysis.get("price_gaps", [])
        if price_gaps:
            best_gap = max(price_gaps, key=lambda x: x["gap_size"])
            recommendations.append(f"Price gap found: ${best_gap['low']}-${best_gap['high']}. Target: ${best_gap['opportunity_price']}")
        
        avg_price = analysis.get("average_price", 0)
        if avg_price > 50:
            recommendations.append("Premium market - Higher margins possible")
        elif avg_price < 20:
            recommendations.append("Budget market - High volume needed")
        
        return recommendations