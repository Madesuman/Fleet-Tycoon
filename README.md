# Fleet Tycoon v2

Delivery-company game for 25 players in 5 teams of 5, plus 2 organizers. 60 minutes. Phones to play, one laptop on the projector.
Spec: "Fleet Tycoon: Scenario Spec v1" (the Docs page). All money is ¥M per fleet per year, multiples of 5.

## Run it
Local test: `pip install -r requirements.txt` then `streamlit run app.py`

Free hosting (no domain needed):
1. Put this folder in a GitHub repo (private is fine).
2. share.streamlit.io, New app, main file `app.py`.
3. In app Settings, Secrets, add: `ADMIN_PASSWORD = "your-password"` (default is `cae2026`).
4. You get `https://something.streamlit.app`. Paste it into the Admin page when you start the game.

## Pages
- `app.py` (phones): log in with team, player number 1 to 5 and the 4 digit team code. Each player has a seat that rotates every year.
- `Leaderboard` (projector): rough picture only. Ranks, stamps, mood faces, profit arrows, event cards. Refreshes every 3 s.
- `Admin` (organizer): start, timer, reveal mid-year card, merger, reveal results, next year, CSV, join links and codes.

## Seats (player seat = (player number - 1 + year) mod 5)
| Seat | Decides | Sees |
| --- | --- | --- |
| Shacho | signs off, mid-year sign-off, override of any field | cash, net worth, the full result detail with every line |
| Engineering | powertrain, trade-in (year 4), autonomy kit (year 5) | energy and subsidy news, price sheet |
| HR | driver grade | labour market and union news |
| Operations | mountain contract (year 1), tender bids (year 2) | market revenue and contracts |
| Compliance and Maintenance | AC, dampers, seats | regulation news |

Each seat sees only its own news, so the team has to talk. Only the shacho sees the money detail.

## Run of show (60 min)
Intro 8, five rounds of about 9 (design 4, mid-year card 2, reveal 3), finale 7.
Per round: Admin starts the timer, teams plan and the shacho signs, Admin reveals the mid-year card, teams decide, Admin reveals results, debrief, next year.
Year 3 mid-year card is the merger window: Admin merges two eligible teams (bottom two or bankrupt).

## Images
49 pictures, listed in `assets/MANIFEST.md` (key, size, what it shows). Drop PNG files named exactly like the key into `assets/`.
No text inside the pictures. Missing files fall back to an emoji, so the game works with none.

## Before the day
- Dry run alone: Admin, start game, then "Fill unsigned teams with bots", reveal, repeat.
- Test the URL on the projector laptop on the real network. Phones on mobile data avoid office wifi filtering.
- Open the URL 10 minutes early. Free apps sleep when idle. Do not redeploy mid-game: the SQLite file lives on the server and is wiped on restart.
- `python selftest.py` checks the balance tables. `python e2e_test.py` plays full games headless.

## Tuning
Everything is a table in `scenario.py`: event effects, mood thresholds, crash odds, merger grant, kit odds.
After a change run `python selftest.py`. The five reference plans must all total exactly 30.

## Known rough edges (flagged in the spec)
- Mood and crash numbers are first guesses.
- Tie-break for equal final net worth is not built yet.
- Heavy comfort items cost 5 each, same as light, to keep every number a multiple of 5.
- A loan of 20 for an EV fleet is not needed because start cash is 120; any other loan costs 5% interest and may give non-round numbers.
