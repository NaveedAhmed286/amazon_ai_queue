import os
import json
import uuid
import redis
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.logger import logger

class QueueManager:
    def __init__(self):
        # Railway provides Redis URL
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis = redis.from_url(redis_url)
        
        # Queue names
        self.TASK_QUEUE = "amazon:queue:tasks"
        self.RESULT_PREFIX = "amazon:result:"
        self.STATUS_PREFIX = "amazon:status:"
        self.STATS_KEY = "amazon:stats"
        
        # Initialize stats
        self._init_stats()
    
    def _init_stats(self):
        """Initialize statistics"""
        if not self.redis.exists(self.STATS_KEY):
            self.redis.hset(self.STATS_KEY, mapping={
                "processed_today": "0",
                "total_processed": "0",
                "avg_processing_time": "0"
            })
    
    async def add_task(self, task_type: str, client_id: str, data: Dict, priority: str = "normal") -> str:
        """Add task to queue"""
        task_id = f"{client_id}_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        task_data = {
            "task_id": task_id,
            "type": task_type,
            "client_id": client_id,
            "data": data,
            "priority": priority,
            "created_at": datetime.utcnow().isoformat(),
            "status": "queued"
        }
        
        # Add to queue based on priority
        if priority == "high":
            self.redis.lpush(self.TASK_QUEUE, json.dumps(task_data))
        else:
            self.redis.rpush(self.TASK_QUEUE, json.dumps(task_data))
        
        # Store initial status
        status_data = {
            "status": "queued",
            "created_at": task_data["created_at"],
            "queue_position": await self.get_queue_position(task_id)
        }
        
        self.redis.setex(
            f"{self.STATUS_PREFIX}{task_id}",
            86400,  # 24 hours
            json.dumps(status_data)
        )
        
        logger.info(f"Task queued: {task_id} ({task_type})")
        return task_id
    
    async def get_next_task(self) -> Optional[Dict]:
        """Get next task from queue (blocking)"""
        # Block for up to 30 seconds waiting for task
        result = self.redis.brpop(self.TASK_QUEUE, timeout=30)
        
        if result:
            _, task_json = result
            task = json.loads(task_json)
            
            # Update status to processing
            status_data = {
                "status": "processing",
                "started_at": datetime.utcnow().isoformat(),
                "queue_position": "0"
            }
            
            self.redis.setex(
                f"{self.STATUS_PREFIX}{task['task_id']}",
                86400,
                json.dumps(status_data)
            )
            
            return task
        
        return None
    
    async def save_result(self, task_id: str, client_id: str, results: Dict):
        """Save task results"""
        result_data = {
            "task_id": task_id,
            "client_id": client_id,
            "results": results,
            "completed_at": datetime.utcnow().isoformat(),
            "status": "completed"
        }
        
        # Save results (available for 24 hours)
        self.redis.setex(
            f"{self.RESULT_PREFIX}{task_id}",
            86400,
            json.dumps(result_data)
        )
        
        # Update status
        status_data = {
            "status": "completed",
            "completed_at": result_data["completed_at"]
        }
        
        self.redis.setex(
            f"{self.STATUS_PREFIX}{task_id}",
            86400,
            json.dumps(status_data)
        )
        
        # Update statistics
        self._update_stats()
        
        logger.info(f"Results saved for task: {task_id}")
    
    async def get_result(self, task_id: str) -> Optional[Dict]:
        """Get task results"""
        # Check for results
        result_json = self.redis.get(f"{self.RESULT_PREFIX}{task_id}")
        
        if result_json:
            return json.loads(result_json)
        
        # Check status if not completed
        status_json = self.redis.get(f"{self.STATUS_PREFIX}{task_id}")
        if status_json:
            status = json.loads(status_json)
            return {
                "task_id": task_id,
                "status": status["status"],
                "message": self._get_status_message(status),
                "queue_position": status.get("queue_position")
            }
        
        return None
    
    def _get_status_message(self, status: Dict) -> str:
        """Get human-readable status message"""
        status_type = status.get("status", "unknown")
        
        messages = {
            "queued": "Task is waiting in queue",
            "processing": "Task is being processed",
            "completed": "Task completed successfully",
            "failed": "Task failed to process"
        }
        
        return messages.get(status_type, "Unknown status")
    
    async def get_queue_position(self, task_id: str) -> int:
        """Get task's position in queue"""
        # Get all tasks from queue
        tasks = self.redis.lrange(self.TASK_QUEUE, 0, -1)
        
        for i, task_json in enumerate(tasks):
            task = json.loads(task_json)
            if task.get("task_id") == task_id:
                return i + 1  # Position in queue (1-based)
        
        return 0  # Not in queue (might be processing or completed)
    
    async def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.redis.llen(self.TASK_QUEUE)
    
    def _update_stats(self):
        """Update processing statistics"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        processed_key = f"processed:{today}"
        
        # Increment counters
        self.redis.incr(processed_key)
        self.redis.incrby(self.STATS_KEY + ":total_processed", 1)
        
        # Set expiry for daily counter (48 hours to be safe)
        self.redis.expire(processed_key, 172800)
    
    async def get_stats(self) -> Dict:
        """Get queue statistics"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        processed_today = self.redis.get(f"processed:{today}") or "0"
        
        queue_size = await self.get_queue_size()
        avg_wait = queue_size * 10  # Estimate 10 seconds per task
        
        return {
            "queue_size": queue_size,
            "active_workers": 1,  # For now, single worker
            "processed_today": int(processed_today),
            "avg_wait_seconds": avg_wait
        }