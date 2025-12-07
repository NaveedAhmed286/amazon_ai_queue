from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "✅ Amazon AI Agent Running!", "status": "ready"}

@app.get("/health")
def health():
    return {"status": "healthy"}