import os
import json
from datetime import datetime
from typing import List, Dict
import openai
from app.logger import logger

class AmazonAgent:
    def __init__(self):
        # Initialize OpenAI (or DeepSeek)
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            self.client = openai.OpenAI(api_key=openai_api_key)
            self.use_ai = True
        else:
            self.use_ai = False
            logger.warning("OPENAI_API_KEY not set. Using mock AI.")
    
    async def analyze_products(self, products: List[Dict]) -> List[Dict]:
        """Analyze Amazon products with AI"""
        logger.info(f"Analyzing {len(products)} products")
        
        results = []
        for product in products:
            try:
                analysis = await self._analyze_product(product)
                results.append(analysis)
            except Exception as e:
                logger.error(f"Error analyzing product: {e}")
                product["error"] = str(e)
                results.append(product)
        
        return results
    
    async def _analyze_product(self, product: Dict) -> Dict:
        """Analyze single product"""
        # Extract product info
        title = product.get("title", "")
        price = product.get("price", 0)
        rating = product.get("rating", 0)
        reviews = product.get("reviews", 0)
        
        # Generate AI insights
        if self.use_ai:
            insights = await self._get_ai_insights(product)
        else:
            insights = self._get_mock_insights(product)
        
        # Calculate profitability score
        score = self._calculate_profitability_score(product, insights)
        
        # Prepare result
        result = {
            **product,
            "analysis": {
                "timestamp": datetime.utcnow().isoformat(),
                "profitability_score": score,
                "insights": insights,
                "recommendations": self._generate_recommendations(insights, score)
            }
        }
        
        return result
    
    async def _get_ai_insights(self, product: Dict) -> Dict:
        """Get AI insights for product"""
        try:
            prompt = self._create_analysis_prompt(product)
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert Amazon product analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            insights_text = response.choices[0].message.content
            return self._parse_insights(insights_text, product)
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return self._get_mock_insights(product)
    
    def _create_analysis_prompt(self, product: Dict) -> str:
        """Create prompt for AI analysis"""
        title = product.get("title", "Unknown product")
        price = product.get("price", 0)
        rating = product.get("rating", 0)
        reviews = product.get("reviews", 0)
        
        return f"""
        Analyze this Amazon product for profitability:
        
        Product: {title}
        Price: ${price}
        Rating: {rating}/5
        Reviews: {reviews}
        
        Provide analysis in this format:
        1. **Price Analysis**: Is the price competitive?
        2. **Market Position**: How does it compare to competitors?
        3. **Profit Margin Estimate**: What's the potential margin?
        4. **Improvement Suggestions**: What could make it better?
        5. **Risk Assessment**: Any potential issues?
        
        Be concise and data-driven.
        """
    
    def _parse_insights(self, insights_text: str, product: Dict) -> Dict:
        """Parse AI response into structured insights"""
        # Simple parsing - can be enhanced
        return {
            "price_analysis": self._extract_section(insights_text, "Price Analysis"),
            "market_position": self._extract_section(insights_text, "Market Position"),
            "estimated_margin": self._extract_margin(insights_text),
            "suggestions": self._extract_section(insights_text, "Improvement Suggestions"),
            "risks": self._extract_section(insights_text, "Risk Assessment")
        }
    
    def _extract_section(self, text: str, section: str) -> str:
        """Extract section from AI response"""
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if section in line:
                # Get next few lines until next section or end
                result = []
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip() and not lines[j].startswith("**"):
                        result.append(lines[j].strip())
                return " ".join(result)
        return "No analysis available"
    
    def _extract_margin(self, text: str) -> str:
        """Extract margin estimate"""
        import re
        match = re.search(r'(\d+-\d+%)', text)
        return match.group(1) if match else "30-40%"
    
    def _get_mock_insights(self, product: Dict) -> Dict:
        """Mock insights for testing"""
        price = product.get("price", 0)
        
        return {
            "price_analysis": "Competitively priced" if price < 50 else "Premium pricing",
            "market_position": "Moderate competition",
            "estimated_margin": "35-45%",
            "suggestions": ["Improve product images", "Add more features"],
            "risks": "Standard market risks"
        }
    
    def _calculate_profitability_score(self, product: Dict, insights: Dict) -> int:
        """Calculate profitability score (1-100)"""
        score = 50
        
        # Adjust based on price
        price = product.get("price", 0)
        if 15 <= price <= 40:
            score += 20
        elif price > 100:
            score -= 10
        
        # Adjust based on rating
        rating = product.get("rating", 0)
        if rating >= 4.5:
            score += 15
        elif rating >= 4.0:
            score += 5
        
        # Adjust based on reviews
        reviews = product.get("reviews", 0)
        if reviews > 100:
            score += 10
        
        return min(max(score, 1), 100)
    
    def _generate_recommendations(self, insights: Dict, score: int) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if score >= 70:
            recommendations.append("High potential product - Consider selling")
        elif score >= 50:
            recommendations.append("Moderate potential - Could work with improvements")
        else:
            recommendations.append("Low potential - Consider other products")
        
        margin = insights.get("estimated_margin", "")
        if "40" in margin or "50" in margin:
            recommendations.append("Good margin opportunity")
        
        return recommendations