"""Database connection and session setup.

Uses DATABASE_URL when it's set (the hosted Postgres database), otherwise a local
SQLite file. A .env file in the project root is read automatically.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Doesn't override variables that are already set, so the host's settings win in production.
load_dotenv(PROJECT_ROOT / ".env")


def database_url() -> URL:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return URL.create("sqlite", database=str(PROJECT_ROOT / "uc_menu.db"))
    # Hosts hand out "postgres://" or "postgresql://" URLs; point them at the psycopg 3 driver we install.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url.removeprefix(prefix)
    return make_url(url)


def make_engine(url: URL):
    if url.get_backend_name() == "sqlite":
        # FastAPI handles requests on worker threads, and SQLite otherwise refuses to
        # use a connection from a thread other than the one that made it.
        return create_engine(url, connect_args={"check_same_thread": False})
    # Neon suspends the database after a few idle minutes, which drops open connections.
    # pre_ping checks each pooled connection before use and replaces dead ones.
    return create_engine(url, pool_pre_ping=True)


engine = make_engine(database_url())
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: one database session per request, closed afterwards."""
    with SessionLocal() as db:
        yield db
