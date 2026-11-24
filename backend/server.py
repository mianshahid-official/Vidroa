"""
FastAPI application entry point for PromptBeast backend.
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.router import api_router

from backend.config import backend_config

app = FastAPI(
    title="PromptBeast Cloud AI API",
    description="Cloud AI inference backend for narration-to-storyboard generation targeting Qwen 30B models.",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "PromptBeast Cloud AI Backend",
        "model": backend_config.model_name,
        "gpu": backend_config.gpu_type,
        "version": "1.0.0",
        "endpoints": {
            "health": "/api/v1/health",
            "test_connection": "/api/v1/test_connection",
            "jobs": "/api/v1/jobs",
            "docs": "/docs"
        }
    }


@app.get("/health")
def root_health():
    return {
        "status": "healthy",
        "service": "PromptBeast Cloud AI Backend",
        "model": backend_config.model_name,
        "gpu": backend_config.gpu_type,
        "version": "1.0.0"
    }


app.include_router(api_router)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
