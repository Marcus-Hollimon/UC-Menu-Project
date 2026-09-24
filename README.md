# UC Dining Favorites

See what every University of Cincinnati dining hall (Center Court, MarketPointe, On The Green) is serving, filter by diet, check nutrition, and save favorite dishes to see which hall serves them, on which day, and at what time.

It runs on your own computer. Menus come from the same Sodexo API the UC Dining website uses.

The web page has three tabs:
- **Menus:** one meal at every hall side by side for any of the next 7 days, with diet labels (vegan, vegetarian, plant-based, mindful) and calories, carbs, protein, fat and portion size. ☆ saves a dish as a favorite.
- **Find a dish:** search the next 7 days for a keyword like "pancake" or "tofu", see where and when each match is served, and save the keyword as a favorite for chosen halls.
- **My favorites:** edit or delete favorites and see this week's matches, day by day.

## Run it

**1. Install Python 3.11 or newer** from https://www.python.org/downloads/. On Windows, tick **"Add python.exe to PATH"** on the installer's first screen. If typing `python` in a terminal opens the Microsoft Store, Python isn't installed yet.

**2. Get the code.** With Git: `git clone https://github.com/Marcus-Hollimon/UC-Menu-Project.git`. Without Git: on the GitHub page, click **Code → Download ZIP** and unzip it.

**3. Open a terminal in the project folder** (the one containing `README.md`) and run:

Windows (PowerShell):

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m app.ingest
.venv\Scripts\python.exe -m uvicorn app.main:app
```

macOS / Linux:

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m app.ingest
.venv/bin/python -m uvicorn app.main:app
```

**4. Open http://127.0.0.1:8000.** The app runs until you press Ctrl+C in the terminal. Next time, only the last command is needed.

The first three commands run once: create a private Python environment in `.venv`, install the libraries into it, and download the next 7 days of menus into a local SQLite file, `uc_menu.db`. Menus change daily. Use the **Refresh menus** button on the page to fetch new ones. Sodexo posts menus only a few days ahead, so later days may be empty. If the download reports failures, Sodexo was slow to answer; refresh again later.

These commands call `.venv`'s Python directly instead of "activating" the environment, because Windows often blocks the activate script ("running scripts is disabled on this system").

**Keep it on your own computer.** The app has no accounts or passwords, so it only accepts connections from the computer it runs on. Don't start it with `--host 0.0.0.0` (for example, to open it on your phone), especially on campus Wi-Fi. Anyone on the same network could then read and change your favorites, or make your computer send repeated requests to Sodexo. As a backstop, the app refuses any request not addressed to `127.0.0.1` or `localhost` ("Invalid host header").

If you pull a version that changes the database tables, rebuild them with `.venv\Scripts\python.exe -m app.ingest --reset` (macOS/Linux: `.venv/bin/python -m app.ingest --reset`). This also deletes your favorites.

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
.venv\Scripts\python.exe -m pytest
```

(macOS/Linux: `.venv/bin/python -m pytest`.) Tests use an in-memory database and saved menus in `tests/fixtures/`, so they don't need the internet.

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
