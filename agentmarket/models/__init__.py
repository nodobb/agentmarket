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


# Render/Heroku provide postgres:// URLs, but SQLAlchemy 2.x only accepts postgresql://
database_url = settings.DATABASE_URL
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}

engine = create_engine(
    database_url,
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
