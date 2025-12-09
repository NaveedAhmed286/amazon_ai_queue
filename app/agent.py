import os
import json
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Any
from app.logger import logger
from app.memory_manager import memory_manager

class AmazonAgent:
    def __init__(self):
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        self.deepseek_api_url = "https://api.deepseek.com/v1/chat/completions"
        
    async def analyze_products(self, products: List[Dict]) -> Dict:
        """Analyze Amazon products using DeepSeek"""
        try:
            # Get product context
            product_context = self._prepare_product_context(products)
            
            # Get analysis from DeepSeek
            analysis = await self._get_deepseek_analysis(
                context=product_context,
                analysis_type="product_analysis"
            )
            
            # Extract insights
            insights = self._extract_insights(analysis)
            
            return {
                "status": "success",
                "products_analyzed": len(products),
                "analysis": analysis,
                "insights": insights,
                "recommendations": self._generate_recommendations(analysis, insights),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Product analysis error: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def analyze_with_memory(self, client_id: str, products: List[Dict]) -> Dict:
        """Analyze products with client memory context"""
        try:
            # Get client context from memory
            client_context = await memory_manager.get_client_context(client_id)
            
            # Prepare enhanced context
            product_context = self._prepare_product_context(products)
            enhanced_context = f"""
            CLIENT HISTORY:
            {client_context}
            
            CURRENT PRODUCTS TO ANALYZE:
            {product_context}
            
            Based on client history, provide targeted analysis.
            """
            
            # Get analysis
            analysis = await self._get_deepseek_analysis(
                context=enhanced_context,
                analysis_type="product_analysis_with_memory"
            )
            
            # Extract and learn insights
            insights = self._extract_insights(analysis)
            
            # Store in memory
            task_id = f"product_{int(datetime.utcnow().timestamp())}"
            await memory_manager.learn_from_analysis(
                client_id=client_id,
                task_id=task_id,
                analysis_type="product_analysis",
                input_data={"products": products},
                result_data=analysis,
                key_insights=insights[:3]  # Top 3 insights
            )
            
            return {
                "status": "success",
                "client_id": client_id,
                "products_analyzed": len(products),
                "analysis": analysis,
                "insights": insights,
                "personalized": bool(client_context),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Memory analysis error: {e}")
            return await self.analyze_products(products)  # Fallback
    
    async def _get_deepseek_analysis(self, context: str, analysis_type: str) -> str:
        """Get analysis from DeepSeek API"""
        if not self.deepseek_api_key:
            logger.warning("DeepSeek API key not configured")
            return "Analysis service not configured."
        
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = self._build_analysis_prompt(context, analysis_type)
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are an expert Amazon product analyst."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.deepseek_api_url,
                    headers=headers,
                    json=payload,
                    timeout=60
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
                    else:
                        error_text = await response.text()
                        logger.error(f"DeepSeek API error: {error_text}")
                        return f"API Error: {response.status}"
                        
        except Exception as e:
            logger.error(f"DeepSeek request failed: {e}")
            return f"Request failed: {str(e)}"
    
    def _prepare_product_context(self, products: List[Dict]) -> str:
        """Prepare product data for analysis"""
        context_lines = []
        for i, product in enumerate(products[:10]):  # Limit to 10 products
            context_lines.append(f"Product {i+1}:")
            context_lines.append(f"  Title: {product.get('title', 'N/A')}")
            context_lines.append(f"  Price: {product.get('price', 'N/A')}")
            context_lines.append(f"  Rating: {product.get('rating', 'N/A')}")
            context_lines.append(f"  Reviews: {product.get('review_count', 'N/A')}")
            if product.get('description'):
                context_lines.append(f"  Description: {product.get('description')[:200]}...")
            context_lines.append("")
        
        return "\n".join(context_lines)
    
    def _build_analysis_prompt(self, context: str, analysis_type: str) -> str:
        """Build prompt for DeepSeek"""
        if analysis_type == "product_analysis":
            return f"""
            Analyze these Amazon products for investment potential:
            
            {context}
            
            Provide:
            1. Market demand assessment
            2. Competition analysis
            3. Profit margin estimation
            4. Risk factors
            5. Investment recommendation (Yes/No/Maybe)
            6. Key insights (bullet points)
            
            Format as structured JSON if possible.
            """
        else:
            return f"""
            {context}
            
            Provide detailed analysis with actionable insights.
            """
    
    def _extract_insights(self, analysis: str) -> List[str]:
        """Extract key insights from analysis text"""
        insights = []
        lines = analysis.split('\n')
        
        for line in lines:
            line = line.strip()
            if any(keyword in line.lower() for keyword in ['insight', 'key finding', 'important', 'critical', 'recommend']):
                insights.append(line)
        
        # If no insights found, extract first 3 meaningful lines
        if not insights:
            insights = [line for line in lines if line and len(line) > 20][:3]
        
        return insights
    
    def _generate_recommendations(self, analysis: str, insights: List[str]) -> Dict:
        """Generate actionable recommendations"""
        return {
            "investment_advice": self._extract_investment_advice(analysis),
            "next_steps": [
                "Review competition more thoroughly",
                "Check supplier reliability",
                "Calculate shipping and storage costs",
                "Set up price monitoring"
            ],
            "key_insights": insights[:5],
            "risk_level": self._assess_risk_level(analysis)
        }
    
    def _extract_investment_advice(self, analysis: str) -> str:
        """Extract investment advice from analysis"""
        analysis_lower = analysis.lower()
        if 'not recommended' in analysis_lower or 'avoid' in analysis_lower:
            return "Not Recommended"
        elif 'highly recommended' in analysis_lower or 'excellent' in analysis_lower:
            return "Highly Recommended"
        elif 'recommended' in analysis_lower or 'good' in analysis_lower:
            return "Recommended"
        else:
            return "Needs Further Research"
    
    def _assess_risk_level(self, analysis: str) -> str:
        """Assess risk level from analysis"""
        analysis_lower = analysis.lower()
        if any(word in analysis_lower for word in ['high risk', 'very risky', 'dangerous']):
            return "High"
        elif any(word in analysis_lower for word in ['moderate risk', 'medium risk']):
            return "Medium"
        elif any(word in analysis_lower for word in ['low risk', 'safe', 'stable']):
            return "Low"
        else:
            return "Unknown"

# Global instance
agent = AmazonAgent()