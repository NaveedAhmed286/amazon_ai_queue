# Amazon AI Queue Agent

This is a **fully automated Amazon product analysis system** using DeepSeek + Google Sheets + Redis memory queue.  
Designed for **fast, safe, and scalable workflow**.  

---

## 🛠 Features

- Accepts **Google Form submissions** (investment/price or keywords).  
- **Analyzes products** using DeepSeek AI.  
- Stores **results in Google Sheet** automatically.  
- **Redis queue** ensures tasks are processed in order.  
- **Memory system** saves past insights for smarter recommendations.  
- Completely **Make.com-free** (all processing inside Python agent).  

---

## 📝 Google Sheet Setup

**Columns (amazon_ai_queue/
├─ app/
│  ├─ __init__.py           # Trigger deploy timestamp
│  ├─ main.py               # FastAPI endpoints + queue processor
│  ├─ agent.py              # AmazonAgent: DeepSeek analysis + Google Sheets saving
│  ├─ queue_manager.py      # Redis queue management
│  ├─ memory_manager.py     # Short-term & long-term memory system
│  ├─ database.py           # PostgreSQL storage (long-term memory + analysis history)
│  ├─ logger.py             # Logging configuration
│  ├─ apify_client.py       # Scraping Amazon products
│  └─ service_account.json  # Google service account (if local)
├─ requirements.txt         # Python dependencies
└─ README.md                # This file → E):**
