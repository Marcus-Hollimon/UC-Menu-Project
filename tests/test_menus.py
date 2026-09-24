"""Listing halls, searching dishes, browsing menus by diet, and the web page.

Requirements: N5 (menus by hall, meal and diet, with nutrition), D3 (nutrition and diet labels exposed), P3 (web page).
"""
from app.ingest import refresh_menus
from tests.conftest import MENU_DAY, fake_fetch


def test_list_locations(client):
    halls = client.get("/locations").json()

    assert [h["name"] for h in halls] == ["Center Court", "MarketPointe", "On The Green"]


# --- Searching dishes ---

def test_search_finds_dishes_across_halls(client, menus):
    response = client.get("/menu-items", params={"q": "PIZZA"})

    assert response.status_code == 200
    assert [d["name"] for d in response.json()] == [
        "Cheese Pizza", "Feta Bruschetta Pizza", "Lasagna Pizza", "Pepperoni Pizza", "Roasted Vegetable Pizza",
    ]


def test_search_can_be_limited_to_one_hall(client, menus):
    response = client.get("/menu-items", params={"q": "pizza", "hall": "marketpointe"})

    assert [d["name"] for d in response.json()] == ["Cheese Pizza", "Pepperoni Pizza"]


def test_search_can_be_limited_to_a_diet(client, menus):
    response = client.get("/menu-items", params={"q": "pizza", "diet": "vegetarian"})

    # Cheese Pizza is missing: Sodexo doesn't label it vegetarian. The filter trusts Sodexo's labels.
    assert [d["name"] for d in response.json()] == ["Feta Bruschetta Pizza", "Roasted Vegetable Pizza"]


def test_search_results_include_nutrition(client, menus):
    cheese_pizza = client.get("/menu-items", params={"q": "cheese pizza"}).json()[0]

    assert cheese_pizza["diets"] == []
    assert (cheese_pizza["calories"], cheese_pizza["carbs_g"], cheese_pizza["protein_g"], cheese_pizza["fat_g"]) == (
        219, 28, 10, 7)
    assert cheese_pizza["portion"] == "SLC=1/8"


def test_search_treats_wildcard_characters_literally(client, menus):
    assert client.get("/menu-items", params={"q": "%%"}).json() == []


def test_search_rejects_unknown_hall(client):
    assert client.get("/menu-items", params={"q": "pizza", "hall": "siddall"}).status_code == 422


# --- Browsing menus ---

def test_browse_one_meal_at_one_hall(client, menus):
    response = client.get("/menus", params={"day": "2026-09-22", "hall": "center-court", "meal": "dinner"})

    servings = response.json()
    assert [s["dish"] for s in servings] == ["Cheese Pizza", "Roasted General Tso Cauliflower"]
    assert {(s["start_time"], s["end_time"]) for s in servings} == {("16:30:00", "20:00:00")}


def test_browse_by_diet(client, menus):
    servings = client.get("/menus", params={"day": "2026-09-22", "diet": "vegan"}).json()

    assert [(s["hall"], s["meal"], s["dish"], s["diets"]) for s in servings] == [
        ("MarketPointe", "Dinner", "Sofrito Black Beans", ["vegetarian", "vegan", "plant-based", "mindful"]),
    ]


def test_servings_include_nutrition(client, menus):
    servings = client.get("/menus", params={"day": "2026-09-22", "hall": "marketpointe", "meal": "breakfast"}).json()

    yogurt = servings[0]
    assert yogurt["dish"] == "Low Fat Strawberry Yogurt"
    assert (yogurt["calories"], yogurt["carbs_g"], yogurt["protein_g"], yogurt["fat_g"], yogurt["portion"]) == (
        18, 1, 1, 1, "OZ")


def test_browse_rejects_unknown_diet(client):
    assert client.get("/menus", params={"diet": "keto"}).status_code == 422
    assert client.get("/menu-items", params={"q": "pizza", "diet": "keto"}).status_code == 422


def test_menus_can_search_several_days_by_keyword(client, db):
    refresh_menus(db, start=MENU_DAY, days=2, fetch=fake_fetch)

    servings = client.get("/menus", params={"day": "2026-09-22", "days": 2, "q": "salmon"}).json()

    assert [(s["date"], s["hall"], s["meal"]) for s in servings] == [
        ("2026-09-22", "MarketPointe", "Dinner"),
        ("2026-09-23", "MarketPointe", "Dinner"),
    ]


def test_menus_limits_how_many_days(client):
    assert client.get("/menus", params={"days": 15}).status_code == 422


# --- Web page ---

def test_web_page_is_served_at_root(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "UC Dining" in response.text
