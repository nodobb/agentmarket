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
    _add_missing_columns()


def _add_missing_columns():
    """
    Minimal migration: create_all never alters existing tables, so columns
    added to the models after a database was first created must be added
    here. (A future move to Alembic would replace this.)
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing:
                    ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(engine.dialect)}"
                    conn.execute(text(ddl))
