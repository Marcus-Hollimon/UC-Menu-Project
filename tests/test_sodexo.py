"""Turning Sodexo's JSON into rows, meal hours, and loading rows into the database.

Requirements: D1 (7 days of menus), D3 (nutrition and diet labels), D4 (keep old data on failure),
and how the app uses Sodexo's data (PROJECT_SPEC.md decision 8).
"""
import datetime as dt
import re
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app import ingest, sodexo
from app.halls import HALLS, HallSlug
from app.ingest import refresh_menus
from app.models import Schedule
from app.sodexo import HEADERS, NON_FOOD_INGREDIENTS, clean_text, flatten_menu, parse_amount
from tests.conftest import MENU_DAY, fake_fetch, load_fixture

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Sodexo's key has this shape (a UUID); nothing in the repository should.
KEY_SHAPE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


def test_requests_name_this_app_instead_of_posing_as_the_dining_site():
    assert "Origin" not in HEADERS
    assert "UC-Menu-Project" in HEADERS["User-Agent"]


def test_no_api_key_is_kept_in_the_repository():
    files = [*PROJECT_ROOT.glob("app/**/*.py"), *PROJECT_ROOT.glob("app/static/*"), *PROJECT_ROOT.glob("tests/**/*"),
             *PROJECT_ROOT.glob("*.md"), PROJECT_ROOT / ".env.example"]
    for path in files:
        if path.is_file():
            assert not KEY_SHAPE.search(path.read_text(encoding="utf-8", errors="ignore")), path.name


def test_fetch_menu_sends_the_key_from_the_environment(monkeypatch):
    sent = {}

    def fake_get(url, params, headers, timeout):
        sent.update(headers)
        return httpx.Response(200, json=[], request=httpx.Request("GET", url))

    monkeypatch.setenv("SODEXO_API_KEY", "key-from-dot-env")
    monkeypatch.setattr(sodexo.httpx, "get", fake_get)

    assert sodexo.fetch_menu(HALLS[HallSlug.MARKETPOINTE], MENU_DAY) == []
    assert sent["Api-Key"] == "key-from-dot-env"


def test_refresh_button_explains_a_missing_key(client, monkeypatch):
    monkeypatch.delenv("SODEXO_API_KEY", raising=False)

    response = client.post("/menus/refresh", params={"days": 1})

    assert response.status_code == 503
    assert "SODEXO_API_KEY" in response.json()["detail"]


def test_command_line_stops_before_touching_the_database_without_a_key(monkeypatch):
    def must_not_run(*args, **kwargs):
        raise AssertionError("touched the database without a key")

    monkeypatch.delenv("SODEXO_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["app.ingest", "--reset"])
    monkeypatch.setattr(ingest.Base.metadata, "drop_all", must_not_run)
    monkeypatch.setattr(ingest, "init_db", must_not_run)

    with pytest.raises(SystemExit, match="SODEXO_API_KEY"):
        ingest.main()


@pytest.mark.parametrize("slug", [hall.value for hall in HallSlug])
def test_fixture_menus_keep_facts_but_not_sodexo_text(slug):
    # The repo is public, and Sodexo's terms forbid redistributing its content.
    # Dish names and nutrition numbers are facts; descriptions and ingredient lists are left out.
    for meal in load_fixture(slug):
        for group in meal["groups"]:
            for item in group["items"]:
                assert "description" not in item
                assert item.get("ingredients") in {None, *NON_FOOD_INGREDIENTS}


def test_clean_text_decodes_entities_and_collapses_spaces():
    assert clean_text("  Mac &amp; Cheese ") == "Mac & Cheese"
    assert clean_text("Mexican  Brown Rice") == "Mexican Brown Rice"
    assert clean_text(None) == ""


def test_flatten_menu_gives_one_row_per_dish():
    rows = flatten_menu(load_fixture("center-court"))

    assert len(rows) == 7
    pizza = next(r for r in rows if r.name == "Roasted Vegetable Pizza")
    assert (pizza.meal, pizza.station, pizza.is_vegetarian) == ("Lunch", "Slices", True)


def test_flatten_menu_cleans_names_and_skips_filler():
    names = {row.name for row in flatten_menu(load_fixture("center-court"))}

    assert "Mexican Brown Rice" in names
    assert "Have a Nice Day" not in names


@pytest.mark.parametrize("value, expected", [
    ("264", 264),
    ("35g", 35),
    ("523mg", 523),
    ("2.6g", 3),
    (0, 0),
    ("", None),
    (None, None),
    ("n/a", None),
])
def test_parse_amount_keeps_the_leading_number(value, expected):
    assert parse_amount(value) == expected


def test_flatten_menu_reads_diet_labels_and_nutrition():
    rows = flatten_menu(load_fixture("marketpointe"))

    beans = next(r for r in rows if r.name == "Sofrito Black Beans")
    assert (beans.is_vegan, beans.is_vegetarian, beans.is_plant_based, beans.is_mindful) == (True, True, True, True)
    assert (beans.calories, beans.carbs_g, beans.protein_g, beans.fat_g, beans.portion) == (45, 6, 2, 2, "1/4 CUP")


def test_hours_depend_on_hall_and_day_of_week():
    tuesday, saturday = dt.date(2026, 9, 22), dt.date(2026, 9, 26)
    center_court = HALLS[HallSlug.CENTER_COURT]
    marketpointe = HALLS[HallSlug.MARKETPOINTE]

    assert center_court.hours_for(tuesday, "Lunch") == (dt.time(10, 30), dt.time(16, 30))
    assert center_court.hours_for(saturday, "Lunch") is None  # closed weekends
    assert marketpointe.hours_for(saturday, "Brunch") == (dt.time(9), dt.time(16, 30))


def test_refresh_stores_servings_with_times(db):
    summary = refresh_menus(db, start=MENU_DAY, days=1, fetch=fake_fetch)

    assert summary.servings == 16
    assert summary.failed == []
    breakfast = db.scalars(select(Schedule).where(Schedule.meal == "Breakfast")).first()
    assert (breakfast.start_time, breakfast.end_time) == (dt.time(7), dt.time(10, 30))


def test_refreshing_twice_does_not_duplicate(db):
    refresh_menus(db, start=MENU_DAY, days=1, fetch=fake_fetch)
    refresh_menus(db, start=MENU_DAY, days=1, fetch=fake_fetch)

    assert db.scalar(select(func.count()).select_from(Schedule)) == 16


def test_refresh_keeps_going_when_one_hall_fails(db):
    def flaky_fetch(hall, day):
        if hall.slug == HallSlug.CENTER_COURT:
            raise httpx.ConnectError("offline")
        return fake_fetch(hall, day)

    summary = refresh_menus(db, start=MENU_DAY, days=1, fetch=flaky_fetch)

    assert summary.servings == 9
    assert len(summary.failed) == 1
    assert summary.failed[0].startswith("Center Court 2026-09-22")


def test_refresh_retries_a_download_that_fails_once(db):
    calls = []

    def fetch_that_stalls_once(hall, day):
        calls.append(hall.slug)
        if hall.slug == HallSlug.CENTER_COURT and calls.count(hall.slug) == 1:
            raise httpx.ReadTimeout("The read operation timed out")
        return fake_fetch(hall, day)

    summary = refresh_menus(db, start=MENU_DAY, days=1, fetch=fetch_that_stalls_once)

    assert summary.failed == []
    assert summary.servings == 16
    assert calls.count(HallSlug.CENTER_COURT) == 2
