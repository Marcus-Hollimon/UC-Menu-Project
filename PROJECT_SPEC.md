# Project Specification: UC Dining Menu Tracker

Last updated: 2026-09-24

This is the source of truth for what the app must do. Every requirement has an ID (N1, D2, P3, ...). Code and tests should point back to those IDs, and the status table in section 5 gets updated as work lands. If the code and this spec disagree, fix one of them on purpose instead of letting them drift.

**Change on 2026-09-24:** after two user interviews, the project became a local-first app that anyone can download from GitHub and run on their own computer. The calendar subscription feed (C1–C3), user accounts, and hosting were dropped or put on hold. Diet filters, nutrition, and a web page moved up. Section 2.1 has the evidence; section 9 lists the decisions.

---

## 1. Overview

A web app that runs on the student's own computer. It pulls menus for the University of Cincinnati dining halls (Center Court, MarketPointe, On The Green) from Sodexo's menu API. Students browse what every hall is serving, filter by diet, see nutrition per dish, save the dishes they care about, and see when and where those dishes are served in the coming week.

Terminology: a **watch entry** and a **favorite** are the same thing. In code they are `UserFavorite` rows in the `user_favorites` table, exposed at `/favorites`.

---

## 2. Target User Needs

1. **Need 1 (Predictability):** Students need to know ahead of time when specific favorite dishes (e.g., plant-based pancakes, General Tso's) are served so they do not miss them.
2. **Need 2 (Aggregated Visibility):** Students need one view that compares what every dining hall is serving for a meal, without checking each hall's page.
3. **Need 3 (Dietary & Nutrition):** Students need to narrow menus to dishes that fit their diet, and see what a dish is (calories, carbs, protein, portion) before they choose it.
4. **Need 4 (Schedule):** Students need a day-by-day view of the coming week showing when their favorites are served.
5. **Need 5 (Watchlist Control):** Students need to edit and remove saved items so the list stays relevant as their tastes change.

### 2.1 What the interviews found (2026-09-24)

Two students were asked five open questions (what they ate yesterday, what they look forward to, a time nothing looked good, show me your calendar, what I should have asked). Two interviews is a small sample, and one participant eats plant-based, so these findings steer priorities rather than prove anything.

| Finding | Evidence | What changed |
|---|---|---|
| Nobody uses a calendar for meals | Interviewee 1 skipped the calendar question; Interviewee 2: "Idk what to put." | Calendar subscription feed (C1–C3) dropped. The in-app week view covers "when." |
| Students move between halls | Interviewee 1 goes to a different hall when nothing looks good; Interviewee 2 ate at three halls in one day. | The web page opens on one meal at every hall side by side (Need 2). |
| Diet drives choices | Interviewee 2 ate plant-based at every meal. | Diet filter (N5) and diet labels move up. |
| Nutrition matters | Interviewee 1's question for me: "what type of food am I eating, like portion or carbs." | Calories, carbs, protein, fat, and portion added (D3). Sodexo already sends them. |
| Favorites help some students | Interviewee 2 looks forward to plant-based pancakes but doesn't know when they'll be served. Interviewee 1 doesn't look forward to anything specific. | Favorites stay, but the page leads with the menu, not the favorites list. |
| Food runs out | Interviewee 2 found no tofu scramble one morning and asked whether halls "actually have food available the entire time they're open." Scrambled Tofu is on On The Green's breakfast menu every weekday of the week checked. | Not solvable with menu data. The page says menus show what is planned. |
| Retail locations matter | Both ate lunch at Stadium View; one also ate at Cincy Grill. | Checked every UC Dining location (D5). None besides the three halls publishes a menu. |

---

## 3. User Stories (CRUD Operations)

* **Story 1 [CREATE]:** As a dining hall regular, I want to save a dish to my favorites, so that I can see when it appears on the upcoming schedule.
* **Story 2 [READ]:** As a busy student, I want a 7-day view of the days, halls, and meal times when my favorites are served, so that I can plan where to eat around my classes.
* **Story 3 [READ]:** As an on-campus resident, I want to see one meal at every hall, filtered by my diet and showing nutrition, so that I can pick where to go and what to eat.
* **Story 4 [UPDATE]:** As a student with changing preferences, I want to edit a favorite's keyword, halls, and notes, so that I only see schedules relevant to my routine.
* **Story 5 [DELETE]:** As a student, I want to remove a favorite, so that it stops appearing in my week view.

---

## 4. Requirements

### 4.1 Core CRUD

**N1.** Application must let a user create a watch entry for a named menu item at one or more dining locations.
- `POST /favorites` takes `keyword`, `halls` (empty = all halls), and `notes`. Returns 201 with the saved entry.
- Rejected with 422: keyword shorter than 2 characters after trimming, unknown hall.
- Rejected with 409: the keyword is already a favorite (case-insensitive).

**N2.** Application must display all upcoming occurrences of the user's watched items, showing date, meal period, and location.
- `GET /favorites/calendar` returns every stored serving from today onward that matches a favorite: date, meal, start and end time, hall, dish, station, and which favorite matched.
- Sorted by date, then start time. The web page shows it grouped by day.

**N3.** Application must let a user edit an existing watch entry, including which locations it covers.
- `PUT /favorites/{id}` replaces keyword, halls, and notes. A missing entry returns 404.
- The next `GET /favorites/calendar` reflects the change.

**N4.** Application must let a user delete a watch entry and remove its upcoming occurrences.
- `DELETE /favorites/{id}` returns 204. Its occurrences are gone from `/favorites/calendar` immediately.

**N5.** Application must let a user view a day's menu for one or all locations, filtered by meal and diet, with nutrition for each dish.
- `GET /menus?day=&hall=&meal=&diet=`. `diet` is one of `vegetarian`, `vegan`, `plant-based`, `mindful` and keeps dishes Sodexo labels that way. Unknown values return 422.
- Each serving includes `diets`, `calories`, `carbs_g`, `protein_g`, `fat_g`, and `portion`.
- `q` (keyword, same matching as favorites) and `days` (1–14) turn the same endpoint into a search of upcoming servings. The web page's "Find a dish" uses it to preview what a favorite would match before saving it.

### 4.2 Data

**D1.** Application must retrieve menu data for the UC dining locations for at least the next seven days.
- `python -m app.ingest`, `POST /menus/refresh`, and the page's Refresh button fetch today plus the next 6 days.
- A day Sodexo hasn't published comes back empty. That is a successful fetch with 0 servings, not an error.
- Downloads run 4 at a time. A full refresh took 15 s on 2026-09-24, down from about 35 s.

**D2.** Application must match watched items to menu entries tolerantly, so that minor naming variations still register as a match.
- Matching follows 6.4. Punctuation and plural handling are in the backlog.

**D3.** Application must record nutrition and diet labels where the source provides them.
- Per dish: calories, carbohydrates (g), protein (g), fat (g), portion text, and the diet flags `isVegan`, `isVegetarian`, `isPlantBased`, `isMindful`.
- A value Sodexo leaves blank is stored as empty (null), never as 0.
- Exposed in `/menu-items`, `/menus`, and `/favorites/calendar`.
- Allergens are not stored or filtered (6.3).

**D4.** Application must keep serving the last successfully retrieved menu data if the source is unavailable.
- A failed download is retried once. Sodexo sometimes stalls past the 20-second timeout on one request and answers the next in under a second.
- If both tries fail, the stored rows for that hall-day stay as they were. The refresh reports which fetches failed.
- The app starts and serves stored menus with no network access.

**D5.** Application must cover every UC Dining location that publishes a menu.
- Checked 2026-09-24 against all 21 location pages on ucdining.sodexomyway.com:
  - Center Court, MarketPointe, On The Green: menus published. Included.
  - Stadium View Café: has a Sodexo menu ID (38364005 / 39589), but the menu is empty every day checked (Sept 21–28). Its page describes a fixed menu (pizza by the slice and a build-your-own bowl station). Not included.
  - The other 17 (Chick-fil-A, Cincy Grill, Halal Shack, Starbucks locations, cafés, markets): hours only, no menu. Not included.
- Re-check before the final presentation.

### 4.3 Calendar (dropped 2026-09-24)

**C1–C3** (subscribable calendar feed, updates when menus change, event times from meal periods) were dropped after the interviews (2.1): neither participant uses a calendar for meals. They were also the riskiest part, needing a public HTTPS server, per-user tokens, and background refreshes. Meal-period times are still stored and shown in the app (N2).

### 4.4 Platform and course deliverables

**P1.** Application must store menu records and watch entries in a relational database.
- SQLite file (`uc_menu.db`) by default. Postgres works through `DATABASE_URL` (6.6).
- Each copy of the app has one user, so there are no accounts.

**P2.** Interactive Swagger/OpenAPI docs at `/docs` cover every endpoint.

**P3.** A web page at `/` lets a user:
- see one meal at every hall side by side, for any of the next 7 days, filtered by hall and diet, with nutrition per dish
- search upcoming servings for a keyword and save it as a favorite, choosing halls and notes
- list, edit, and delete favorites
- see this week's matches for their favorites, grouped by day
- refresh menus from Sodexo

**P4.** The code is in a public GitHub repository, and the README lets someone clone it, install it, load menus, and open the page.
- Waiting on the instructor to confirm this satisfies "public deployment" (open decision 1). If not, see 6.6.

**P5.** An automated pytest suite covers every N and D requirement and runs without network access.

---

## 5. Status

| ID | Status | Where | Tests |
|---|---|---|---|
| N1 | Done | `routers/favorites.py` | `test_crud.py` create tests |
| N2 | Done: API and the page's "This week" view | `GET /favorites/calendar` | `test_calendar_*` |
| N3 | Done | `PUT /favorites/{id}` | `test_update_*` |
| N4 | Done | `DELETE /favorites/{id}` | `test_delete_*`, `test_calendar_is_empty_after_favorite_is_deleted` |
| N5 | Done | `GET /menus` | `test_browse_*`, `test_servings_include_nutrition`, `test_menus_can_search_several_days_by_keyword` |
| D1 | Done (limited by how far ahead Sodexo publishes) | `ingest.py` | `test_refresh_*` |
| D2 | Partial: broad matching done; punctuation and plurals in backlog | `models.matches_keyword` | `test_calendar_keyword_matches_all_words_in_any_order`, `test_search_treats_wildcard_characters_literally` |
| D3 | Done | `sodexo.py`, `models.MenuItem` | `test_parse_amount_*`, `test_flatten_menu_reads_diet_labels_and_nutrition`, `test_search_results_include_nutrition` |
| D4 | Done | `ingest.refresh_menus` | `test_refresh_keeps_going_when_one_hall_fails`, `test_refresh_retries_a_download_that_fails_once` |
| D5 | Done: survey recorded above | `halls.py` | manual check |
| C1–C3 | Dropped 2026-09-24 | | |
| P1 | Done | `models.py`, `database.py` | |
| P2 | Done | `/docs` | |
| P3 | Done: every tab clicked through in Edge (light, dark, phone width) 2026-09-24 | `app/static/index.html` | `test_web_page_is_served_at_root`; manual check |
| P4 | In progress: public repo https://github.com/Marcus-Hollimon/UC-Menu-Project (2026-09-24); fresh-clone check passed on Python 3.11 (see Phase 2); instructor confirming it counts | `README.md` | manual check |
| P5 | Ongoing: 59 tests passing | `tests/` | |

---

## 6. Design

### 6.1 Architecture: local first

```
Sodexo menu API ──> app/ingest.py ──> uc_menu.db (SQLite) ──> FastAPI (app/main.py) ──> web page at /
                    (refresh: CLI,                            JSON API + /docs
                     button, or POST)
```

- Everything runs on the student's computer: `uvicorn app.main:app`, then open http://127.0.0.1:8000.
- Menus change daily, so the page has a Refresh button. It calls `POST /menus/refresh`, which is safe to leave unauthenticated because only the local machine can reach it. That depends on the server's default listen address (127.0.0.1), so the README warns against starting it with `--host 0.0.0.0`.
- Meal times come from each hall's regular hours in `app/halls.py`. Sodexo's menu API has no times.

### 6.2 Database changes

`menu_items` gains `is_plant_based`, `is_mindful`, `calories`, `carbs_g`, `protein_g`, `fat_g` (integers, nullable), and `portion` (text).

There are no migrations. After a table change, rebuild the local database with `python -m app.ingest --reset`, which drops every table and deletes local favorites. That is acceptable because every copy is a single-user local install.

### 6.3 Nutrition and diet data (D3, N5)

Sodexo sends numbers as text, sometimes with units: `"264"`, `"35g"`, `"523mg"`, or `""` when unknown. The leading number is kept and rounded to a whole number; a blank value becomes null.

Coverage on 2026-09-24 (468 dishes across the three halls):
- calories 458, carbohydrates 468, fat 468, protein 336, portion 468
- sugar, added sugar, and fiber were always 0, so they are not stored
- portion is free text such as `3 OZ`, `1/2 CUP`, `SLC=1/8`, `EA`, and is shown as-is

Diet labels:
- They come straight from Sodexo, unchecked, and they vary a lot. On 2026-09-22, 25 of 484 dishes were flagged vegan. On 2026-09-24, 120 of 468 were.
- Missing flags are common. For example, Cheese Pizza is not flagged vegetarian.
- A missing flag makes a diet filter hide a dish that would have fit, not show one that doesn't.
- Every dish flagged vegan on 2026-09-24 was also flagged vegetarian and plant-based.

Allergens are not used. On 2026-09-22 only 31 of 484 dishes listed any allergen, and 17 of 20 pizzas listed none. A "hide dishes with milk" filter would still show pizza, so the app does not offer one.

### 6.4 Keyword matching (D2)

Matching is deliberately broad. A dish matches when **every** word of the keyword appears **somewhere** in the dish name, even inside a longer word, ignoring case and word order. So "pizza" finds every pizza and "chick" finds "Chicken". Matching runs in SQL (`LIKE`, with `%` and `_` escaped so they aren't wildcards).

The cost is extra matches: "ham" also finds "Graham Cracker", and "cheese" matches 35 dishes including toppings like Crumbled Feta Cheese. "Find a dish" shows what a keyword matches before it is saved, so the user can add words or pick halls.

Backlog (only widens matches): ignore apostrophes and punctuation ("general tsos" → "General Tso's Chicken"), and let a plural keyword match its singular ("tacos" → "Chicken Soft Taco").

| Keyword | Must match | Must not match |
|---|---|---|
| `pizza` | Cheese Pizza; Lasagna Pizza | |
| `chick` | Chicken Soft Taco | |
| `pizza cheese` | Cheese Pizza | Pepperoni Pizza |
| `general tso` | Roasted General Tso Cauliflower; General Tso's Chicken | |
| `bbq pulled pork` | BBQ Pulled Pork  Sandwich (double space in source) | |
| `%%` | | anything (`%` is not a wildcard) |

### 6.5 Web page (P3)

- One file, `app/static/index.html`, with plain HTML, CSS, and JavaScript calling the JSON API. No build step and no CDN, so it works offline once menus are stored.
- Three tabs:
  - **Menus** (the default): day buttons for the next 7 days, then meal buttons for the meals served that day. It opens on the meal being served now, or the next one. Hall and diet selects. One column per hall, dishes grouped by station, each with diet labels, nutrition, and a ☆ button that saves the dish name as a favorite.
  - **Find a dish:** keyword and diet → upcoming servings over 7 days (`/menus?q=&days=7`), grouped by dish, with a form to save the keyword as a favorite, limited to chosen halls, with notes.
  - **My favorites:** each favorite with edit and delete, then "This week" from `/favorites/calendar`, grouped by day.
- The header has Refresh menus. The footer says menus show what is planned and dishes can run out.
- Dish names are inserted as text, never as HTML.

### 6.6 Hosting (on hold since 2026-09-24)

Only needed if the instructor says a public repo is not enough (open decision 1). What already exists:
- `DATABASE_URL` switches the app to Postgres (psycopg 3).
- A Neon database was created and passed a smoke test on 2026-09-22. It still holds that test data.
- Its password was reset on 2026-09-24, after the original had been shared in a chat log.
- The local `.env` line is commented out, so local runs use SQLite.

What a hosted version would still need:
- A per-browser ID so visitors don't share one favorites list.
- `POST /menus/refresh` locked or replaced with a scheduled job.
- A Render (or similar) web service, with its address added to the app's allowed hosts (`ALLOWED_HOSTS` in `app/main.py`).
- Neon's tables rebuilt with `python -m app.ingest --reset`, since they predate the nutrition and diet columns (6.2).

---

## 7. Plan

Each phase is done when its "done when" line is true and all tests pass.

### Phase 0: Backend alpha (done 2026-09-22)
- 7 days of menus for all three halls, with meal hours.
- Dish search, day menus, favorites CRUD, JSON week view. 34 passing tests.

### Phase 1: Diet, nutrition, web page (2026-09-24 to 09-27)
1. D3: store nutrition and diet labels. (Done 2026-09-24.)
2. N5: `diet`, `q`, and `days` on `/menus`; `diet` on `/menu-items`. (Done 2026-09-24.)
3. D1: parallel downloads so the Refresh button is quick. (Done 2026-09-24.)
4. P3: the web page per 6.5. (Done 2026-09-24.)
5. P4: README for clone-and-run (done 2026-09-24); public GitHub repo.

Done when: someone following only the README can open the page, see tonight's dinner at every hall filtered to vegan, save a favorite, and see when it's served this week.

### Phase 2: Testing milestone (by Wed 2026-10-01)
- Automated tests for every N and D requirement (section 8).
- Manual: follow the README in a fresh clone; click through every tab; a pass through `/docs`.
  - Fresh clone, 2026-09-24, Windows, Python 3.11: install, menu download, and all tests worked. Three problems found and fixed:
    1. `python` opens a Microsoft Store stub on a PC without Python. The README now says where to get Python.
    2. The Windows `activate` script is often blocked by PowerShell. The README now calls `.venv`'s Python directly.
    3. 8 of 21 menu downloads timed out while Sodexo was slow. Downloads are now retried once (D4).
- If possible, a short walkthrough of the page with an interview participant, noting confusion.
- Write up results, including failures.

Done when: every requirement in section 5 has a test or a recorded manual check.

### Phase 3: Final delivery (2026-10-02 to 10-06)
- Re-check D5 and hall hours on the UC Dining site.
- Final README and status table, AI reflection report, presentation.

### Backlog (only if time allows)
- D2 punctuation and plural matching.
- Meal-period filter on favorites (e.g., "only at breakfast").
- Hours-only list of the 17 locations without menus ("what's open now").
- Hosting (6.6).

---

## 8. Testing approach

**Automated (pytest, no network):**
- **Unit:** number parsing for nutrition; turning Sodexo JSON into rows (names, diet flags, nutrition, filler dishes skipped); meal hours by hall and weekday.
- **API:** each endpoint's success cases and its 404/409/422 cases; diet filter on `/menus` and `/menu-items`; `q` and `days` on `/menus`; nutrition fields present; the page is served at `/`.
- **Resilience:** a failed fetch keeps old data; refreshing twice doesn't duplicate.
- **Fixtures:** trimmed real Sodexo responses in `tests/fixtures/`, rebuilt with nutrition and diet fields.
- **Traceability:** each test module's docstring names the requirement IDs it covers.

**Manual:** README run-through in a fresh clone; every tab of the page; `/docs`.

---

## 9. Decisions

| # | Decision | Status |
|---|---|---|
| 1 | Does a public GitHub repo satisfy the "public deployment" deliverable? | **Open.** Asking the instructor 2026-09-24. If not, see 6.6. |
| 2 | Calendar subscription feed | **Dropped** 2026-09-24 (interviews, 2.1). |
| 3 | Where the app runs | **Local first** 2026-09-24. Neon + Render on hold (6.6). |
| 4 | Allergen filter | **Dropped** 2026-09-24. Data too sparse (6.3). |
| 5 | Keyword matching | **Broad** substring matching, decided 2026-09-22 (6.4). |
| 6 | Web page technology | **Plain HTML + JS**, no build step, decided 2026-09-22. |
| 7 | Meal hours | **Hard-coded** regular hours; breaks and holidays not handled. |

---

## 10. Known risks and limitations

- **Unofficial data source.** The Sodexo API and key come from the UC Dining website's own requests and could change without notice.
  - The key isn't secret: the UC Dining website sends it to every visitor's browser. But the service is Sodexo's, and calling it from another app may not be something their terms allow.
  - The app keeps its traffic small: 21 requests per refresh, 4 at a time, with at most one retry each, and only when the user asks for a refresh.
- **Menus show what's planned.** Dishes can run out or be swapped (2.1).
- **Diet labels are Sodexo's and inconsistent** (6.3). The app never claims a dish is safe for an allergy; the page footer and the README tell people to ask dining staff.
- **Security (reviewed 2026-09-24).** Low risk while the app runs only on the user's own computer and stores only menus and favorites.
  - Checked and passing: no password or `.env` in the git history; dish names are inserted into the page as text, not HTML; every database query is parameterized; no known vulnerabilities in the 28 installed libraries (pip-audit); the server listens only on 127.0.0.1; a forged cross-site "add favorite" request is rejected.
  - Added the same day: the app refuses any request not addressed to `127.0.0.1` or `localhost` (`TrustedHostMiddleware` in `app/main.py`). This blocks DNS rebinding, and also requests over the local network if someone starts it with `--host 0.0.0.0`. Tested in `tests/test_security.py`.
  - The Neon password, shared in a chat log on 2026-09-22, was reset on 2026-09-24.
- **Short menu horizon.** Sodexo publishes some halls only a few days ahead, so the end of the 7-day window can be empty.
- **Hard-coded hours.** Breaks and holidays show regular hours.
- **Broad matching over-matches** (6.4).
- **Each install has its own data.** Favorites don't sync between computers.

## 11. Out of scope

- Calendar subscriptions, push, email, or SMS alerts.
- User accounts and hosting (unless decision 1 requires hosting).
- Allergen filtering.
- Menus for retail locations (none are published, D5).
- Nutrition goals and tracking.
