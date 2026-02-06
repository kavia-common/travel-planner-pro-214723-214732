from __future__ import annotations

import os
from dataclasses import dataclass


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
        """Build a SQLAlchemy psycopg URL for PostgreSQL."""
        # psycopg3 SQLAlchemy dialect uses `postgresql+psycopg`
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
    # - full URL (e.g. postgresql://user:pass@host:port/db)
    # We keep parsing minimal and robust: if it contains '://', try to extract host.
    postgres_host = postgres_url.strip()
    if "://" in postgres_host and "@" in postgres_host:
        # naive split: scheme://creds@host:port/db
        try:
            after_at = postgres_host.split("@", 1)[1]
            host_port_and_path = after_at.split("/", 1)[0]
            postgres_host = host_port_and_path.split(":", 1)[0]
        except Exception:
            # Fall back to raw POSTGRES_URL as host; engine creation will fail with a clear error.
            postgres_host = postgres_url.strip()

    return Settings(
        postgres_url=postgres_url,
        postgres_user=postgres_user,
        postgres_password=postgres_password,
        postgres_db=postgres_db,
        postgres_port=postgres_port,
        postgres_host=postgres_host,
    )
