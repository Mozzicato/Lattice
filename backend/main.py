"""
Lattice API - Main Application Entry Point
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import os
from contextlib import asynccontextmanager

from app.config import settings
from app.api.v1 import documents, equations, simulations, questions, summaries, sessions, notes_beautify_visual

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Lattice API...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Database: {settings.DATABASE_URL}")
    
    # Create upload directory if it doesn't exist
    import os
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Lattice API...")


# Create FastAPI application
app = FastAPI(
    title="Lattice API",
    description="AI-powered learning tool for understanding complex research papers and homework problems",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors gracefully"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "detail": str(exc) if settings.ENVIRONMENT == "development" else None
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Check API health status"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "Welcome to Lattice API",
        "version": "1.0.0",
        "docs": "/api/docs"
    }


# Include API routers
app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
app.include_router(equations.router, prefix="/api/v1", tags=["equations"])
app.include_router(simulations.router, prefix="/api/v1", tags=["simulations"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(questions.router, prefix="/api/v1", tags=["questions"])
app.include_router(summaries.router, prefix="/api/v1", tags=["summaries"])
app.include_router(notes_beautify_visual.router, prefix="/api/v1", tags=["notes-beautify"])

# Mount uploads directory for serving images
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development"
    )
