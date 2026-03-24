from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Loomin-Docs API",
    description="Air-gapped AI document editor backend",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "Loomin-Docs backend is running"}

@app.get("/health")
def health():
    return {"status": "ok", "message": "Health check will be expanded in Phase 3"}