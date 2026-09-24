"""Shared test setup: a throwaway in-memory database and saved menus instead of the network."""
import datetime as dt
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.ingest import init_db, refresh_menus
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"
MENU_DAY = dt.date(2026, 9, 22)  # a Tuesday: the day the fixture menus were saved


def load_fixture(slug: str) -> list[dict]:
    return json.loads((FIXTURES / f"{slug}.json").read_text(encoding="utf-8"))


def fake_fetch(hall, day):
    """Stands in for sodexo.fetch_menu: same saved menu for every day."""
    return load_fixture(hall.slug)


@pytest.fixture
def db():
    # StaticPool keeps one connection, so every session sees the same in-memory database.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    # Not `with TestClient(app)`: that would run the app's startup against the real uc_menu.db.
    # base_url: the app only answers requests addressed to 127.0.0.1 or localhost.
    yield TestClient(app, base_url="http://127.0.0.1")
    app.dependency_overrides.clear()


@pytest.fixture
def menus(db):
    """Load the saved menus for MENU_DAY."""
    return refresh_menus(db, start=MENU_DAY, days=1, fetch=fake_fetch)
