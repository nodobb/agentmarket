"""
Application Configuration Management
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Core Application
    DEBUG: bool = True
    SECRET_KEY: str = "your-super-secret-key-change-this-in-production"
    ALLOWED_HOSTS: str = "*"
    CORS_ORIGINS: str = "*"
    
    # Database
    DATABASE_URL: str = "sqlite:///./agentmarket.db"
    
    # Redis (for caching and sessions)
    REDIS_URL: Optional[str] = None
    
    # Stripe Payment Processing
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    
    # JWT Settings
    JWT_SECRET_KEY: str = "jwt-secret-key-change-this"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Email Configuration
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SUPPORT_EMAIL: str = "support@agentmarket.com"
    
    # Business Configuration
    COMMISSION_RATE: float = 0.025  # 2.5%
    MIN_TRANSACTION_AMOUNT: float = 1.00
    MAX_TRANSACTION_AMOUNT: float = 10000.00
    HANDSHAKE_EXPIRE_MINUTES: int = 5
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Analytics
    ANALYTICS_ENABLED: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()