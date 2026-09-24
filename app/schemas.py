"""Request and response shapes. Pydantic validates incoming JSON against these."""
import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.halls import HallSlug
from app.models import Schedule


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str


class DishFacts(BaseModel):
    """Diet labels and per-portion nutrition, as Sodexo lists them. Blank values are null."""
    model_config = ConfigDict(from_attributes=True)

    diets: list[str] = Field(examples=[["vegetarian", "vegan", "plant-based"]])
    calories: int | None
    carbs_g: int | None
    protein_g: int | None
    fat_g: int | None
    portion: str = Field(examples=["3 OZ"])


class MenuItemOut(DishFacts):
    id: int
    name: str
    description: str


class Serving(DishFacts):
    """A dish served at a hall during one meal on one date."""
    dish: str
    hall: str
    hall_slug: str
    date: dt.date
    meal: str
    start_time: dt.time | None
    end_time: dt.time | None
    station: str

    @classmethod
    def from_schedule(cls, schedule: Schedule, **extra):
        facts = DishFacts.model_validate(schedule.menu_item).model_dump()
        return cls(
            dish=schedule.menu_item.name,
            hall=schedule.location.name,
            hall_slug=schedule.location.slug,
            date=schedule.date,
            meal=schedule.meal,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            station=schedule.station,
            **facts,
            **extra,
        )


class CalendarEntry(Serving):
    """A serving that matched one of your favorites."""
    favorite_id: int
    keyword: str


class FavoriteIn(BaseModel):
    keyword: str = Field(min_length=2, max_length=100, examples=["pizza"])
    halls: list[HallSlug] = Field(
        default_factory=list,
        description="Only match at these halls. Leave empty for all halls.",
    )
    notes: str = Field(default="", max_length=500)

    @field_validator("keyword", mode="before")
    @classmethod
    def tidy_keyword(cls, value):
        # "  General   Tso " -> "General Tso", before the length check runs
        return " ".join(value.split()) if isinstance(value, str) else value

    @field_validator("halls")
    @classmethod
    def drop_repeated_halls(cls, value):
        return list(dict.fromkeys(value))


class FavoriteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keyword: str
    halls: list[str]
    notes: str
    created_at: dt.datetime
