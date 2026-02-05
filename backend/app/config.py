from pydantic_settings import BaseSettings
from typing import Optional
import os

# Load .env from parent directory (project root)
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))


class Settings(BaseSettings):
    OCR_LOW_CONFIDENCE: float = 60.0
    
    # Feature flags
    # Vision Pipeline Active
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
