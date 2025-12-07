import os
import json
import requests
from typing import Dict, List, Optional
from app.logger import logger

class MakeClient:
    def __init__(self):
        self.webhook_url = os.getenv("MAKE_WEBHOOK_URL")
        self.api_key = os.getenv("MAKE_API_KEY")
        
    async def send_analysis_results(self, client_id: str, analysis_data: Dict, webhook_url: Optional[str] = None) -> bool:
        """
        Send analysis results to Make.com webhook
        """
        try:
            # Use provided webhook URL or default
            url = webhook_url or self.webhook_url
            
            if not url:
                logger.warning("No Make.com webhook URL configured")
                return False
            
            payload = {
                "client_id": client_id,
                "analysis_type": "product_analysis",
                "data": analysis_data,
                "timestamp": analysis_data.get("timestamp"),
                "status": "completed"
            }
            
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Results sent to Make.com for client: {client_id}")
                return True
            else:
                logger.error(f"❌ Make.com webhook failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending to Make.com: {e}")
            return False
    
    async def send_keyword_analysis(self, client_id: str, keyword: str, analysis_data: Dict, webhook_url: Optional[str] = None) -> bool:
        """
        Send keyword analysis to Make.com
        """
        try:
            url = webhook_url or self.webhook_url
            
            if not url:
                logger.warning("No Make.com webhook URL configured")
                return False
            
            payload = {
                "client_id": client_id,
                "analysis_type": "keyword_analysis",
                "keyword": keyword,
                "data": analysis_data,
                "opportunity_score": analysis_data.get("opportunity_score", 0),
                "recommendations": analysis_data.get("recommendations", []),
                "timestamp": analysis_data.get("timestamp")
            }
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Keyword analysis sent to Make.com: {keyword}")
                return True
            else:
                logger.error(f"❌ Make.com keyword webhook failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending keyword to Make.com: {e}")
            return False
    
    async def notify_client(self, client_email: str, subject: str, message: str, results_url: Optional[str] = None) -> bool:
        """
        Send email notification via Make.com
        """
        try:
            if not self.webhook_url:
                return False
            
            payload = {
                "action": "send_email",
                "client_email": client_email,
                "subject": subject,
                "message": message,
                "results_url": results_url,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            response = requests.post(self.webhook_url, json=payload, timeout=30)
            return response.status_code in [200, 201, 202]
            
        except Exception as e:
            logger.error(f"Error notifying client: {e}")
            return False

# Global instance
make_client = MakeClient()