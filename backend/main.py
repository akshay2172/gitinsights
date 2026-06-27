import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database.database import engine, Base
from backend.routers import repos, explorer, search, chat, explain
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="GitInsight API",
    description="AI-powered GitHub repository analyzer using RAG & LangChain",
    version="1.0"
)

# Configure CORS to allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local dev; restrict to specific domains in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(repos.router, prefix="/api")
app.include_router(explorer.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(explain.router, prefix="/api")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "Welcome to the GitInsight API! Use /docs to view endpoint specifications."
    }

if __name__ == "__main__":
    import uvicorn
    # Bind to port 8000
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
