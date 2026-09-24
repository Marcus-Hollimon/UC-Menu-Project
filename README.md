# UC Dining Favorites

See what every University of Cincinnati dining hall (Center Court, MarketPointe, On The Green) is serving, filter by diet, check nutrition, and save favorite dishes to see which hall serves them, on which day, and at what time.

It runs on your own computer. Menus come from the same Sodexo API the UC Dining website uses.

The web page has three tabs:
- **Menus:** one meal at every hall side by side for any of the next 7 days, with diet labels (vegan, vegetarian, plant-based, mindful) and calories, carbs, protein, fat and portion size. ☆ saves a dish as a favorite.
- **Find a dish:** search the next 7 days for a keyword like "pancake" or "tofu", see where and when each match is served, and save the keyword as a favorite for chosen halls.
- **My favorites:** edit or delete favorites and see this week's matches, day by day.

## Run it

You need Python 3.11 or newer and an internet connection for downloading menus.

**Windows (PowerShell):**

```
git clone https://github.com/Marcus-Hollimon/UC-Menu-Project.git
cd UC-Menu-Project
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.ingest
uvicorn app.main:app
```

**macOS / Linux:**

```
git clone https://github.com/Marcus-Hollimon/UC-Menu-Project.git
cd UC-Menu-Project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.ingest
uvicorn app.main:app
```

Then open http://127.0.0.1:8000. Stop the app with Ctrl+C. Next time, just activate `.venv` and run `uvicorn app.main:app`.

`python -m app.ingest` downloads the next 7 days of menus into a local SQLite file, `uc_menu.db`. Menus change daily. Use the **Refresh menus** button on the page, or run `python -m app.ingest` again, to fetch new ones. Sodexo posts menus only a few days ahead, so later days may be empty.

If you pull a version that changes the database tables, rebuild them with `python -m app.ingest --reset`. This also deletes your favorites.

## API

The page is built on a JSON API. Try every endpoint at http://127.0.0.1:8000/docs.

| Method | Path | What it does |
|---|---|---|
| GET | `/locations` | List the dining halls |
| GET | `/menu-items?q=pizza&hall=marketpointe&diet=vegetarian` | Search dishes by name |
| GET | `/menus?day=2026-09-24&hall=center-court&meal=Lunch&diet=vegan` | One day's menu, with nutrition |
| GET | `/menus?q=pancake&days=7` | Where and when dishes matching a keyword are served |
| POST | `/menus/refresh?days=7` | Download fresh menus from Sodexo |
| POST | `/favorites` | Add a favorite: `{"keyword": "pizza", "halls": [], "notes": ""}` |
| GET | `/favorites` | List favorites |
| GET | `/favorites/{id}` | Get one favorite |
| PUT | `/favorites/{id}` | Replace a favorite's keyword, halls and notes |
| DELETE | `/favorites/{id}` | Remove a favorite |
| GET | `/favorites/calendar?days=7` | Where and when your favorites are served |

A keyword matches a dish when every word in it appears in the dish name, ignoring case. `halls` limits matches to those halls; an empty list means all halls. `diet` is one of `vegetarian`, `vegan`, `plant-based`, `mindful`.

## Tests

```
python -m pytest
```

Tests use an in-memory database and saved menus in `tests/fixtures/`, so they don't need the internet.

## Project layout

```
PROJECT_SPEC.md  requirements, design and plan (the source of truth)
app/
  main.py          FastAPI app; serves the page at /
  static/index.html  the web page (plain HTML, CSS and JavaScript)
  halls.py         hall IDs and meal hours
  sodexo.py        download menus and flatten the JSON
  ingest.py        load menus into the database (python -m app.ingest)
  database.py      database connection (SQLite by default)
  models.py        tables: locations, menu_items, schedules, user_favorites
  schemas.py       request/response shapes
  routers/         endpoints: locations, menus, favorites
tests/             pytest suite and fixture menus
```

## Known limitations

- Menus show what's planned. Dishes can run out or change.
- Diet labels and nutrition come straight from Sodexo, and labels are sometimes missing. Don't use this app for allergies.
- Meal times are each hall's regular hours (copied from the UC Dining site on 2026-09-22). Breaks and holidays aren't handled.
- Matching is substring-based, so "ham" also matches "Graham Cracker".
- Only the three residential halls publish menus. Retail locations (Stadium View, Chick-fil-A, and others) don't.
- Each copy of the app has its own favorites; they don't sync between computers.

## Optional: Postgres

The app can use Postgres instead of SQLite. Copy `.env.example` to `.env` and set `DATABASE_URL` to a Postgres connection string. `.env` is git-ignored so the password never gets committed. This was set up for hosting, which is on hold (see `PROJECT_SPEC.md` section 6.6).
