"""Database tables, plus the query helpers shared by the routers."""
import datetime as dt
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, Select, and_, false, func, select
from sqlalchemy.orm import Mapped, contains_eager, mapped_column, relationship

from app.database import Base


class Location(Base):
    """A dining hall."""
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    sodexo_location_id: Mapped[str]
    sodexo_menu_id: Mapped[str]


class Diet(StrEnum):
    """Diet labels Sodexo puts on dishes."""
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    PLANT_BASED = "plant-based"
    MINDFUL = "mindful"  # Sodexo's label for lighter, balanced dishes


# Which MenuItem column holds each label
DIET_FIELDS = {
    Diet.VEGETARIAN: "is_vegetarian",
    Diet.VEGAN: "is_vegan",
    Diet.PLANT_BASED: "is_plant_based",
    Diet.MINDFUL: "is_mindful",
}


class MenuItem(Base):
    """A dish, stored once no matter how often it is served."""
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str] = mapped_column(default="")
    is_vegan: Mapped[bool] = mapped_column(default=False)
    is_vegetarian: Mapped[bool] = mapped_column(default=False)
    is_plant_based: Mapped[bool] = mapped_column(default=False)
    is_mindful: Mapped[bool] = mapped_column(default=False)
    # Per portion, as Sodexo lists them; None when Sodexo leaves the field blank.
    calories: Mapped[int | None]
    carbs_g: Mapped[int | None]
    protein_g: Mapped[int | None]
    fat_g: Mapped[int | None]
    portion: Mapped[str] = mapped_column(default="")

    schedules: Mapped[list["Schedule"]] = relationship(back_populates="menu_item")

    @property
    def diets(self) -> list[str]:
        """The diet labels this dish has, e.g. ["vegetarian", "vegan"]."""
        return [diet.value for diet, field in DIET_FIELDS.items() if getattr(self, field)]


class Schedule(Base):
    """One dish served at one hall, on one date, during one meal."""
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    date: Mapped[dt.date] = mapped_column(index=True)
    meal: Mapped[str]
    station: Mapped[str]
    start_time: Mapped[dt.time | None]
    end_time: Mapped[dt.time | None]

    menu_item: Mapped[MenuItem] = relationship(back_populates="schedules")
    location: Mapped[Location] = relationship()


class UserFavorite(Base):
    """A keyword on the watchlist, such as "pizza" or "general tso"."""
    __tablename__ = "user_favorites"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str]
    # Hall slugs to limit matches to; an empty list means every hall.
    halls: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(default="")
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


def matches_keyword(keyword: str):
    """SQL condition: the dish name contains every word of `keyword`, ignoring case.

    "pizza cheese" matches "Cheese Pizza"; autoescape keeps % and _ from acting as wildcards.
    """
    words = keyword.split()
    if not words:
        return false()
    return and_(*(MenuItem.name.icontains(word, autoescape=True) for word in words))


def has_diet(diet: Diet):
    """SQL condition: Sodexo labels the dish with `diet`."""
    return getattr(MenuItem, DIET_FIELDS[diet])


def select_servings() -> Select[tuple[Schedule]]:
    """Schedules joined to their dish and hall, loaded in the same query."""
    return (
        select(Schedule)
        .join(Schedule.menu_item)
        .join(Schedule.location)
        .options(contains_eager(Schedule.menu_item), contains_eager(Schedule.location))
    )
