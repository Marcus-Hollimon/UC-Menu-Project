import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.halls import HallSlug, campus_today
from app.ingest import RefreshSummary, refresh_menus
from app.models import Allergen, Diet, Location, MenuItem, Schedule, has_diet, matches_keyword, select_servings
from app.schemas import AllergenCoverage, MenuItemOut, Serving
from app.sodexo import MissingApiKey

router = APIRouter(tags=["menus"])

# A hall-day's allergen data counts as incomplete when fewer than this share of its dishes list any allergen.
# 2026-09-22 had 6% (17 of 20 pizzas listed nothing); 2026-10-08 had 50% (every pizza listed gluten).
MIN_ALLERGEN_COVERAGE = 0.25


def date_range(day: dt.date | None, days: int):
    """SQL condition: served from `day` (default today) through the following `days - 1` days."""
    first = day or campus_today()
    return Schedule.date.between(first, first + dt.timedelta(days=days - 1))


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
    exclude_allergen: list[Allergen] = Query(
        [], description="Hide dishes that list any of these allergens (repeatable). Dishes listing none are kept."
    ),
    db: Session = Depends(get_db),
):
    """What's served on a day (or several), optionally narrowed by hall, meal, diet, listed allergens or keyword."""
    query = select_servings().where(date_range(day, days))
    if hall:
        query = query.where(Location.slug == hall)
    if meal:
        query = query.where(func.lower(Schedule.meal) == meal.strip().lower())
    if diet:
        query = query.where(has_diet(diet))
    if q:
        query = query.where(matches_keyword(q))
    query = query.order_by(Schedule.date, Location.name, Schedule.start_time, Schedule.station, MenuItem.name)
    servings = [Serving.from_schedule(schedule) for schedule in db.scalars(query)]
    if exclude_allergen:
        hidden = {allergen.value for allergen in exclude_allergen}
        servings = [serving for serving in servings if not hidden & set(serving.allergens)]
    return servings


@router.get("/menus/allergen-coverage", response_model=list[AllergenCoverage])
def allergen_coverage(
    day: dt.date | None = Query(None, description="First day to include. Defaults to today."),
    days: int = Query(1, ge=1, le=14),
    db: Session = Depends(get_db),
):
    """How complete Sodexo's allergen data looks for each hall and day.

    Sodexo's allergen lists come and go (6% of dishes listed any on 2026-09-22, 50% on 2026-10-08),
    so a hall-day where few dishes list allergens is flagged and the page warns before filtering on it.
    """
    query = select_servings().where(date_range(day, days)).order_by(Schedule.date, Location.name)
    counts: dict[tuple[dt.date, str], AllergenCoverage] = {}
    for schedule in db.scalars(query):
        key = (schedule.date, schedule.location.slug)
        if key not in counts:
            counts[key] = AllergenCoverage(
                hall=schedule.location.name, hall_slug=schedule.location.slug, date=schedule.date,
                dishes=0, dishes_listing_allergens=0, incomplete=False,
            )
        counts[key].dishes += 1
        counts[key].dishes_listing_allergens += bool(schedule.menu_item.allergens)
    for coverage in counts.values():
        coverage.incomplete = coverage.dishes_listing_allergens < MIN_ALLERGEN_COVERAGE * coverage.dishes
    return list(counts.values())


@router.post("/menus/refresh", response_model=RefreshSummary)
def refresh(days: int = Query(7, ge=1, le=14), db: Session = Depends(get_db)):
    """Download the next `days` days of menus from Sodexo. Takes several seconds."""
    try:
        return refresh_menus(db, start=campus_today(), days=days)
    except MissingApiKey as error:
        raise HTTPException(status_code=503, detail=str(error))
