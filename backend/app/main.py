"""
Main FastAPI application for RankPredict v2
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import strategy, outline, auth
from app.database import init_db
from app.config import ALLOWED_ORIGINS

app = FastAPI(
    title="RankPredict v2 API",
    description="Two-screen SEO tool: Strategy Dashboard + Dynamic Outline Builder",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    print("RankPredict v2 API started")

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(strategy.router, prefix="/api/strategy", tags=["strategy"])
app.include_router(outline.router, prefix="/api/outline", tags=["outline"])


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "RankPredict v2 API"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "RankPredict v2 API",
        "version": "2.0.0",
        "docs": "/docs"
    }

