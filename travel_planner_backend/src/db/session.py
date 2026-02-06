from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.core.settings import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for ORM models."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _get_engine() -> Engine:
    """Create (or return) the process-global SQLAlchemy engine.

    This is intentionally lazy to avoid crashing app startup if:
    - environment variables are not injected yet, or
    - the database is temporarily unavailable at startup time.

    The engine will be created on the first request that needs DB access.
    """
    global _engine, _SessionLocal
    if _engine is not None and _SessionLocal is not None:
        return _engine

    settings = get_settings()
    _engine = create_engine(settings.sqlalchemy_database_uri, pool_pre_ping=True)
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _engine


def _get_sessionmaker() -> sessionmaker[Session]:
    """Return a lazily-initialized SessionLocal."""
    if _SessionLocal is None:
        _get_engine()
    # At this point it must be set; mypy/typing: keep runtime assertion.
    assert _SessionLocal is not None
    return _SessionLocal


# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """This is a public function.

    FastAPI dependency that yields a SQLAlchemy Session and guarantees cleanup.

    Notes:
        Engine/session creation is lazy; if the DB is unavailable, the first DB-backed
        request will fail, but the service can still start and serve non-DB endpoints.

    Yields:
        sqlalchemy.orm.Session: DB session scoped to the request.
    """
    db: Session = _get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
