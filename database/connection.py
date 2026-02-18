"""
Database connection and session management.
"""

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from core.config import settings
from database.models import Base


def _ensure_data_dir() -> Path:
    """Ensure data directory exists for SQLite."""
    if "sqlite" in settings.DATABASE_URL:
        path = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
    return Path(".")


def _get_engine():
    """Create SQLAlchemy engine with appropriate config."""
    _ensure_data_dir()

    connect_args = {}
    if "sqlite" in settings.DATABASE_URL:
        connect_args["check_same_thread"] = False

    return create_engine(
        settings.DATABASE_URL,
        connect_args=connect_args,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=5 if not settings.USE_SQLITE else 1,
        max_overflow=10 if not settings.USE_SQLITE else 0,
    )


engine = _get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
