"""Create, read, update and delete favorites, plus the favorites calendar.

Requirements: N1 (create), N2 (upcoming occurrences), N3 (edit), N4 (delete), D2 (keyword matching).
"""
import pytest


def add_favorite(client, keyword="pizza", **fields):
    response = client.post("/favorites", json={"keyword": keyword, **fields})
    assert response.status_code == 201, response.text
    return response.json()


# --- Create ---

def test_create_favorite(client):
    response = client.post(
        "/favorites",
        json={"keyword": "  General   Tso ", "halls": ["center-court"], "notes": "try at lunch"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["keyword"] == "General Tso"
    assert body["halls"] == ["center-court"]
    assert body["notes"] == "try at lunch"
    assert isinstance(body["id"], int)


def test_create_defaults_to_all_halls(client):
    assert add_favorite(client)["halls"] == []


@pytest.mark.parametrize("body", [
    {"keyword": ""},
    {"keyword": "   x   "},
    {"halls": ["center-court"]},
    {"keyword": "pizza", "halls": ["siddall-hall"]},
])
def test_create_rejects_invalid_input(client, body):
    assert client.post("/favorites", json=body).status_code == 422


def test_create_rejects_duplicate_keyword_ignoring_case(client):
    add_favorite(client, "Pizza")

    assert client.post("/favorites", json={"keyword": "PIZZA"}).status_code == 409


# --- Read ---

def test_list_favorites(client):
    add_favorite(client, "pizza")
    add_favorite(client, "salmon")

    keywords = [f["keyword"] for f in client.get("/favorites").json()]
    assert keywords == ["pizza", "salmon"]


def test_get_favorite(client):
    favorite = add_favorite(client)

    response = client.get(f"/favorites/{favorite['id']}")
    assert response.status_code == 200
    assert response.json() == favorite


def test_get_missing_favorite_returns_404(client):
    assert client.get("/favorites/999").status_code == 404


# --- Update ---

def test_update_favorite_replaces_fields(client):
    favorite = add_favorite(client, "pizza")

    response = client.put(
        f"/favorites/{favorite['id']}",
        json={"keyword": "cheese pizza", "halls": ["marketpointe"], "notes": "dinner only"},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["keyword"], body["halls"], body["notes"]) == ("cheese pizza", ["marketpointe"], "dinner only")
    assert client.get(f"/favorites/{favorite['id']}").json() == body


def test_update_missing_favorite_returns_404(client):
    assert client.put("/favorites/999", json={"keyword": "pizza"}).status_code == 404


def test_update_to_another_favorites_keyword_returns_409(client):
    add_favorite(client, "pizza")
    salmon = add_favorite(client, "salmon")

    assert client.put(f"/favorites/{salmon['id']}", json={"keyword": "Pizza"}).status_code == 409


def test_update_can_keep_its_own_keyword(client):
    favorite = add_favorite(client, "pizza")

    response = client.put(f"/favorites/{favorite['id']}", json={"keyword": "pizza", "notes": "new note"})
    assert response.status_code == 200


# --- Delete ---

def test_delete_favorite(client):
    favorite = add_favorite(client)

    assert client.delete(f"/favorites/{favorite['id']}").status_code == 204
    assert client.get(f"/favorites/{favorite['id']}").status_code == 404
    assert client.get("/favorites").json() == []


def test_delete_missing_favorite_returns_404(client):
    assert client.delete("/favorites/999").status_code == 404


# --- Calendar: where and when favorites are served ---

def get_calendar(client):
    response = client.get("/favorites/calendar", params={"start": "2026-09-22"})
    assert response.status_code == 200
    return response.json()


def test_calendar_shows_hall_date_meal_and_hours(client, menus):
    add_favorite(client, "general tso")

    entries = get_calendar(client)

    assert [(e["hall"], e["date"], e["meal"], e["start_time"], e["end_time"]) for e in entries] == [
        ("Center Court", "2026-09-22", "Lunch", "10:30:00", "16:30:00"),
        ("Center Court", "2026-09-22", "Dinner", "16:30:00", "20:00:00"),
    ]
    assert entries[0]["dish"] == "Roasted General Tso Cauliflower"
    assert entries[0]["keyword"] == "general tso"


def test_calendar_entries_include_nutrition(client, menus):
    add_favorite(client, "salmon")

    entry = get_calendar(client)[0]
    assert (entry["dish"], entry["calories"], entry["protein_g"]) == ("Salmon, Barley and Lentil Salad", 422, 31)


def test_calendar_keyword_matches_all_words_in_any_order(client, menus):
    add_favorite(client, "pizza cheese")

    dishes = {e["dish"] for e in get_calendar(client)}
    assert dishes == {"Cheese Pizza"}


def test_calendar_only_uses_chosen_halls(client, menus):
    add_favorite(client, "cheese pizza", halls=["on-the-green"])

    entries = get_calendar(client)
    assert [(e["hall"], e["meal"]) for e in entries] == [("On The Green", "Lunch")]


def test_calendar_is_empty_after_favorite_is_deleted(client, menus):
    favorite = add_favorite(client, "salmon")
    assert len(get_calendar(client)) == 1

    client.delete(f"/favorites/{favorite['id']}")
    assert get_calendar(client) == []


def test_calendar_ignores_days_outside_the_window(client, menus):
    add_favorite(client, "pizza")

    response = client.get("/favorites/calendar", params={"start": "2026-09-23", "days": 7})
    assert response.json() == []
