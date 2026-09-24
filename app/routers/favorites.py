import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.halls import campus_today
from app.models import Location, Schedule, UserFavorite, matches_keyword, select_servings
from app.schemas import CalendarEntry, FavoriteIn, FavoriteOut

router = APIRouter(prefix="/favorites", tags=["favorites"])


def get_or_404(db: Session, favorite_id: int) -> UserFavorite:
    favorite = db.get(UserFavorite, favorite_id)
    if favorite is None:
        raise HTTPException(status_code=404, detail=f"Favorite {favorite_id} not found")
    return favorite


def reject_duplicate(db: Session, keyword: str, ignore_id: int | None = None) -> None:
    """409 if another favorite already has this keyword (ignoring case)."""
    query = select(UserFavorite.id).where(func.lower(UserFavorite.keyword) == keyword.lower())
    if ignore_id is not None:
        query = query.where(UserFavorite.id != ignore_id)
    if db.scalar(query) is not None:
        raise HTTPException(status_code=409, detail=f"'{keyword}' is already a favorite")


@router.post("", response_model=FavoriteOut, status_code=201)
def create_favorite(favorite: FavoriteIn, db: Session = Depends(get_db)):
    """Add a keyword to your watchlist."""
    reject_duplicate(db, favorite.keyword)
    row = UserFavorite(**favorite.model_dump(mode="json"))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=list[FavoriteOut])
def list_favorites(db: Session = Depends(get_db)):
    """Everything on your watchlist."""
    return db.scalars(select(UserFavorite).order_by(UserFavorite.id)).all()


# Declared before /{favorite_id} so "calendar" isn't read as a favorite ID.
@router.get("/calendar", response_model=list[CalendarEntry])
def favorites_calendar(
    start: dt.date | None = Query(None, description="First day to include. Defaults to today."),
    days: int = Query(7, ge=1, le=14),
    db: Session = Depends(get_db),
):
    """Where and when your favorites are served: date, hall, meal and hours."""
    first = start or campus_today()
    last = first + dt.timedelta(days=days - 1)

    entries = []
    for favorite in db.scalars(select(UserFavorite).order_by(UserFavorite.id)):
        query = select_servings().where(
            Schedule.date.between(first, last),
            matches_keyword(favorite.keyword),
        )
        if favorite.halls:
            query = query.where(Location.slug.in_(favorite.halls))
        entries += [
            CalendarEntry.from_schedule(schedule, favorite_id=favorite.id, keyword=favorite.keyword)
            for schedule in db.scalars(query)
        ]

    entries.sort(key=lambda e: (e.date, e.start_time or dt.time.min, e.hall, e.dish))
    return entries


@router.get("/{favorite_id}", response_model=FavoriteOut)
def get_favorite(favorite_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, favorite_id)


@router.put("/{favorite_id}", response_model=FavoriteOut)
def update_favorite(favorite_id: int, changes: FavoriteIn, db: Session = Depends(get_db)):
    """Replace a favorite's keyword, halls and notes."""
    row = get_or_404(db, favorite_id)
    reject_duplicate(db, changes.keyword, ignore_id=favorite_id)
    for field, value in changes.model_dump(mode="json").items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{favorite_id}", status_code=204)
def delete_favorite(favorite_id: int, db: Session = Depends(get_db)):
    """Remove a favorite so it stops appearing in the calendar."""
    db.delete(get_or_404(db, favorite_id))
    db.commit()
