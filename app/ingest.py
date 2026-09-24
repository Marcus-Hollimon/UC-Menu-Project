"""Load dining hall data into the database.

Run `python -m app.ingest` to download the next 7 days of menus.
"""
import argparse
import datetime as dt
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import httpx
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app import sodexo
from app.database import Base, SessionLocal, engine
from app.halls import HALLS, Hall, campus_today
from app.models import Location, MenuItem, Schedule

FetchMenu = Callable[[Hall, dt.date], list[dict]]
# Downloads at once. Each takes ~1.7 s, so 21 of them one by one took ~35 s. Kept small to go easy on Sodexo.
PARALLEL_DOWNLOADS = 4
# MenuRow fields copied onto the MenuItem row each time a dish is seen
DISH_FIELDS = (
    "description", "is_vegan", "is_vegetarian", "is_plant_based", "is_mindful",
    "calories", "carbs_g", "protein_g", "fat_g", "portion",
)


@dataclass
class RefreshSummary:
    start: dt.date
    days: int
    servings: int = 0
    failed: list[str] = field(default_factory=list)


def init_db(bind: Engine) -> None:
    """Create any missing tables and make sure every hall has a row in `locations`."""
    Base.metadata.create_all(bind)
    with Session(bind) as db:
        for hall in HALLS.values():
            location = db.scalar(select(Location).where(Location.slug == hall.slug))
            if location is None:
                location = Location(slug=hall.slug)
                db.add(location)
            location.name = hall.name
            location.sodexo_location_id = hall.sodexo_location_id
            location.sodexo_menu_id = hall.sodexo_menu_id
        db.commit()


def refresh_menus(
    db: Session,
    start: dt.date,
    days: int = 7,
    fetch: FetchMenu = sodexo.fetch_menu,
) -> RefreshSummary:
    """Download `days` days of menus for every hall, replacing what's stored for those days.

    A hall/day that fails to download keeps its old rows, so one bad request
    doesn't wipe out data. `fetch` is swappable so tests can run without the network.
    """
    summary = RefreshSummary(start=start, days=days)
    items = {item.name: item for item in db.scalars(select(MenuItem))}
    locations = {location.slug: location for location in db.scalars(select(Location))}
    jobs = [(hall, start + dt.timedelta(days=offset)) for hall in HALLS.values() for offset in range(days)]

    def download(job: tuple[Hall, dt.date]) -> list[sodexo.MenuRow] | str:
        """Rows for one hall on one day, or an error message if the download failed."""
        hall, day = job
        try:
            return sodexo.flatten_menu(fetch(hall, day))
        except (httpx.HTTPError, ValueError) as error:
            return f"{hall.name} {day}: {error}"

    # Only the downloads run in parallel; all database writes happen below, one at a time.
    with ThreadPoolExecutor(max_workers=PARALLEL_DOWNLOADS) as pool:
        results = list(pool.map(download, jobs))

    for (hall, day), rows in zip(jobs, results):
        if isinstance(rows, str):
            summary.failed.append(rows)
            continue

        location = locations[hall.slug]
        db.execute(delete(Schedule).where(Schedule.location_id == location.id, Schedule.date == day))
        for row in rows:
            item = items.get(row.name)
            if item is None:
                item = items[row.name] = MenuItem(name=row.name)
            for name in DISH_FIELDS:
                setattr(item, name, getattr(row, name))

            start_time, end_time = hall.hours_for(day, row.meal) or (None, None)
            db.add(Schedule(
                menu_item=item,
                location=location,
                date=day,
                meal=row.meal,
                station=row.station,
                start_time=start_time,
                end_time=end_time,
            ))
            summary.servings += 1

    db.commit()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Download upcoming UC dining menus into the database.")
    parser.add_argument("--days", type=int, default=7, help="how many days to download (default 7)")
    parser.add_argument(
        "--reset", action="store_true",
        help="drop and recreate every table first, which also deletes all favorites",
    )
    args = parser.parse_args()

    print(f"Database: {engine.url.render_as_string(hide_password=True)}")
    if args.reset:
        Base.metadata.drop_all(engine)
        print("Dropped all tables.")
    init_db(engine)
    with SessionLocal() as db:
        summary = refresh_menus(db, start=campus_today(), days=args.days)
    print(f"Saved {summary.servings} servings for {summary.days} days starting {summary.start}.")
    for failure in summary.failed:
        print(f"  failed: {failure}")


if __name__ == "__main__":
    main()
