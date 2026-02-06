from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.core.settings import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for ORM models."""


# Create engine once per process.
_settings = get_settings()
engine = create_engine(
    _settings.sqlalchemy_database_uri,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """This is a public function.

    FastAPI dependency that yields a SQLAlchemy Session and guarantees cleanup.

    Yields:
        sqlalchemy.orm.Session: DB session scoped to the request.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
