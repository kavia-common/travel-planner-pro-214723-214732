from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    postgres_url: str
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_port: str
    postgres_host: str

    @property
    def sqlalchemy_database_uri(self) -> str:
        """Build a SQLAlchemy psycopg URL for PostgreSQL.

        Supports two formats for POSTGRES_URL:
        - host only (e.g. "localhost" or "db")
        - full DSN (e.g. "postgresql://user:pass@host:port/db" or "postgresql://host:port/db")

        We always normalize to SQLAlchemy's psycopg3 dialect: "postgresql+psycopg://...".
        """
        raw = self.postgres_url.strip()

        # If POSTGRES_URL looks like a DSN, parse it and prefer its host/port/db when present.
        if "://" in raw:
            parsed = urlparse(raw)
            host = parsed.hostname or self.postgres_host
            port = str(parsed.port) if parsed.port is not None else self.postgres_port
            db = parsed.path.lstrip("/") or self.postgres_db

            return f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}@{host}:{port}/{db}"

        # Host-only format.
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            "This backend expects database container env vars to be configured."
        )
    return value


# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """This is a public function.

    Loads and validates settings from environment variables.

    Expected env vars (provided by database container):
    - POSTGRES_URL (may include host; we parse host from it when possible)
    - POSTGRES_USER
    - POSTGRES_PASSWORD
    - POSTGRES_DB
    - POSTGRES_PORT
    """
    postgres_url = _require_env("POSTGRES_URL")
    postgres_user = _require_env("POSTGRES_USER")
    postgres_password = _require_env("POSTGRES_PASSWORD")
    postgres_db = _require_env("POSTGRES_DB")
    postgres_port = _require_env("POSTGRES_PORT")

    # POSTGRES_URL may be either:
    # - host only (e.g. localhost)
    # - full URL/DSN (e.g. postgresql://user:pass@host:port/db or postgresql://host:port/db)
    # If it's a DSN, extract the hostname safely; otherwise treat it as host.
    postgres_host = postgres_url.strip()
    if "://" in postgres_host:
        parsed = urlparse(postgres_host)
        if parsed.hostname:
            postgres_host = parsed.hostname

    return Settings(
        postgres_url=postgres_url,
        postgres_user=postgres_user,
        postgres_password=postgres_password,
        postgres_db=postgres_db,
        postgres_port=postgres_port,
        postgres_host=postgres_host,
    )
