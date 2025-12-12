"""
Application Configuration
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    ENVIRONMENT: str = "development"
    
    # LLM API Keys (Optional - basic analysis works without them)
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    
    # Database
    DATABASE_URL: str = "sqlite:///./lattice.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Security
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    
    # File Upload
    MAX_FILE_SIZE_MB: int = 10
    UPLOAD_DIR: str = "./uploads"
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".txt", ".png", ".jpg", ".jpeg", ".tiff"]

    # OCR
    OCR_LOW_CONFIDENCE: int = 75
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Logging
    LOG_LEVEL: str = "info"
    
    # Computation Limits
    MAX_COMPUTATION_TIME: int = 5  # seconds
    MAX_MEMORY_MB: int = 100
    
    # LLM Settings
    LLM_PROVIDER: str = "gemini"  # "openai" or "gemini"
    LLM_MODEL: str = "gemini-2.5-flash"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
