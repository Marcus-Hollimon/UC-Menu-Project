"""Download menus from Sodexo's menu API and flatten them into simple rows.

The API returns a list of meals, each with stations ("groups"), each with dishes:

    [{"name": "Lunch", "groups": [{"name": "Slices", "items": [{"formalName": "Cheese Pizza", ...}]}]}]

It has no meal times; those come from app.halls.
"""
import datetime as dt
import html
import re
from dataclasses import dataclass

import httpx

from app.halls import Hall

API_URL = "https://api-prd.sodexomyway.net/v0.2/data/menu/{location_id}/{menu_id}"
# The public key the UC Dining website itself sends with every menu request.
HEADERS = {
    "Api-Key": "REMOVED-SODEXO-API-KEY",
    "Origin": "https://ucdining.sodexomyway.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
}
# Sodexo lists placeholder "dishes" such as "Have a Nice Day" with this ingredient text.
NON_FOOD_INGREDIENTS = {"Plate Cost Peripherals"}


@dataclass
class MenuRow:
    meal: str
    station: str
    name: str
    description: str
    is_vegan: bool
    is_vegetarian: bool
    is_plant_based: bool
    is_mindful: bool
    # Per portion; None when Sodexo leaves the field blank.
    calories: int | None
    carbs_g: int | None
    protein_g: int | None
    fat_g: int | None
    portion: str  # free text such as "3 OZ" or "SLC=1/8"


def fetch_menu(hall: Hall, day: dt.date) -> list[dict]:
    """Raw menu JSON for one hall on one day. Raises httpx.HTTPError or ValueError on failure."""
    url = API_URL.format(location_id=hall.sodexo_location_id, menu_id=hall.sodexo_menu_id)
    response = httpx.get(url, params={"date": day.isoformat()}, headers=HEADERS, timeout=20)
    response.raise_for_status()
    meals = response.json()
    if not isinstance(meals, list):
        raise ValueError(f"expected a list of meals, got {type(meals).__name__}")
    return meals


def clean_text(text: str | None) -> str:
    """Decode HTML entities like &amp; and collapse repeated whitespace."""
    return " ".join(html.unescape(text or "").split())


def parse_amount(value: str | int | None) -> int | None:
    """Sodexo sends numbers as text, sometimes with units: "35g" -> 35, "523mg" -> 523, "" -> None."""
    match = re.match(r"\s*(\d+(?:\.\d+)?)", str(value if value is not None else ""))
    return round(float(match.group(1))) if match else None


def flatten_menu(meals: list[dict]) -> list[MenuRow]:
    """Turn the nested meals -> stations -> dishes JSON into one row per dish."""
    rows = []
    for meal in meals:
        for station in meal.get("groups", []):
            for item in station.get("items", []):
                name = clean_text(item.get("formalName"))
                if not name or item.get("ingredients") in NON_FOOD_INGREDIENTS:
                    continue
                rows.append(MenuRow(
                    meal=clean_text(meal.get("name")),
                    station=clean_text(station.get("name")),
                    name=name,
                    description=clean_text(item.get("description")),
                    is_vegan=bool(item.get("isVegan")),
                    is_vegetarian=bool(item.get("isVegetarian")),
                    is_plant_based=bool(item.get("isPlantBased")),
                    is_mindful=bool(item.get("isMindful")),
                    calories=parse_amount(item.get("calories")),
                    carbs_g=parse_amount(item.get("carbohydrates")),
                    protein_g=parse_amount(item.get("protein")),
                    fat_g=parse_amount(item.get("fat")),
                    portion=clean_text(item.get("portion")),
                ))
    return rows
