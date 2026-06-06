"""
Database connection and initialization
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from agentmarket.utils.config import settings
from agentmarket.models.database import Base
import asyncio


# Determine if we're using async or sync database
if settings.DATABASE_URL.startswith("postgresql"):
    # Use async PostgreSQL
    async_engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        echo=settings.DEBUG
    )
    AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession)
    
    async def get_async_db():
        async with AsyncSessionLocal() as session:
            yield session
            
    async def init_db():
        """Initialize database tables"""
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

else:
    # Use sync SQLite for development
    engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    async def init_db():
        """Initialize database tables"""
        Base.metadata.create_all(bind=engine)


# Database dependency
if settings.DATABASE_URL.startswith("postgresql"):
    get_db_dependency = get_async_db
else:
    def get_db_dependency():
        return get_db()