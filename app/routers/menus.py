import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.halls import HallSlug, campus_today
from app.ingest import RefreshSummary, refresh_menus
from app.models import Diet, Location, MenuItem, Schedule, has_diet, matches_keyword, select_servings
from app.schemas import MenuItemOut, Serving

router = APIRouter(tags=["menus"])


@router.get("/menu-items", response_model=list[MenuItemOut])
def search_menu_items(
    q: str = Query(min_length=2, description="Words to look for in dish names, e.g. 'pizza'"),
    hall: HallSlug | None = None,
    diet: Diet | None = None,
    db: Session = Depends(get_db),
):
    """Search dishes by name. Every word in `q` must appear; case doesn't matter."""
    query = select(MenuItem).where(matches_keyword(q)).order_by(MenuItem.name)
    if hall:
        query = query.where(MenuItem.schedules.any(Schedule.location.has(Location.slug == hall)))
    if diet:
        query = query.where(has_diet(diet))
    return db.scalars(query).all()


@router.get("/menus", response_model=list[Serving])
def browse_menu(
    day: dt.date | None = Query(None, description="First day to include. Defaults to today."),
    days: int = Query(1, ge=1, le=14, description="How many days to include, starting at `day`"),
    hall: HallSlug | None = None,
    meal: str | None = Query(None, examples=["Lunch"]),
    diet: Diet | None = Query(None, description="Only dishes Sodexo labels with this diet"),
    q: str | None = Query(None, min_length=2, description="Only dishes whose names contain every word"),
    db: Session = Depends(get_db),
):
    """What's served on a day (or several), optionally narrowed by hall, meal, diet or keyword."""
    first = day or campus_today()
    query = select_servings().where(Schedule.date.between(first, first + dt.timedelta(days=days - 1)))
    if hall:
        query = query.where(Location.slug == hall)
    if meal:
        query = query.where(func.lower(Schedule.meal) == meal.strip().lower())
    if diet:
        query = query.where(has_diet(diet))
    if q:
        query = query.where(matches_keyword(q))
    query = query.order_by(Schedule.date, Location.name, Schedule.start_time, Schedule.station, MenuItem.name)
    return [Serving.from_schedule(schedule) for schedule in db.scalars(query)]


@router.post("/menus/refresh", response_model=RefreshSummary)
def refresh(days: int = Query(7, ge=1, le=14), db: Session = Depends(get_db)):
    """Download the next `days` days of menus from Sodexo. Takes several seconds."""
    return refresh_menus(db, start=campus_today(), days=days)
