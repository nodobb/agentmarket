"""
Database connection and initialization.

The API code uses synchronous SQLAlchemy sessions (`db.query(...)`) throughout,
so the database layer must provide a synchronous Session for both SQLite and
PostgreSQL. Keeping this sync avoids FastAPI injecting an async session into sync
query code, and avoids accidentally returning a generator object instead of a
session.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agentmarket.models.database import Base
from agentmarket.utils.config import settings


connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_dependency():
    """FastAPI dependency that yields a real SQLAlchemy Session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
