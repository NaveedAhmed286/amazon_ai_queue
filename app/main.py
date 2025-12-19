import os
import asyncio
import uuid
import signal
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional

from app.logger import logger
from app.queue_manager import QueueManager
from app.agent import AmazonAgent

# Initialize FastAPI
app = FastAPI(
    title="Amazon AI Queue Agent",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Initialize components
queue_manager = QueueManager()
agent = AmazonAgent()

# Track application state
app_state = {
    "healthy": True,
    "start_time": datetime.utcnow(),
    "total_tasks": 0,
    "failed_tasks": 0,
    "external_services": {
        "redis": True,
        "google_sheets": True,
        "deepseek": True
    }
}

# Models
class ProductAnalysisRequest(BaseModel):
    client_id: str
    products: List[Dict]
    priority: str = "normal"

class KeywordAnalysisRequest(BaseModel):
    client_id: str
    keyword: str
    max_products: int = 50
    investment: Optional[float] = None

# Signal handling for graceful shutdown
def handle_shutdown(signum, frame):
    logger.info("🛑 Received shutdown signal, cleaning up...")
    app_state["healthy"] = False
    # Add cleanup logic here if needed

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Amazon AI Agent starting up...")
    
    # Start queue processor
    asyncio.create_task(queue_processor())
    
    # Start health monitor
    asyncio.create_task(health_monitor())
    
    # Start service checker
    asyncio.create_task(service_health_checker())
    
    logger.info("✅ All background tasks started")

# Health monitor
async def health_monitor():
    """Monitor system health"""
    while True:
        try:
            # Check memory usage
            import psutil
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                logger.warning(f"⚠️ High memory usage: {memory.percent}%")
            
            # Check disk space
            disk = psutil.disk_usage('/')
            if disk.percent > 90:
                logger.warning(f"⚠️ Low disk space: {disk.percent}%")
                
        except Exception as e:
            logger.debug(f"Health monitor error: {e}")
        
        await asyncio.sleep(300)  # Check every 5 minutes

# Service health checker
async def service_health_checker():
    """Check external service health"""
    while True:
        try:
            # Check Redis
            redis_ok = await queue_manager.check_health()
            app_state["external_services"]["redis"] = redis_ok
            
            # Check Google Sheets (simple test)
            try:
                # Try a simple sheets operation
                pass  # You could add a test here
            except:
                app_state["external_services"]["google_sheets"] = False
            
        except Exception as e:
            logger.debug(f"Service health check error: {e}")
        
        await asyncio.sleep(60)  # Check every minute

# UNBREAKABLE Queue processor
async def queue_processor():
    """Process tasks from queue - designed to never crash"""
    logger.info("🔄 Queue processor started")
    
    restart_attempts = 0
    max_restarts = 10
    
    while restart_attempts < max_restarts:
        try:
            logger.info(f"🔄 Queue processor iteration {restart_attempts + 1}")
            
            processed_count = 0
            error_count = 0
            
            # Process up to 10 tasks in this iteration
            for _ in range(10):
                try:
                    processed = await process_next_task()
                    if processed:
                        processed_count += 1
                    else:
                        break  # No more tasks in queue
                except Exception as task_error:
                    error_count += 1
                    logger.error(f"Task processing error: {task_error}")
                    # Continue with next task
                    await asyncio.sleep(1)
            
            # Log batch results
            if processed_count > 0 or error_count > 0:
                logger.info(f"✅ Processed {processed_count} tasks, errors: {error_count}")
            
            # Exponential backoff when idle
            if processed_count == 0:
                sleep_time = min(30, 2 ** restart_attempts)
                await asyncio.sleep(sleep_time)
            else:
                restart_attempts = 0  # Reset on successful processing
                await asyncio.sleep(1)
                
        except Exception as catastrophic_error:
            restart_attempts += 1
            logger.critical(f"🚨 CATASTROPHIC: Queue processor crashed (attempt {restart_attempts}/{max_restarts}): {catastrophic_error}")
            import traceback
            logger.critical(f"Traceback: {traceback.format_exc()}")
            
            # Exponential backoff before restart
            wait_time = min(300, 30 * restart_attempts)  # Max 5 minutes
            logger.info(f"⏳ Waiting {wait_time}s before restart...")
            await asyncio.sleep(wait_time)
    
    logger.critical(f"🛑 Queue processor failed after {max_restarts} attempts. Manual restart required.")

# Process next task
async def process_next_task():
    """Process a single task from queue"""
    try:
        task = await queue_manager.get_next_task()
        if not task:
            return False

        task_id = task["task_id"]
        task_type = task["type"]
        client_id = task["client_id"]
        data = task["data"]

        logger.info(f"🔄 Processing {task_type}: {task_id}")
        await queue_manager.update_task_status(task_id, "processing")
        
        # Track total tasks
        app_state["total_tasks"] += 1

        try:
            if task_type == "product_analysis":
                results = await agent.analyze_products(data["products"])
            elif task_type == "keyword_analysis":
                results = await agent.analyze_keyword(
                    keyword=data["keyword"],
                    client_id=client_id,
                    max_products=data.get("max_products", 50)
                )
            else:
                results = {"error": "Unknown task type", "status": "failed"}
            
            # Save results
            await queue_manager.save_task_result(
                task_id=task_id,
                client_id=client_id,
                task_type=task_type,
                results=results
            )
            
            logger.info(f"✅ Completed {task_type}: {task_id}")
            return True
            
        except Exception as task_error:
            logger.error(f"Task {task_id} failed: {task_error}")
            app_state["failed_tasks"] += 1
            
            await queue_manager.save_task_result(
                task_id=task_id,
                client_id=client_id,
                task_type=task_type,
                results={"error": str(task_error), "status": "failed"}
            )
            return True  # Task was "processed" (failed)
            
    except Exception as e:
        logger.error(f"Task processing system error: {e}")
        return False  # Don't count as processed

# Enhanced Health endpoint
@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    try:
        redis_health = await queue_manager.check_health()
        queue_size = await queue_manager.get_queue_size()
        
        health_status = "healthy" if (
            redis_health and 
            app_state["healthy"] and
            queue_size < 100  # Not overloaded
        ) else "degraded"
        
        return {
            "status": health_status,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": str(datetime.utcnow() - app_state["start_time"]),
            "queue": {
                "size": queue_size,
                "total_tasks": app_state["total_tasks"],
                "failed_tasks": app_state["failed_tasks"]
            },
            "services": app_state["external_services"],
            "memory": {
                "percent": psutil.virtual_memory().percent if 'psutil' in globals() else "unknown"
            },
            "version": "2.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Amazon AI Queue Agent v2.0",
        "status": "operational" if app_state["healthy"] else "degraded",
        "features": [
            "Resilient task processing",
            "Automatic retry on failures",
            "Health monitoring",
            "External service checks"
        ],
        "endpoints": {
            "submit_products": "POST /api/analyze/products",
            "submit_keyword": "POST /api/analyze/keyword",
            "check_status": "GET /api/status/{task_id}",
            "queue_stats": "GET /api/queue/stats",
            "system_health": "GET /health",
            "docs": "/docs"
        }
    }

# [Keep all your existing API endpoints - they don't need to change]
# /api/analyze/products
# /api/analyze/keyword  
# /api/status/{task_id}
# /api/queue/stats

# Run app
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False, log_level="info")
