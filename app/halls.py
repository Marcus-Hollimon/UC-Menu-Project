"""The three UC residential dining halls: Sodexo IDs and regular meal hours.

IDs and hours were copied from each hall's page on ucdining.sodexomyway.com
on 2026-09-22. Holiday and break hours are not included.
"""
import datetime as dt
from dataclasses import dataclass
from enum import StrEnum
from zoneinfo import ZoneInfo

CAMPUS_TZ = ZoneInfo("America/New_York")


class HallSlug(StrEnum):
    CENTER_COURT = "center-court"
    MARKETPOINTE = "marketpointe"
    ON_THE_GREEN = "on-the-green"


# Meal name (as the menu API spells it) -> (start, end)
MealHours = dict[str, tuple[dt.time, dt.time]]


@dataclass(frozen=True)
class Hall:
    slug: HallSlug
    name: str
    sodexo_location_id: str
    sodexo_menu_id: str
    weekday_hours: MealHours  # Monday-Friday
    weekend_hours: MealHours  # Saturday-Sunday

    def hours_for(self, day: dt.date, meal: str) -> tuple[dt.time, dt.time] | None:
        """Start and end time of `meal` at this hall on `day`, or None if not listed."""
        hours = self.weekday_hours if day.weekday() < 5 else self.weekend_hours
        return hours.get(meal)


def _hours(start: str, end: str) -> tuple[dt.time, dt.time]:
    return dt.time.fromisoformat(start), dt.time.fromisoformat(end)


_WEEKDAY_THREE_MEALS: MealHours = {
    "Breakfast": _hours("07:00", "10:30"),
    "Lunch": _hours("10:30", "16:30"),
    "Dinner": _hours("16:30", "20:00"),
}
_WEEKEND_TWO_MEALS: MealHours = {
    "Brunch": _hours("09:00", "16:30"),
    "Dinner": _hours("16:30", "20:00"),
}

HALLS: dict[HallSlug, Hall] = {
    HallSlug.CENTER_COURT: Hall(
        slug=HallSlug.CENTER_COURT,
        name="Center Court",
        sodexo_location_id="38364002",
        sodexo_menu_id="150665",
        weekday_hours={
            "Lunch": _hours("10:30", "16:30"),
            "Dinner": _hours("16:30", "20:00"),
            "Late Night": _hours("20:00", "22:00"),
        },
        weekend_hours={},  # closed on weekends
    ),
    HallSlug.MARKETPOINTE: Hall(
        slug=HallSlug.MARKETPOINTE,
        name="MarketPointe",
        sodexo_location_id="38364003",
        sodexo_menu_id="158252",
        weekday_hours=_WEEKDAY_THREE_MEALS,
        weekend_hours=_WEEKEND_TWO_MEALS,
    ),
    HallSlug.ON_THE_GREEN: Hall(
        slug=HallSlug.ON_THE_GREEN,
        name="On The Green",
        sodexo_location_id="38364004",
        sodexo_menu_id="150721",
        weekday_hours=_WEEKDAY_THREE_MEALS,
        weekend_hours=_WEEKEND_TWO_MEALS,
    ),
}


def campus_today() -> dt.date:
    """Today's date in Cincinnati, even if the server runs in another time zone."""
    return dt.datetime.now(CAMPUS_TZ).date()
