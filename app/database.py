"""
Database Setup & Session Management.

Configures SQLAlchemy engine, session factory, declarative base, and FastAPI
dependency for request-scoped database sessions.
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

# SQLite requires check_same_thread=False when the same connection
# might be used across multiple threads (e.g., in FastAPI async handlers or background tasks).
# When switching to PostgreSQL or MySQL, this argument is omitted.
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

# Session factory for generating new database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for all SQLAlchemy ORM models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session per HTTP request
    and guarantees it is closed upon request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Creates all database tables defined in the ORM models.
    Called on application startup.
    """
    # Import models here so Base.metadata knows about them
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
