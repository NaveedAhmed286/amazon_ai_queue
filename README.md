Amazon AI Queue Agent

🚀 Fully automated Amazon product analysis system using DeepSeek AI + Google Sheets + Redis queue — built for speed, safety, and scalability.

---

🛠️ Features

· ✅ Accepts Google Form submissions (investment/price or keywords)
· ✅ Analyzes products using DeepSeek AI
· ✅ Stores results in Google Sheets automatically
· ✅ Redis queue ensures tasks are processed in order
· ✅ Memory system saves past insights for smarter recommendations
· ✅ Completely Make.com-free (all processing inside Python agent)

---

📁 Project Structure

```
amazon_ai_queue/
├─ app/
│  ├─ __init__.py          # Trigger deploy timestamp
│  ├─ main.py              # FastAPI endpoints + queue processor
│  ├─ agent.py             # AmazonAgent: DeepSeek analysis + Google Sheets saving
│  ├─ queue_manager.py     # Redis queue management
│  ├─ memory_manager.py    # Short-term & long-term memory system
│  ├─ database.py          # PostgreSQL storage (long-term memory + analysis history)
│  ├─ logger.py            # Logging configuration
│  ├─ apify_client.py      # Scraping Amazon products
│  └─ service_account.json # Google service account (if local)
├─ requirements.txt        # Python dependencies
└─ README.md               # This file
```

---

📝 Google Sheet Setup

Columns (Sheet: amazon_ai_queue/ → E):

(Column structure matches automated output from the AI agent)

Column Name Description
timestamp Submission time
query Input keyword or investment range
product_title Amazon product title
price Current price
analysis DeepSeek AI insights
recommendation Buy / Avoid / Research further
past_memory_used Whether historical data was applied
status Processed / Pending / Failed

---

🚀 How It Works

1. User submits a Google Form (investment range or keywords)
2. Form writes to Google Sheets (triggers the agent)
3. Redis queue picks the task in order
4. AmazonAgent uses DeepSeek AI to analyze product data
5. Memory system enhances analysis with past insights
6. Results saved back to Google Sheets + PostgreSQL for history
7. Fully automated — no manual steps after submission

---

🧠 Memory System

· Short-term: Redis cache for session-based insights
· Long-term: PostgreSQL database for historical analysis & trends
· Smarter over time — learns from past recommendations

---

⚙️ Tech Stack

· Backend: FastAPI (Python)
· AI: DeepSeek API
· Queue: Redis
· Storage: Google Sheets API, PostgreSQL
· Scraping: Apify client for Amazon data
· Logging: Structured logs via logger.py

---

📦 Deployment

· Ready for scalable cloud deployment
· Environment variables for API keys & database connections
· Includes requirements.txt for dependencies

---

✅ Why It’s Reliable

· ✅ Ordered processing via Redis queue
· ✅ No third-party automation tools (all in Python)
· ✅ Persistent memory for improved accuracy
· ✅ Error logging & retry logic built-in
· ✅ Secure credential handling via service accounts

---

🎯 Use Cases

· Amazon product research
· Investment decision support
· Product trend analysis
· Automated competitor tracking

---

📬 Contact

Built for speed, safety, and scalability — fully automated, no manual intervention needed.

---

This README is technical and complete — deploy directly. 🚀   
