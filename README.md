# Arcade Event Creator

Web form: select a show → auto-fill details → create a Leap ticket event + Airtable record in one submit.

## How it works

- **Backend (`app.py`)** — Flask. Serves the form, proxies Leap (ShowClix V2):
  creates the event shell (`POST /events`), attaches a General Admission price
  level (`POST /price_levels`), and returns the public ticket URL. Also manages
  the show catalog (`shows.json`).
- **Frontend (`templates/index.html`)** — after the backend returns the ticket
  URL, the browser posts the record directly to the Airtable **Schedule** table.
  The `const AT = {...}` block is filled in by Flask from `AT_API_KEY`,
  `AT_BASE_ID` and `AT_TABLE` in `.env` — don't hardcode credentials there.

  Because the browser talks to Airtable directly, the token is served to every
  client that loads the page. Fine on a trusted LAN; if this ever goes public,
  proxy the Airtable write through `app.py` instead.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in .env
```

## Getting a Leap API token

Tokens are self-service in the Leap Admin UI (the old ShowClix
`POST /api/registration` endpoint no longer exists):

1. Log in at <https://admin.leapevents.com>
2. Go to <https://admin.leapevents.com/user>
3. Generate an **Integration Token** and copy it
4. Run the setup helper and paste it:

```bash
python get_leap_token.py
```

The script validates the token, writes `LEAP_API_TOKEN` to `.env`, and helps
you pick `LEAP_SELLER_ID` and `LEAP_VENUE_ID` from your account.

If Leap calls ever start failing with 401, generate a fresh token in the
admin and rerun the script.

## Running

```bash
python app.py
# Runs on http://localhost:5050
```

It binds to `0.0.0.0`, so any machine on the network can reach it at
`http://<your-ip>:5050`.

## Endpoints

| Route | Purpose |
|---|---|
| `GET /` | The form |
| `GET /shows.json` | Show catalog (consumed by the frontend) |
| `GET /show-data/<name>` | Single show details |
| `GET /api/venues` | Venues from your Leap account (frontend falls back to a hardcoded list if unavailable) |
| `GET /api/series` | Series from your Leap account |
| `POST /shows` | Append a new show to `shows.json` |
| `POST /create` | Create the Leap event + price level, return ticket URL |

## Editing shows

Use the **Add Show to Catalog** tab, or edit `shows.json` by hand. Each show
has: `name`, `slug`, `description`, `short_description`, `default_price`,
`default_capacity`, `default_duration_minutes`, `tags`, and optionally
`image_url`.

## After creation

The Airtable Schedule record is created with `Status = Draft` and the ticket
URL written into `Showclix Ticket Link`, so downstream sync (ghostlight →
WordPress) picks it up as usual.

## WordPress auth (future)

The app is currently standalone with no authentication. The plan is to
eventually put it behind WordPress auth; nothing in the app assumes it yet.
# ACT_leepair
# ACT_leepair
# ACT_leepair
